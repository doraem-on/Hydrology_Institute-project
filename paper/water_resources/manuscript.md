# When does a river forecast change a decision?
## Flood warning at Gandak Barrage and water allocation on the Potomac

### Abstract

We replayed two decisions using river and weather records. On the Gandak, three models signalled the September 2026 rise in barrage inflow six hours ahead, one hour after downstream Khadda had already reached its warning level. We then forecast Khadda’s water level directly. Across three test monsoons in 2024–2026, adding upstream Triveni readings gave advance warning for 24 of 26 qualifying crossings of 95 m, compared with 15 using the town gauge alone. For the 14 crossings both caught, the median gain was 4.5 hours. False alert hours increased from 49 to 68. On ten matched next-day forecasts, Bihar’s official bulletins had a mean absolute stage error of 9 cm, compared with 11 cm for the upstream model. On the Potomac, we forecast next-day water use and compared it with reconstructed municipal withdrawals on 2,041 days. Mean absolute demand error was 34% lower than using the historical average. Conservative planning cut overcommitment from 36.6% to 1.0% of days while leaving another 98,699 m³/day of demand unmet. Both cases measure what the decision gains and what it costs.

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

### Would a different model warn sooner?

We compared the combined ridge regression with a random forest and gradient boosting. Each model used the same barrage, gauge and rainfall inputs, training cutoff and 1–24 hour forecast horizons. We fixed the tree settings before this comparison and already knew the September event. At 15:00 IST on 25 September, the highest flows predicted for the next 24 hours were 4,803, 4,904 and 4,663 m³/s respectively. One hour later they were 5,100, 5,359 and 5,045 m³/s. All three crossed the 5,022 m³/s signal threshold together. Each gave six hours of advance warning at the barrage, and each first signalled one hour after Khadda reached its local warning level.

Across 739 eligible barrage decisions, each model signalled on six hours and had zero false alert hours. Carrying the latest reading forward gave no advance warning. At 24 hours, mean absolute flow errors were 896 m³/s for ridge, 770 for random forest, 784 for gradient boosting and 749 for the last reading. The smaller average errors of the tree models did not yield an earlier warning in this flood.

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

### How much warning did the upstream gauge add at Khadda?

The barrage replay forecast inflow at a different location. Here we forecast water level at the town itself. We extracted June–October hourly readings from CWC [6] for Khadda and upstream Triveni, near the barrage. The archive starts in August 2023 and ends in October 2026. For each test season from 2024 to 2026, we trained only on earlier seasons, using the same examples for both models. At each hourly decision, a ridge regression used Khadda’s latest level and its changes over 1–24 hours. A second regression added the same measurements at Triveni. We assumed a one-hour gauge reporting delay at both stations. Historical release and revision times are unknown.

A warning predicted that Khadda would reach 95 m within the next 24 hours. A new crossing required a full preceding day below 95 m. Individual crossings can occur during the same monsoon flood. The 2023 training record supplied eight such crossings. There were six assessable crossings in 2024, eight in 2025 and twelve in 2026.

| Town warning at 95 m | Khadda only | Khadda and Triveni |
| --- | ---: | ---: |
| Crossings warned / 26 | 15 | 24 |
| Missed crossings | 11 | 2 |
| False alert hours / 6,114 eligible hours | 49 | 68 |
| Runs of consecutive false alert hours | 30 | 28 |

Both models warned for 14 crossings. Adding Triveni was earlier on 11, tied on two, and later on one. The median gain was 4.5 hours, ranging from 12 hours later to 20 hours earlier. Triveni caught ten crossings the local model missed and lost one the local model caught. On 25 September 2026, the upstream model signalled at 07:00 IST and the local model at 14:00, before the town reached 95 m at 15:00. Residents’ first receipt time remains unknown.

At the higher 96 m danger level, the upstream model warned for all four assessable crossings and the local model warned for three. Neither produced a false danger-alert hour in this sample. Four crossings give limited evidence about rare events.

---

### Official forecasts, rain and gauge failures

We verified ten dated Bihar Water Resources Department bulletins [15] against the same Khadda observation and our two models at exactly the same 24-hour lead. Each 15:00 IST bulletin gave a water level for 15:00 the next day. Mean absolute errors were 9.0 cm for the official product, 11.2 cm with Triveni, and 13.3 cm with Khadda alone. The one matched observation at or above 95 m was 96.00 m on 27 September 2026. All three forecasts exceeded 95 m, but fell below 96 m. The official forecast was 95.99 m. None forecast a high level on the other nine dates. This sparse set measures stage accuracy at specified hours. It cannot establish the first public alert across all 26 crossings.

The CWC advisory dated 3 July 2024 listed severe conditions at Khadda for 6 July [16]. The town reached 96 m at 22:00 IST on 6 July. The upstream model first signalled that day at 15:00 and the local model at 18:00. In that case the published advisory identified the danger days earlier. It covered seven days, while our models forecast up to 24 hours ahead.

Could forecast rainfall add more time? The archived weather runs covered part of 2026. We trained all three variants on the same portion of that season before 16 September, then scored the remaining hours. Adding forecast rain to the two gauges gave the same eight hours of warning for the one 95 m crossing and the same 14 hours for the one 96 m crossing. Both variants produced four false warning-level hours and one false danger-level hour. This smaller weather comparison used different training dates from the three-season experiment.

We also simulated six hours of upstream sensor failure every seventh day during the monsoon. If the gauge stopped reporting, the system used the town-only model until upstream history was complete again. If it silently repeated its last value, the system continued forecasting with that reading. Both scenarios warned for 23 of 26 crossings at 95 m, against 24 with intact records. These tests measure a consequence of faulty data. A governance study would also need timestamped records of who issued a warning, how it was delivered and when communities received it.

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

