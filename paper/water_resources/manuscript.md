# When does a river forecast change a decision?
## Flood warning at Gandak Barrage and water allocation on the Potomac

### Abstract

River forecasts can affect the timing of flood warnings and the amount of water promised to users. We evaluated these decisions in two historical case studies. At Gandak Barrage, India, we compared forecasts using recent inflow, an upstream gauge at Devghat in Nepal, and archived rainfall forecasts. On 25 September 2026, the gauge and rainfall together signalled a study-defined high-flow threshold six hours before it was crossed. The gauge alone gave four hours of warning. Only one qualifying onset occurred. For the subsequent crest, the combined model predicted 22,780 m³/s against an observed 15,396 m³/s. At 24 hours, carrying the last inflow forward also gave a smaller mean absolute error than the combined model. On the Potomac River, we simulated daily allocations using six years of forecasts. Planning for a low flow reduced the frequency of overcommitment from 63.5% to 1.5%, at the expense of greater unmet demand. Under a linear cost assumption, that choice was preferable when the cost per unit of overcommitment exceeded 3.55 times the cost per unit of unmet demand. These results distinguish three outcomes a forecast user might value differently: earlier warning, an accurate crest estimate, and a reliable water commitment.

### Research question and related work

Kratzert et al. [1] evaluated LSTM rainfall–runoff models across 241 catchments. Raftery et al. [2] calibrated weather forecast ensembles. Their methods motivate the Potomac benchmark, where the question is how forecast uncertainty changes a daily allocation. Delaney et al. [3] already evaluated ensemble forecasts for reservoir operations. Our narrower addition is a break-even cost for an explicit allocation rule, together with an audit of uncertainty in different flow conditions.

Earlier work also used rainfall to forecast Narayani floods at Devghat [4]. Kumar et al. [5] studied daily water levels at Triveni at one-, five- and ten-day leads. We ask a different question at the downstream barrage: how much warning does an upstream reading add once its reporting delay is respected, and does earlier warning improve the predicted magnitude of the crest? Two independent cases address different decisions. We estimate no transfer of a fitted model between basins.

---

### Gandak experiment

The target is hourly barrage inflow in the Central Water Commission archive [6]. We retained the existing August–October 2026 study window and data cleaning. All training targets precede 16 September. We joined the last 25 hours of local flow history to 10,466 dated Devghat records from Nepal’s BIPAD archive [7]. At each issue time, the latest eligible gauge measurement had to be at most two hours old, and both its creation and last modification in the archive had to precede or equal issue time. Features were level and six-hour change. The latest gauge level at the crest forecast was 11.80 m, compared with a maximum of 7.39 m in the pre-test period under the same availability rule.

For rainfall we retrieved individual 00 UTC NOAA GFS runs through Open-Meteo [8]. We averaged forecasts at three upstream grid points near Pokhara, Besisahar and Gorkha. The predictors summed forecast precipitation over the preceding six hourly endpoints and the next forecast horizon. Each issue used a single archived run at least 12 hours old. A 24-hour minimum age tested sensitivity to later delivery. These sites sample part of the basin. Actual GFS file delivery times and historical revisions to the barrage series are unknown.

We fitted a separate regression at each lead from 1 to 72 hours. Each used the original ridge penalty and training-only scaling. The comparisons used identical complete training and test rows for the local, gauge-added, rain-added and combined regressions. Persistence carries the current inflow forward. At 24 hours we could evaluate 809 of 975 otherwise eligible test issues. Missing or stale inputs account for the excluded cases. The results describe the hours on which the extended model could run.

### Did the extra inputs give earlier warning?

We defined high flow as the 95th percentile of training inflow, 5,022 m³/s. This is a research threshold. An onset required 24 preceding hours below it. From each eligible hour below the threshold, a warning meant the model predicted at least one crossing in the next 24 hours. At 22:00 IST on 25 September the observed inflow crossed the threshold. The combined model first warned at 16:00, the gauge model at 18:00. Rain alone and local history alone gave no advance warning. The combined model issued six positive hourly decisions, all for this one event, across 739 eligible decisions. This sample gives little information about the long-run false-alarm rate.

Using a 24-hour rainfall release lag reduced the combined warning to five hours. Using the training 90th or 99th percentile as the event threshold gave five and six hours respectively under the primary release assumption. All three thresholds describe the same flood episode.

---

### Did earlier warning improve the crest forecast?

![Gandak forecast and errors](../../results/gandak_warning/warning_comparison.png)

Figure 1. The left panel follows one forecast issued at 14:00 IST on 27 September. The right panel compares all models at each lead on matched observations. Gauge and rain additions include the local barrage history.

