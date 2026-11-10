# Which model signalled first?

Ridge regression, random forest and gradient boosting all first predicted a crossing at 16:00 IST on 25 September 2026. The barrage crossed at 22:00, while Khadda had already reached its local warning level at 15:00. All six positive barrage decision hours for each model related to this one flood. Persistence gave no advance warning at the barrage.

Run from the repository root after following the [original input guide](../gandak_warning/README.md). The comparison uses scikit-learn from the existing requirements-satellite-lock.txt.

    PYTHONPATH=src .venv/bin/python scripts/gandak_model_comparison.py

For each lead from 1 to 24 hours, both tree models fit the same change in log(1 + inflow) as the deposited combined ridge model. All models use identical features and training rows. Training target times precede 16 September. Issue-time forecasts require available features only. Model settings were fixed for the comparison with no tuning on the holdout. The September event was known when designing this follow-up.

The random forest uses 150 trees of maximum depth 6. Gradient boosting uses 100 sequential trees of maximum depth 2 with learning rate 0.05. Both require at least 10 training samples per leaf. The random seed is 42. settings.json gives all parameters and the library version. The baseline carries the latest barrage inflow forward.

forecasts.csv.gz contains 19,416 matched forecasts per method (809 issues × 24 leads). barrage_audit.csv counts a false hour when an alert was issued below threshold and the barrage failed to reach 5,021.658 m³/s in the following 24 hours. barrage_onsets.csv records the earliest qualifying decision for each onset. The Khadda tables repeat the original downstream checks. A positive interval in khadda_timing.csv means the signal preceded the local crossing. The 47 hours between the signal and Khadda’s higher danger level is an observed elapsed interval. Each model forecast barrage inflow only.