For example, if an excess commitment cost four times as much per unit as an unmet request, conservative planning would have cost less in summer and autumn. The original flow forecasts describe water remaining at the downstream gauge after actual diversions. Here they supply a common reference for comparing policies. The replay uses withdrawals known after the fact, assumes they were requested in full at decision time, and measures simulated outcomes. The following replay estimates demand in advance. A utility trial would also need actual requests, operating costs and pre-withdrawal flows.

---

### Replaying the two decisions with the outcomes hidden

For the Gandak we used Khadda, a downstream gauge with published warning and danger levels of 95.0 and 96.0 m [12]. At each issue hour we used the saved model to predict the highest barrage inflow over the next 24 hours. The signal turned on when that forecast reached the existing 5,022 m³/s threshold. The comparison rule used the latest barrage reading against the same threshold. We then looked up the town’s hourly stage [6]. The archive lacks real-time publication timestamps for the barrage readings. Times below are IST and refer to first recorded threshold attainment.

| Khadda in September 2026 | First recorded crossing | When the model signalled |
| --- | ---: | ---: |
| Warning level, 95 m | 25 Sep, 15:00 | 1 hour after |
| Danger level, 96 m | 27 Sep, 15:00 | 47 hours before |

The first model signal was at 16:00 on 25 September. Waiting for the barrage reading itself gave a signal at 22:00, seven hours after Khadda’s warning level and 41 hours before its danger level. The 47-hour interval is elapsed time between the model signal and the observed crossing. The model forecast barrage inflow only. As a test of next-day town warnings, both rules missed the one 95 m onset and both signalled within the 24 hours before the one 96 m onset. Of 51 positive model decision hours below 96 m, 29 had no danger crossing in the next 24 hours. Repeated decisions can belong to one episode.

What did residents hear? A report published at 15:18 on 25 September described a departmental high alert already in effect [13]. A local report updated at 14:51 on 26 September documented loudspeaker warnings in Khadda-area villages, 24 hours and 9 minutes before the gauge first recorded danger level [14]. Neither identifies when the first resident received a warning. No public alert was issued by this research model.

### How much water would we have promised tomorrow?

For each day in 2020–2025 we forecast withdrawals using only the target date’s position in the year and its weekday. The model was fitted once to 3,519 eligible days from 2010 through October 2019. We left a two-month buffer for monthly reporting and used the training-period mean as a constant-demand baseline. The experiment uses the archived previous day’s flow as available when planning. Historical publication and revision times for individual flow readings are unknown. Both demand rules produced 2,192 forecasts, with 2,041 eligible withdrawals for verification. Mean absolute error fell from 161,038 to 106,378 m³/day. The calendar forecast overestimated use by 38,185 m³/day on average.

---

### What did forecasting demand change?

Each policy promised the smaller of predicted demand and its forecast supply budget. Only after fixing the promise did we reveal observed flow and withdrawals. Delivery was limited by the promise, actual supply and actual use. The following comparison holds the demand forecast fixed across all three ways to estimate tomorrow’s flow.

| Supply estimate | Days overcommitted | Mean unmet use (m³/day) |
| --- | ---: | ---: |
| Previous day’s flow | 32.5% | 412,318 |
| Ensemble mean | 36.6% | 408,333 |
| Ensemble fifth percentile | 1.0% | 507,033 |

Compared with the ensemble mean, the conservative rule avoided 26,063 m³/day of excess commitments while leaving an extra 98,699 m³/day unmet. The break-even unit-cost ratio was 3.79 with forecast demand, compared with 4.01 when the replay was given realized withdrawals in advance. The previous-day flow rule also overcommitted less often than the mean ensemble, at the cost of slightly higher unmet use. All three use the same simulated reserve and diversion cap.

For a dated example, on 10 November 2026 a refit using the available approved archive gave a next-day withdrawal estimate of 1.27 million m³ for 11 November. The latest usable training observation was 29 September 2025. The estimate reflects expected seasonal use. Unusual local conditions can produce larger errors, and the target day was unobserved when this paper was prepared.

### Next field test

A further monsoon with hourly barrage inflow, timestamped upstream readings and archived weather runs would allow the frozen model’s warnings, misses, false alarms and crest errors to be scored together. A continuous archive of operational forecasts and delivery receipts would extend the ten matched Khadda bulletins to a test of warning delivery across a full season.

---

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

[12] Bihar Water Resources Department. Gandak gauge forecast bulletin, 2 June 2026. https://www.fmiscwrdbihar.gov.in/bulletin/Gandak_Model_Result.pdf

[13] Dainik Jagran, Kushinagar, 25 September 2026. Departmental alert for the Gandak. https://www.jagran.com/uttar-pradesh/kushinagar-kushinagar-on-high-alert-gandak-river-flood-threat-from-nepal-rains-40384752.html

[14] Amar Ujala, Kushinagar, 26 September 2026. Loudspeaker warnings in Khadda-area villages. https://www.amarujala.com/uttar-pradesh/kushinagar/narayani-river-surging-alert-issued-for-embankments-flood-threat-to-a-dozen-villages-in-khadda-2026-09-26

[15] Bihar WRD, FMIS daily water level and flood forecasts, dated bulletins. https://www.fmiscwrdbihar.gov.in/bulletin/

[16] Central Water Commission, Daily Flood Situation Report cum Advisories, 3 July 2024. https://cwc.gov.in/sites/default/files/dfsitrepca-03.07.2024.pdf
