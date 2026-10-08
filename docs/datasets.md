# Dataset acquisition and compatibility

Checked on 8 October 2026. Download status is separate from modelling
suitability. The four original candidate sources come from section 6.2 of
the supplied proposal. USGS was added with the user's approval for streamflow
forecasting. Checksums and exact saved paths appear in [the manifest](../data/manifest.json).

| Source | Download status | Forecasting suitability |
| --- | --- | --- |
| Webb et al. (2025) | Downloaded ZIP, including Table S2.xlsx | Wetland study-level extraction, not a daily flow sequence |
| Anderson et al. (2024) | Publisher files blocked by a human-verification page | Literature synthesis; associated Old Woman Creek data require a separate audit |
| UEA / Cooper (2020), Ingol and Mun | File located; download returned HTTP 403 and browser attempts did not save it | Sparse monthly water-quality observations |
| Dykes et al. (2025) | Paper downloaded locally; underlying observations available on request | Seasonal wetland case study; raw records not obtained |
| USGS 01646500 | Downloaded and validated | Daily mean streamflow for the initial next-day benchmark |

## Webb

[Article](https://www.mdpi.com/2073-4441/17/22/3301) and
[supporting materials](https://www.mdpi.com/article/10.3390/w17223301/s1).
The archive was downloaded through the publisher's browser interface after
direct requests failed. It contains Figures S1–S3, Table S1 and Table S2.xlsx.
The original workbook is preserved. Its used range is 230 rows × 105 columns,
including two heading rows and a legend area; this is not a claim of 228
independent usable wetlands. It includes monitoring, phosphorus, flow,
wetland-design and management fields. No daily sequence was manufactured
from summary records.

Attribution: Webb, C. J., van Biervliet, O., Wood, K. A., Roberts, D. and
Wake, H. (2025), *Phosphorus Removal in Constructed Treatment Wetlands:
A Systematic Review*, Water 17(22), 3301, DOI 10.3390/w17223301.
The publisher identifies the article as [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
The archive and extracted workbook are unchanged; check any separate
third-party notices before reusing individual content.

## Anderson

[Article and availability statement](https://www.sciencedirect.com/science/article/pii/S1470160X24014262).
The paper states that the literature-synthesis data and resampling code are
supplements. It also cites McMurray et al. (2024),
[Old Woman Creek data](https://doi.org/10.6073/pasta/3f251395d82eafb33a93a9f3ebfb858c),
EDI package `edi.1810.1`. The publisher and EDI portal presented human
verification; the EDI metadata service returned HTTP 403. No files from
these sources have been represented as downloaded. Their data overlap,
licensing, sampling interval and discharge fields remain unverified.

## UEA / Cooper

[Catalogue](https://research-portal.uea.ac.uk/en/datasets/integrated-constructed-wetlands-icw-water-quality-data-for-the-ri/)
and [linked Wetland_Data.csv](https://research-portal.uea.ac.uk/files/197849717/Wetland_Data.csv).
The catalogue describes manual monthly grab sampling from 5 February to
19 September 2019. Its file listing is 6.42 KB. The catalogue is accessible,
but the CSV download did not succeed in this session. File contents and
reuse terms remain unaudited. The proposal identifies the related study's
phosphorus measurement as phosphate, requiring separate treatment from
total phosphorus.

## Dykes

[Paper](https://doi.org/10.1016/j.jwpe.2025.107350) and
[university-hosted PDF](https://wrap.warwick.ac.uk/id/eprint/190387/1/1-s2.0-S2214714425004222-main.pdf).
The downloaded paper's page 16 confirms that data will be made available
on request. The paper also mentions supplementary material, but the raw
observations have not been acquired. No author has been contacted. The
paper PDF is stored locally as reference material and is not a dataset.

## USGS streamflow

Station **01646500**, Potomac River near Washington, DC, Little Falls Pump
Station. The response contains 13,149 daily mean discharge observations
from 1 January 1990 through 31 December 2025, parameter `00060`, statistic
`00003`. All observations carry the approved `A` qualifier; 174 also carry
the estimated `e` qualifier. Estimated records are retained and flagged.
The series is not claimed to be an unregulated or naturalized catchment.

The archived JSON preserves the returned source values and qualifiers.
Preprocessing converts ft³/s to m³/s using 0.028316846592, rejects unapproved,
negative, nonfinite and sentinel values, and rejects duplicate dates.
Window generation skips missing values or gaps instead of interpolating.
This run has complete usable daily coverage. Revisions after retrieval may
change later downloads, so the response checksum is retained.

[USGS station](https://waterdata.usgs.gov/monitoring-location/USGS-01646500/)
and [USGS data licensing](https://www.usgs.gov/data-management/data-licensing).
Source: U.S. Geological Survey, National Water Information System daily
values, retrieved 8 October 2026. Federal USGS-produced data are generally
public domain; retain attribution and review source-specific notices.

## Completing the outstanding downloads

Use the linked public pages to obtain the Anderson supplements and the UEA
CSV when verification or file access is available. Store original files
under the corresponding `data/raw` folder, record their checksums and inspect
their fields before modelling. Request Dykes' raw observations through an
explicitly authorized author communication. Wetland and streamflow records
must remain separate unless a scientifically compatible integration is
established.
