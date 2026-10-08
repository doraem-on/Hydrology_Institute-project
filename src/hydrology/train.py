"""Reproducible rolling next-day hindcast; separate tuning and BMA calibration."""
import argparse
import copy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import random
import time

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, TensorDataset

from .bma import ForecastBMA
from .data import make_windows
from .models import NAMES, build_model


def metrics(observed, predicted):
    y, p = np.asarray(observed, float), np.asarray(predicted, float)
    if y.shape != p.shape or y.size < 2 or not np.isfinite([y, p]).all():
        raise ValueError("Metrics need aligned finite arrays")
    residual = p-y
    variance = np.sum((y-y.mean())**2)
    correlation = np.corrcoef(y, p)[0, 1] if y.std() > 0 and p.std() > 0 else np.nan
    kge = 1-np.sqrt((correlation-1)**2+(p.std()/y.std()-1)**2+(p.mean()/y.mean()-1)**2) if y.std() > 0 and y.mean() != 0 else np.nan
    def finite(value):
        return float(value) if np.isfinite(value) else None
    return {"n": len(y), "rmse_cms": float(np.sqrt(np.mean(residual**2))),
            "mae_cms": float(np.mean(np.abs(residual))),
            "nse": finite(1-np.sum(residual**2)/variance) if variance > 0 else None,
            "kge_2009": finite(kge), "bias_cms": float(residual.mean())}


@torch.no_grad()
def predict(model, x, batch_size=512):
    model.eval()
    return np.concatenate([model(torch.from_numpy(x[i:i+batch_size])).numpy()
                           for i in range(0, len(x), batch_size)])


