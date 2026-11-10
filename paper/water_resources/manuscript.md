# When does a river forecast change a decision?
## Flood warning at Gandak Barrage and water allocation on the Potomac

### Abstract

We tested when river forecasts help people issue flood warnings or decide how much water to promise. At Gandak Barrage in India, upstream water levels and archived rainfall forecasts gave six hours of warning before the one qualifying high-flow event in 2026. The same model overestimated the subsequent crest by 7,384 m³/s. Across 809 forecasts, its average crest error was 4,715 m³/s when the upstream gauge exceeded its training range and 1,673 m³/s within that range. Earlier monsoons lacked the hourly barrage records needed to validate this warning model. A separate daily model trained in 2024 missed the one assessable crossing in 2025. On the Potomac River, we replayed water commitments against municipal diversions reconstructed from USGS records on 2,041 days. Planning with the lower end of the flow forecast cut overcommitment from 35.7% of days to 0.9%, while leaving an additional 100,674 m³/day of demand unmet on average. Under the simulated allocation rule, the cost of promising water that could not be supplied had to exceed about four times the cost of leaving the same volume unmet for conservative planning to pay off.

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

### When should a flood forecaster be cautious?

At issue time we flagged Devghat levels below 3.943 m or above 7.389 m, the limits in the combined model’s training rows. For each complete 72-hour forecast, we compared its predicted maximum with the observed maximum over the same hours. Each forecast contributed one absolute peak error, even if the two peaks occurred at different hours. The September crest forecast was flagged high. The overlapping windows often cover the same flood.

| Upstream gauge at issue | Complete forecasts | Mean absolute peak error (m³/s) |
| --- | ---: | ---: |
| Below training range | 354 | 2,259 |
| Within training range | 406 | 1,673 |
| Above training range | 49 | 4,715 |

Of the 81 forecasts with the largest peak errors, 19 were flagged high, 28 low and 34 fell inside the training range. A high flag identified 19 large errors in 49 forecasts. It signals when a crest estimate deserves closer inspection. Its long-run reliability still needs testing across other floods.

### What could earlier monsoons actually test?

We saved the 72 fitted regressions, their scaling constants and the warning threshold. The CWC archive [6] contained 43, 152 and 153 inflow readings in June–October of 2023, 2024 and 2025 respectively, all at 08:00 IST. None of those seasons supplied the 25 consecutive hours needed to issue even one forecast with the frozen model. Bihar’s historical bulletins report downstream discharge [10]. Gate operations can change that quantity. The six-hour warning result therefore remains a single-season finding.

A separate test used the morning readings at their recorded frequency. A ridge regression learned to predict next-morning inflow from the current reading and its one-day change, using 148 training pairs in 2024. We fixed the threshold at the 2024 morning inflow’s 95th percentile (5,516 m³/s). In 2025, 145 forecasts could be scored. There were 144 issues below the threshold. On 16 September the model forecast 4,108 m³/s for the next morning, when 6,082 m³/s was observed. Both the daily model and persistence missed this sole assessable crossing and gave zero false warnings. Their mean absolute errors were 354 and 353 m³/s respectively. These data can detect crossings between morning readings only when the flow remains high at the second reading.

---

### Potomac allocation and forecast uncertainty

For USGS gauge 01646500 at Little Falls [9], four neural networks used 30 days of flow history to forecast the next day. Training used 1990–2009, model selection 2010–2014, ensemble calibration 2015–2019, and testing 2020–2025. Across 2,192 test days the stacked LSTM achieved a root-mean-square error of 111.2 m³/s, compared with 145.8 for persistence. The calibrated ensemble supplied a range as well as a mean.

We checked whether the nominal 90% forecast interval covered observed flows under different conditions. We defined the bands from calibration-period flow and assigned each forecast using the previous day’s reading, which the model already knew. Coverage was 94.4% after low flows (339 days), 92.9% in the middle band (1,782 days), and 88.7% after high flows (71 days). The high-flow sample is small. The pooled 93.0% coverage conceals this difference.

The allocation replay assumes total demand of 3 million m³/day, a 20 m³/s environmental reserve and a diversion limit of 10% of flow above that reserve. Planning with the ensemble fifth percentile instead of its mean avoided 75,809 m³ of excess commitments per day but left another 269,332 m³ of demand unmet. If each type of loss carries a constant unit cost, the break-even ratio is 269,332 / 75,809 = 3.55. The conservative rule minimizes cost between these two policies only above this ratio. Annual break-even ratios ranged from 3.04 to 4.09. These values describe the specified scenario. Regional operating costs are unknown.

---

### What changed with recorded Potomac water use?

USGS defines adjusted flow at Little Falls as measured river flow plus upstream diversions reported by cooperating agencies [11]. We subtracted the two published daily flows and converted cubic feet per second to m³/day. Of 2,192 test dates, 2,041 had a positive difference and approved values for both series. We excluded four missing pairs, 145 pairs with provisional or estimated values, and two zero differences. Published flows are rounded, so the differences approximate fulfilled withdrawals. They cannot reveal requests that suppliers had to turn down.

We used each day’s reconstructed volume as the simulated request and kept the original forecasts, reserve and diversion cap. The daily amounts averaged 1.31 million m³. Across matched days the conservative rule reduced overcommitment from 35.7% to 0.9%. It avoided 25,091 m³/day of excess commitments while leaving another 100,674 m³/day unmet. The resulting break-even cost ratio was 4.01. Holding demand constant at the same mean gave 4.25. Using the original 3 million m³/day on those same dates gave 3.61.

| Season | Matched days | Break-even cost ratio |
| --- | ---: | ---: |
| Winter (Dec–Feb) | 477 | 6.18 |
| Spring (Mar–May) | 541 | 5.87 |
| Summer (Jun–Aug) | 540 | 3.57 |
| Autumn (Sep–Nov) | 483 | 3.48 |

For example, if an excess commitment cost four times as much per unit as an unmet request, conservative planning would have cost less in summer and autumn. The original flow forecasts describe water remaining at the downstream gauge after actual diversions. Here they supply a common reference for comparing policies. The replay uses withdrawals known after the fact, assumes they were requested in full at decision time, and measures simulated outcomes. Operating costs, advance demand estimates and pre-withdrawal flows would be needed for a utility planning trial.

---

### Next field test

A further monsoon with hourly barrage inflow, timestamped upstream readings and archived weather runs would allow the frozen model’s warnings, misses, false alarms and crest errors to be scored together. It would also allow a comparison with an operational forecast for the same target and issue time.

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

[10] Bihar Water Resources Department, historical barrage reports. https://www.fmiscwrdbihar.gov.in/fmis/gate.aspx

[11] USGS, Chesapeake Bay estimated streamflow methods and Potomac diversion adjustment. https://www.usgs.gov/centers/chesapeake-bay-activities/science/chesapeake-bay-estimated-streamflow-methods