The observed maximum was 15,396 m³/s at hour 14. The local regression predicted a maximum of 12,505 m³/s. Adding the gauge and rain instead produced 22,780 m³/s at hour 7, an overshoot of 7,384 m³/s. The event extended beyond the upstream levels seen in training. Extrapolation is a plausible explanation for the overshoot. A single event cannot isolate its cause.

| 24-hour model | Mean absolute error (m³/s) | Root-mean-square error (m³/s) |
| --- | ---: | ---: |
| Last reading | 749 | 1,671 |
| Barrage history | 1,057 | 1,861 |
| Barrage and Devghat | 989 | 1,641 |
| Barrage and rain | 972 | 1,790 |
| Barrage, Devghat and rain | 896 | 1,534 |

The combined model reduced errors relative to the local regression at 24 hours. Relative to the last reading it made larger absolute errors on average, but scored better on the measure that gives large errors more weight. A paired three-day block bootstrap estimated a combined-minus-local mean absolute error difference of −161 m³/s (95% interval −329 to −59). Against the last reading the difference was +147 m³/s (−154 to +352). These descriptive intervals use 2,000 circular resamples of calendar days and only 37 matched test dates. The September episode was known during study design.

---

### Potomac allocation and forecast uncertainty

For USGS gauge 01646500 at Little Falls [9], four neural networks used 30 days of flow history to forecast the next day. Training used 1990–2009, model selection 2010–2014, ensemble calibration 2015–2019, and testing 2020–2025. Across 2,192 test days the stacked LSTM achieved a root-mean-square error of 111.2 m³/s, compared with 145.8 for persistence. The calibrated ensemble supplied a range as well as a mean.

We checked whether the nominal 90% forecast interval covered observed flows under different conditions. We defined the bands from calibration-period flow and assigned each forecast using the previous day’s reading, which the model already knew. Coverage was 94.4% after low flows (339 days), 92.9% in the middle band (1,782 days), and 88.7% after high flows (71 days). The high-flow sample is small. The pooled 93.0% coverage conceals this difference.

The allocation replay assumes total demand of 3 million m³/day, a 20 m³/s environmental reserve and a diversion limit of 10% of flow above that reserve. Planning with the ensemble fifth percentile instead of its mean avoided 75,809 m³ of excess commitments per day but left another 269,332 m³ of demand unmet. If each type of loss carries a constant unit cost, the break-even ratio is 269,332 / 75,809 = 3.55. The conservative rule minimizes cost between these two policies only above this ratio. Annual break-even ratios ranged from 3.04 to 4.09. These are trade-offs in a hypothetical scenario, not measured prices or regional operating rules.

### What would strengthen the evidence?

First, freeze the model, threshold and alert rule before testing a separate monsoon with multiple floods and quiet periods. Report warning lead, missed episodes, false alert episodes, crest bias and the fraction of hours with an available forecast. Include a fallback policy during gauge outages. Next, compare the regression with a travel-time routing model using basin-wide rainfall and a forecast from the water department matched by target, time and units. Finally, repeat the Potomac decision analysis with seasonal demand and costs supplied by a water manager. This would test whether either simulated rule fits the decisions people actually make.

### Sources

[1] Kratzert et al. (2018). Rainfall–runoff modelling using LSTM networks. https://doi.org/10.5194/hess-22-6005-2018

[2] Raftery et al. (2005). Using Bayesian model averaging to calibrate forecast ensembles. https://doi.org/10.1175/MWR2906.1

[3] Delaney et al. (2020). Forecast informed reservoir operations using ensemble streamflow predictions. https://doi.org/10.1029/2019WR026604

[4] Artan et al. (2011). Bias-adjusted satellite-based rainfall estimates for predicting floods in the Narayani Basin. https://doi.org/10.1111/j.1753-318X.2011.01121.x

[5] Kumar et al. (2025). Multi-lead-time water-level forecasting in the Gandak River Basin. https://harbinengineeringjournal.com/index.php/journal/article/view/4857

[6] Central Water Commission readings, public historical archive. https://github.com/diagram-chasing/cwc-flood-forecasts

[7] Nepal DHM, Narayani at Devghat, BIPAD observation archive, station 25, series 4140. https://bipadportal.gov.np/api/v1/river/?station=25

[8] NOAA GFS via Open-Meteo, individual forecast runs. https://open-meteo.com/en/docs/single-runs-api

[9] USGS, Potomac River near Washington, DC, station 01646500. https://waterdata.usgs.gov/monitoring-location/USGS-01646500/
