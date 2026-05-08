# EDA Plan — On-Time Performance Data

## Packages

### Install required
```
pip install pandas pyarrow numpy matplotlib seaborn plotly hdbscan scikit-learn jupyterlab
```

| Package | Purpose |
|---|---|
| `pandas` | core dataframes, groupbys, aggregations |
| `pyarrow` | parquet read/write |
| `numpy` | numerical operations |
| `matplotlib` | base plotting |
| `seaborn` | statistical charts (distributions, heatmaps) |
| `plotly` | interactive charts in notebook |
| `hdbscan` | clustering for route analysis (Section 10) |
| `scikit-learn` | preprocessing and scaling before HDBSCAN |
| `jupyterlab` | notebook environment |

Standard library (no install): `zipfile`, `glob`, `pathlib`, `os`

---

## File Locations

### Data
| File | Path |
|---|---|
| Raw zip files (source, do not modify) | `data/raw/zips/ontime_YYYY_MM.zip` |
| DMV-filtered parquet (main working dataset) | `data/processed/ontime_dmv.parquet` |
| Route-level features for HDBSCAN | `data/processed/route_features.parquet` |
| Any exports for visualizations | `data/exports/` |

### Code
| File | Path |
|---|---|
| Data download script | `src/ingestion/ontime_download.py` |
| Load + filter zips → parquet | `src/processing/build_ontime_dmv.py` |
| EDA helper functions (reusable transforms, groupbys) | `src/eda/helpers.py` |
| Route feature builder (input to HDBSCAN) | `src/eda/build_route_features.py` |

### Notebooks
| File | Path |
|---|---|
| Main EDA notebook | `notebooks/01_eda.ipynb` |

The `.py` files in `src/` hold the heavy logic (extraction, filtering, feature building) so the
notebook stays readable. The notebook imports from `src/eda/helpers.py` for transforms and calls
`src/processing/build_ontime_dmv.py` and `src/eda/build_route_features.py` to produce the parquets.
Run those scripts once to generate the parquets, then do all exploration in the notebook.

---

## 0. Setup and Load
- Zips live in data/raw/zips/ — do not extract to disk, read directly with zipfile + pandas
- Loop over zips, read each CSV, filter to Origin in ['IAD', 'DCA', 'BWI'] inside the loop
  before appending to list — do NOT concat first then filter or you will OOM
- pd.concat the filtered list into a single dataframe (this is a vertical stack, not a relational join)
- Save concatenated parquet to data/processed/ontime_dmv.parquet
- Check shape — how many rows, how many columns
- Print column names and dtypes
- NOTE: actual column names are CamelCase throughout (FlightDate, ArrDelay, Origin, etc.)
  not ALL_CAPS — see column list below in Section 2

## 1. Basic Data Quality
- Null counts per column — especially delay cause columns (CarrierDelay,
  WeatherDelay, NASDelay, SecurityDelay, LateAircraftDelay)
- Are nulls in delay cause columns only present for non-delayed flights?
  Or are there genuinely missing values?
- Check for duplicate rows
- Verify FlightDate range covers 2015-01 through 2026-01 with no unexpected gaps
- Check Month and DayOfWeek distributions look correct

## 2. Filter to Three Airports
- Filtering happens inside the load loop (see Section 0) — by this point the parquet is already DMV-only
- Column name reference (CamelCase, not ALL_CAPS):
  Month, DayOfWeek, FlightDate, Reporting_Airline, Flight_Number_Reporting_Airline,
  Origin, OriginCityName, OriginStateName, Dest, DestCityName, DestState,
  CRSDepTime, DepTime, DepDelay, DepDelayMinutes, TaxiOut,
  CRSArrTime, ArrTime, ArrDelay, ArrDelayMinutes, TaxiIn,
  Cancelled, CancellationCode, Diverted,
  CRSElapsedTime, ActualElapsedTime, AirTime, Distance,
  CarrierDelay, WeatherDelay, NASDelay, SecurityDelay, LateAircraftDelay
- Check row counts per airport — are they roughly what you'd expect?
- This parquet is the working dataset for everything downstream

## 3. Flight Volume
- Total flights per airport per year — first look at the COVID dip (2020-2021)
- Total flights per airport per month — seasonality shape
- Are all 12 months present for every year at every airport? (2015 through 2026-01)
- Flag any months with suspiciously low counts

## 4. Airline Coverage
- Which carriers operate at each airport?
- Market share by carrier per airport (flight count basis)
- Has carrier mix changed over the 2015-2024 period?
- Confirm Southwest (WN) appears at BWI but not IAD or DCA
- Confirm United (UA) dominance at IAD
- Confirm American (AA) dominance at DCA

## 5. Route Coverage
- Unique destination count per airport
- Top 20 destinations by flight frequency per airport
- Which destinations are served by all three airports?
  (This determines Part 4 — same destination three airports)
- Which destinations are international? Domestic?
- Are there routes with very thin volume that should be excluded from
  certain analyses?

## 6. Delay Profile
- Overall on-time rate per airport (ArrDel15 = 0, column is present in raw PREZIP files)
- Average ARR_DELAY per airport — mean and median
- Distribution shape of ARR_DELAY — confirm right skew
- On-time rate by carrier per airport
- On-time rate by month (seasonality) per airport
- On-time rate by day of week per airport
- On-time rate by departure time block per airport
- Are morning flights actually more reliable?

## 7. Delay Cause Breakdown
- What % of delayed flights have each cause attributed?
- Null rate in delay cause columns for delayed vs non-delayed flights
- Are weather delays underreported? (flag for NOAA integration later)
- Which carrier has highest carrier delay rate at each airport?
- Which routes have worst NAS delay rates?

## 8. Cancellations and Diversions
- Cancellation rate per airport per year
- Cancellation code breakdown (A=carrier, B=weather, C=NAS, D=security)
- Did COVID show up as cancellation spike? One annotation, move on
- Diversion rate per airport — is it meaningful or negligible?

## 9. Taxi Times
- Average TAXI_OUT per airport — IAD notorious for this
- Average TAXI_IN per airport
- Do taxi times correlate with time of day or season?
- Does TAXI_OUT explain part of IAD's delay reputation?

## 10. Route-Level Features for HDBSCAN
- For each origin-destination pair compute:
  - Mean ARR_DELAY
  - On-time rate
  - Flight frequency
  - Cancellation rate
  - Seasonal variance (std of monthly on-time rate)
  - Primary carrier (most frequent)
  - Average distance
- Save as data/processed/route_features.parquet
- This is the direct input to the HDBSCAN model later

## 11. Shared Destination Candidates (Part 4)
- Find all destinations served by at least two of the three airports
- For each shared destination count flights per airport
- Flag destinations with enough volume for statistically honest comparison
  (suggest minimum 500 flights per airport per year as threshold)
- Shortlist 6-8 candidates for Part 4 — LHR, LAX, ORD, MIA, etc.
- Note which require connections from DCA due to perimeter rule

## 12. Export Notes for Visualizations
- Which routes go on the CesiumJS globe? All of them or frequency threshold?
- What coordinate data do you need? Airport lat/lon lookup table
- Flag any data quality issues discovered that affect specific visualizations
- Document anything surprising found during EDA in decisions.md