def run(args):
    if args.epochs < 1 or args.patience < 1 or args.batch_size < 1:
        raise ValueError("Epochs, patience and batch size must be positive")
    torch.set_num_threads(args.threads)
    torch.use_deterministic_algorithms(True)
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    data = make_windows(pd.read_csv(args.data), args.lookback, args.train_end,
                        args.validation_end, args.calibration_end)
    out = args.output
    if out.exists() and any(out.iterdir()):
        raise ValueError("Output directory is nonempty; choose a new run directory")
    (out/"checkpoints").mkdir(parents=True)
    masks, x, y = data["masks"], data["x"], data["y"]
    predictions, histories, training_seconds = {}, {}, {}
    for name in NAMES:
        torch.manual_seed(args.seed)
        model = build_model(name, args.hidden, args.lookback)
        optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)
        loader = DataLoader(TensorDataset(torch.from_numpy(x[masks["train"]]),
                                         torch.from_numpy(y[masks["train"]])),
                            batch_size=args.batch_size, shuffle=True,
                            generator=torch.Generator().manual_seed(args.seed))
        best, best_state, stale, history = float("inf"), None, 0, []
        start = time.monotonic()
        for epoch in range(1, args.epochs+1):
            model.train()
            total, count = 0.0, 0
            for xb, yb in loader:
                optimizer.zero_grad()
                loss = torch.mean((model(xb)-yb)**2)
                if not torch.isfinite(loss):
                    raise ValueError(f"Nonfinite training loss: {name}")
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                total += float(loss.detach())*len(yb)
                count += len(yb)
            validation = float(np.mean((predict(model, x[masks["validation"]])-y[masks["validation"]])**2))
            history.append({"epoch": epoch, "train_mse_scaled_log": total/count,
                            "validation_mse_scaled_log": validation})
            print(f"{name}: epoch={epoch} train={total/count:.5f} validation={validation:.5f}", flush=True)
            if validation < best-1e-6:
                best, best_state, stale = validation, copy.deepcopy(model.state_dict()), 0
            else:
                stale += 1
            if stale >= args.patience:
                break
        model.load_state_dict(best_state)
        predictions[name] = predict(model, x)*data["scale"]+data["mean"]
        training_seconds[name] = time.monotonic()-start
        histories[name] = history
        torch.save({"model": name, "state_dict": best_state, "hidden": args.hidden,
                    "lookback": args.lookback, "log_mean": data["mean"], "log_scale": data["scale"]},
                   out/"checkpoints"/f"{name}.pt")
    matrix = np.column_stack([predictions[name] for name in NAMES])
    calibration = masks["calibration"]
    bma = ForecastBMA().fit(matrix[calibration], np.log1p(data["q"][calibration]))
    if not bma.converged:
        raise RuntimeError("BMA calibration did not converge; no final test scores published")
    # Smearing correction is fitted only on calibration residuals so base-model
    # conditional means and the BMA mean are compared on the discharge scale.
    smearing = np.mean(np.exp(np.log1p(data["q"][calibration])[:, None]-matrix[calibration]), axis=0)
    individual = np.maximum(np.exp(matrix)*smearing-1, 0)
    test = masks["test"]
    q = data["q"][test]
    table = pd.DataFrame({"date": data["dates"][test].strftime("%Y-%m-%d"),
                          "observed_cms": q, "persistence_cms": data["persistence"][test]})
    scores = {"persistence": metrics(q, data["persistence"][test])}
    for k, name in enumerate(NAMES):
        table[name+"_cms"] = individual[test, k]
        scores[name] = metrics(q, individual[test, k])
    table["equal_average_cms"] = individual[test].mean(axis=1)
    table["bma_mean_cms"] = bma.mean_discharge(matrix[test])
    table["bma_lower90_cms"] = bma.quantile_discharge(matrix[test], 0.05)
    table["bma_upper90_cms"] = bma.quantile_discharge(matrix[test], 0.95)
    scores["equal_average"] = metrics(q, table.equal_average_cms)
    scores["bma"] = metrics(q, table.bma_mean_cms)
    scores["bma"]["coverage90"] = float(((q >= table.bma_lower90_cms) & (q <= table.bma_upper90_cms)).mean())
    scores["bma"]["mean_width90_cms"] = float((table.bma_upper90_cms-table.bma_lower90_cms).mean())
    split_summary = {name: {"n": int(mask.sum()), "start": str(data["dates"][mask].min().date()),
                           "end": str(data["dates"][mask].max().date())} for name, mask in masks.items()}
    metadata = {"config": {k: str(v) if isinstance(v, Path) else v for k,v in vars(args).items()},
                "data_sha256": hashlib.sha256(args.data.read_bytes()).hexdigest(),
                "split": split_summary, "normalization": {"mean": data["mean"], "scale": data["scale"]},
                "model_order": NAMES, "smearing": smearing.tolist(), "training_seconds": training_seconds,
                "versions": {p: importlib.metadata.version(p) for p in ["torch", "numpy", "pandas", "scipy"]},
                "forecast_protocol": "Rolling next-day hindcast from the previous 30 days (or configured lookback); observed past test flows become available at each issue date. No future flows or weather."}
    table.to_csv(out/"test_predictions.csv", index=False)
    cal_table = pd.DataFrame(matrix[calibration], columns=NAMES)
    cal_table.insert(0, "date", data["dates"][calibration].strftime("%Y-%m-%d"))
    cal_table["observed_log1p_cms"] = np.log1p(data["q"][calibration])
    cal_table.to_csv(out/"calibration_predictions.csv", index=False)
    for filename, obj in [("metrics.json", scores), ("run.json", metadata),
                          ("training_history.json", histories), ("bma.json", bma.to_dict())]:
        (out/filename).write_text(json.dumps(obj, indent=2, allow_nan=False)+"\n")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    shown = table[table.date >= table.date.iloc[-1][:4]+"-01-01"]
    dates = pd.to_datetime(shown.date)
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.fill_between(dates, shown.bma_lower90_cms, shown.bma_upper90_cms,
                    alpha=0.2, color="#2563eb", label="BMA 90% interval")
    ax.plot(dates, shown.observed_cms, color="#111827", lw=1, label="Observed")
    ax.plot(dates, shown.bma_mean_cms, color="#2563eb", lw=1, label="BMA mean")
    ax.set(title="Potomac daily streamflow: rolling next-day hindcasts", ylabel="Discharge (m³/s)", xlabel="Date")
    ax.legend(frameon=False, ncol=3)
    fig.tight_layout()
    fig.savefig(out/"test_hydrograph.png", dpi=180)
    plt.close(fig)
    print(json.dumps(scores, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data/processed/streamflow.csv"))
    parser.add_argument("--output", type=Path, default=Path("results/baseline_seed42"))
    parser.add_argument("--lookback", type=int, default=30)
    parser.add_argument("--hidden", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--train-end", default="2009-12-31")
    parser.add_argument("--validation-end", default="2014-12-31")
    parser.add_argument("--calibration-end", default="2019-12-31")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
