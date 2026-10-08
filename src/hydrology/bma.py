"""Forecast BMA: bias-corrected Gaussian mixture on log1p discharge.

Empirical calibration following the forecast-mixture approach of Raftery et al.
(2005), not a fully Bayesian posterior over neural-network parameters.
"""
import numpy as np
from scipy.special import logsumexp, ndtr


class ForecastBMA:
    def fit(self, predictions, observed, max_iter=10000, tolerance=1e-8):
        if max_iter < 1 or tolerance <= 0:
            raise ValueError("EM iteration budget and tolerance must be positive")
        f = np.asarray(predictions, dtype=float)
        y = np.asarray(observed, dtype=float)
        if (f.ndim != 2 or y.shape != (len(f),) or len(y) < 3 or f.shape[1] < 1
                or not np.isfinite(f).all() or not np.isfinite(y).all()):
            raise ValueError("BMA requires finite, aligned calibration predictions and targets")
        self.intercept, self.slope = np.zeros(f.shape[1]), np.zeros(f.shape[1])
        for k in range(f.shape[1]):
            if f[:, k].std() < 1e-10:
                self.intercept[k] = y.mean()
            else:
                self.intercept[k], self.slope[k] = np.linalg.lstsq(
                    np.column_stack((np.ones(len(f)), f[:, k])), y, rcond=None)[0]
        mu = self.locations(f)
        errors = (y[:, None] - mu) ** 2
        self.weights = np.full(f.shape[1], 1 / f.shape[1])
        floor = max(float(y.var()) * 1e-6, 1e-8)
        self.variance = max(float(errors.mean()), floor)
        self.log_likelihood = []
        self.converged = False
        for _ in range(max_iter):
            logp = np.log(self.weights) - 0.5 * (np.log(2*np.pi*self.variance) + errors/self.variance)
            normalizer = logsumexp(logp, axis=1)
            likelihood = float(normalizer.sum())
            self.log_likelihood.append(likelihood)
            if len(self.log_likelihood) > 1 and abs(likelihood-self.log_likelihood[-2]) <= tolerance*(1+abs(likelihood)):
                self.converged = True
                break
            responsibilities = np.exp(logp - normalizer[:, None])
            self.weights = np.maximum(responsibilities.mean(axis=0), 1e-12)
            self.weights /= self.weights.sum()
            self.variance = max(float((responsibilities*errors).sum()/len(y)), floor)
        return self

    def locations(self, predictions):
        f = np.asarray(predictions, dtype=float)
        if f.ndim != 2 or f.shape[1] != len(self.slope) or not np.isfinite(f).all():
            raise ValueError("Invalid BMA prediction matrix")
        return self.intercept + self.slope*f

    def mean_discharge(self, predictions):
        mu = self.locations(predictions)
        sigma = np.sqrt(self.variance)
        # Exact mean for Q=max(exp(Z)-1, 0), including the mass at zero.
        component_mean = np.exp(mu+self.variance/2)*ndtr((mu+self.variance)/sigma) - ndtr(mu/sigma)
        return np.maximum(component_mean @ self.weights, 0)

    def quantile_discharge(self, predictions, probability):
        if not 0 < probability < 1:
            raise ValueError("Probability must be between zero and one")
        mu = self.locations(predictions)
        sigma = np.sqrt(self.variance)
        low, high = mu.min(axis=1)-12*sigma, mu.max(axis=1)+12*sigma
        for _ in range(80):
            mid = (low+high)/2
            cdf = ndtr((mid[:, None]-mu)/sigma) @ self.weights
            low = np.where(cdf < probability, mid, low)
            high = np.where(cdf >= probability, mid, high)
        return np.maximum(np.expm1((low+high)/2), 0)

    def to_dict(self):
        return {"weights": self.weights.tolist(), "intercept": self.intercept.tolist(),
                "slope": self.slope.tolist(), "shared_log_variance": self.variance,
                "converged": self.converged, "em_iterations": len(self.log_likelihood),
                "log_likelihood": self.log_likelihood}
