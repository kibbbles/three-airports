# Modeling Plan — three-airports (09_modeling.ipynb)

## Objective

EDA told us what the numbers are. This notebook finds structure beneath
the numbers that groupbys cannot surface. Four model families, each
serving a distinct section of the blog narrative. Every model produces
a clean export to `data/exports/` that the frontend consumes directly.

---

## Packages

```
pip install hdbscan umap-learn pygam mapie prophet scikit-learn plotly
```

| Package | Purpose |
|---|---|
| `hdbscan` | density-based route clustering |
| `umap-learn` | 3D dimensionality reduction for cluster visualization |
| `pygam` | Generalized Additive Model for delay prediction |
| `mapie` | conformal prediction uncertainty bands for Prophet |
| `prophet` | time series forecasting of volume and delay rate |
| `scikit-learn` | preprocessing, train/test split, Isolation Forest |
| `plotly` | all interactive visualizations and 3D scatter |

---

## Source Data

| File | Path | Notes |
|---|---|---|
| Main flight-level dataset | `data/processed/flights_featured.parquet` | 2.8M rows, 53 cols |
| International T-100 | `data/processed/t100_intl_dmv.parquet` | for globe only, not modeling |

All modeling uses `operated` subset (Cancelled == 0) unless stated otherwise.

---

## Exports (what the frontend consumes)

| File | Section produced | Used in blog |
|---|---|---|
| `data/exports/route_clusters_3d.html` | Section 2 | Part 7 — cluster scatter |
| `data/exports/route_clusters.parquet` | Section 2 | globe anomaly layer |
| `data/exports/prophet_forecasts.parquet` | Section 3 | Part 4 — time series |
| `data/exports/gam_partials.parquet` | Section 4 | Part 5 — delay curves |
| `data/exports/anomalous_routes.parquet` | Section 5 | globe red layer |

---

## Section 1 — Route Feature Engineering

**Goal:** Build one row per origin-destination pair summarizing its
full performance profile. This is the input matrix for HDBSCAN.

**Steps:**

```python
# Base aggregation — no outer-scope lambdas, no computed ratios
route_features = operated.groupby(['Origin', 'Dest']).agg(
    mean_arr_delay   = ('ArrDelayMinutes',   'mean'),
    median_arr_delay = ('ArrDelayMinutes',   'median'),
    late_rate        = ('is_late',           'mean'),
    flight_freq      = ('is_late',           'count'),
    mean_taxi_out    = ('TaxiOut',           'mean'),
    mean_distance    = ('Distance',          'mean'),
    carrier_share    = ('t100_carrier_share','mean'),
    mean_fare        = ('db1b_avg_fare',     'mean'),
    wx_ts_rate       = ('wx_had_ts',         'mean'),
    nas_minutes      = ('NASDelay',          'sum'),
    weather_minutes  = ('WeatherDelay',      'sum'),
    pos_delay_min    = ('ArrDelayMinutes',   lambda x: x[x > 0].sum()),
).reset_index()

# Delay-cause shares — post-agg to avoid division-by-zero on early arrivals
route_features['nas_share']     = (route_features['nas_minutes']
                                    / route_features['pos_delay_min'].replace(0, np.nan))
route_features['weather_share'] = (route_features['weather_minutes']
                                    / route_features['pos_delay_min'].replace(0, np.nan))
route_features = route_features.drop(columns=['nas_minutes', 'weather_minutes', 'pos_delay_min'])

# cancel_rate — must come from feat (full dataset); operated has Cancelled=0 always
cancel_by_route = (
    feat.groupby(['Origin', 'Dest'])['Cancelled']
    .mean()
    .reset_index()
    .rename(columns={'Cancelled': 'cancel_rate'})
)
route_features = route_features.merge(cancel_by_route, on=['Origin', 'Dest'], how='left')

# seasonal_variance — explicit groupby avoids outer-scope reference
# routes with only one season represented return NaN std and are dropped below
seasonal_var = (
    operated.groupby(['Origin', 'Dest', 'season'])['is_late']
    .mean()
    .reset_index()
    .groupby(['Origin', 'Dest'])['is_late']
    .std()
    .reset_index()
    .rename(columns={'is_late': 'seasonal_variance'})
)
route_features = route_features.merge(seasonal_var, on=['Origin', 'Dest'], how='left')

# Apply frequency filter then drop any remaining nulls
route_features = (
    route_features[route_features['flight_freq'] > 200]
    .dropna()
    .reset_index(drop=True)
)
```

**Notes:**
- Drop routes with fewer than 200 total flights — too thin for stable
  cluster membership. Filter is applied after all merges.
- `cancel_rate` is joined from `feat` (not `operated`) because `operated`
  excludes cancelled flights, making its `Cancelled` column always 0.
- `seasonal_variance` captures routes that are reliable in some seasons
  but chaotic in others. Routes present in only one season get NaN std
  and are dropped by the final `dropna()`.
- `nas_share` and `weather_share` denominator is `ArrDelayMinutes > 0`
  only — early arrivals (negative values) are excluded to prevent
  distorting the denominator.
- Save as `data/processed/route_features.parquet` before scaling.
  Always preserve the unscaled version — scaling is done in-memory only.

**Checks to run:**
- Print shape and null counts — should be zero nulls after dropna
- Print descriptive stats on each feature
- Verify `flight_freq` distribution — flag if p50 is below 500

---

## Section 2 — HDBSCAN Route Clustering + 3D UMAP

**Goal:** Find natural groupings of DMV routes based on their combined
performance profile. Name clusters based on what the data shows, not
what you assumed going in.

**Key principle:** Run HDBSCAN on scaled original features. Use UMAP
purely for visualization. Do not cluster on UMAP coordinates — UMAP
distorts distances in ways that mislead density-based methods.

**Steps:**

```python
from sklearn.preprocessing import StandardScaler
import hdbscan
import umap
import plotly.express as px

# 1. Scale features
feature_cols = [
    'mean_arr_delay', 'late_rate', 'cancel_rate', 'flight_freq',
    'mean_taxi_out', 'mean_distance', 'carrier_share', 'mean_fare',
    'wx_ts_rate', 'nas_share', 'weather_share', 'seasonal_variance'
]
scaler = StandardScaler()
scaled = scaler.fit_transform(route_features[feature_cols])

# 2. HDBSCAN on scaled features
clusterer = hdbscan.HDBSCAN(
    min_cluster_size=5,
    min_samples=3,
    metric='euclidean'
)
route_features['cluster'] = clusterer.fit_predict(scaled)
route_features['cluster_prob'] = clusterer.probabilities_

# 3. UMAP to 3D for visualization only
reducer = umap.UMAP(n_components=3, random_state=42, n_neighbors=15)
embedding = reducer.fit_transform(scaled)
route_features['umap_x'] = embedding[:, 0]
route_features['umap_y'] = embedding[:, 1]
route_features['umap_z'] = embedding[:, 2]

# 4. 3D scatter — the centerpiece visual
# Cast cluster to string so Plotly uses a discrete color palette,
# not a continuous scale (which makes adjacent cluster integers
# appear as nearly identical shades).
route_features['cluster_label'] = (
    route_features['cluster'].astype(str).replace('-1', 'Noise')
)
fig = px.scatter_3d(
    route_features,
    x='umap_x', y='umap_y', z='umap_z',
    color='cluster_label',
    size='flight_freq',
    hover_data=['Origin', 'Dest', 'mean_fare', 'late_rate',
                'mean_distance', 'carrier_share'],
    title='DMV Route Clusters — UMAP 3D (HDBSCAN labels)',
    color_discrete_sequence=px.colors.qualitative.Bold,
)
fig.write_html('data/exports/route_clusters_3d.html')
```

**Hyperparameter sweep:**
Try `min_cluster_size` in [5, 8, 10, 15] and `min_samples` in [2, 3, 5].
For each combination print: number of clusters, noise point fraction,
mean cluster size. Pick the run that produces 4-7 clusters with less
than 20% noise points and meaningful size variation between clusters.
Document chosen parameters in `knowledge/decisions.md`.

**Cluster interpretation — do this for every cluster:**
```python
cluster_profiles = (
    route_features.groupby('cluster')[feature_cols]
    .mean()
    .round(3)
    .sort_values('late_rate', ascending=False)
)
print(cluster_profiles)
```
Read the profile table and give each cluster a descriptive name.
Examples of what you might find (do not assume — let data decide):
- "United mainline long-haul" — high distance, high fare, moderate NAS share
- "Southwest leisure BWI" — high frequency, low fare, high cancel_rate
- "Short-hop northeast contested" — low distance, low fare, high late_rate
- "Thin monopoly routes" — low freq, high carrier_share, high fare
- Noise points (-1) — routes that don't fit any cluster, worth examining

Add a markdown cell naming each cluster with a one-sentence rationale
based on the profile table. These names go directly into the blog narrative.

**Checks to run:**
- What fraction of routes are noise (-1)? Over 30% means parameters too strict.
- Are all three airports represented across clusters or are clusters
  airport-specific? Airport-specific clusters are less interesting.
- Do any clusters contain only one origin airport? Flag and investigate.

**Export:**
```python
route_features.to_parquet('data/exports/route_clusters.parquet', index=False)
```

---

## Section 3 — Prophet Time Series Forecasting

**Goal:** Quantify what normal DMV flight performance looked like
pre-COVID, forecast what recovery should have looked like, and measure
the gap between forecast and actual in 2022-2026. The gap is the
evidence for systemic post-COVID operational degradation.

**Two targets per airport (six Prophet models total):**
- Monthly flight volume (operated flight count)
- Monthly late rate (fraction of operated flights that were late)

**Steps:**

```python
from prophet import Prophet
from mapie.regression import MapieRegressor
import pandas as pd

monthly = (
    operated
    .assign(month=operated['FlightDate'].dt.to_period('M'))
    .groupby(['Origin', 'month'])
    .agg(
        flights   = ('is_late', 'count'),
        late_rate = ('is_late', 'mean')
    )
    .reset_index()
)
monthly['ds'] = monthly['month'].dt.to_timestamp()

forecasts = []
for airport in ['IAD', 'DCA', 'BWI']:
    for target in ['flights', 'late_rate']:
        df_ap = (
            monthly[monthly['Origin'] == airport][['ds', target]]
            .rename(columns={target: 'y'})
        )

        # Train on pre-COVID only (2015-2019) to get clean baseline
        train = df_ap[df_ap['ds'] < '2020-01-01']
        
        m = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=False,  # monthly data, weekly irrelevant
            daily_seasonality=False,
            changepoint_prior_scale=0.05  # conservative — don't overfit
        )
        m.fit(train)

        # Forecast through 2026
        future = m.make_future_dataframe(periods=84, freq='MS')
        forecast = m.predict(future)
        forecast['Origin'] = airport
        forecast['target'] = target
        
        # Join actual values
        forecast = forecast.merge(df_ap, on='ds', how='left')
        forecasts.append(forecast)

all_forecasts = pd.concat(forecasts, ignore_index=True)
all_forecasts.to_parquet('data/exports/prophet_forecasts.parquet', index=False)
```

**Conformal prediction for honest uncertainty bands:**
```python
# After fitting each Prophet model, compute empirical coverage
# on 2015-2019 holdout fold rather than trusting Prophet's
# Gaussian uncertainty assumption
# Use MAPIE to wrap the Prophet point forecast with
# distribution-free prediction intervals
# See: https://mapie.readthedocs.io for implementation
```

Note: Full MAPIE integration with Prophet requires wrapping Prophet's
predict output as a sklearn-compatible estimator. Document the approach
in `knowledge/decisions.md` and implement if time allows. If it adds
more than 2 days of implementation work, Prophet's native intervals
are acceptable with a written caveat in the blog post.

**Key finding to surface:**
For each airport compute the gap between forecasted and actual late_rate
in 2023, 2024, 2025:
```python
# Note: future forecast rows have no actual y — dropna removes them
# so the mean is only over months where actual data exists.
# Derive year inside the chain to avoid referencing the unfiltered
# all_forecasts DataFrame from the outer scope (which would break
# after the target filter).
gap = (
    all_forecasts[all_forecasts['target'] == 'late_rate']
    .assign(gap=lambda x: x['y'] - x['yhat'],
            year=lambda x: x['ds'].dt.year)
    .dropna(subset=['gap'])
    .groupby(['Origin', 'year'])['gap']
    .mean()
    .reset_index()
)
print(gap[gap['year'] >= 2022].to_string())
```
A positive gap means actual late_rate was worse than the pre-COVID
trend would have forecast. This number, per airport per year, is
your headline finding for the NAS crisis section.

**Checks to run:**
- Plot train vs forecast vs actual for each of the six models visually
  before exporting. Sanity check that COVID shows up as a massive dip
  below forecast, not as something the model predicted.
- Check changepoints detected — do they land near March 2020? If not,
  adjust `changepoint_prior_scale`.

---

## Section 4 — GAM Delay Predictor

**Goal:** Fit a Generalized Additive Model that predicts late probability
from weather, time, and operational features. Produce smooth partial
dependence curves showing exactly how each variable affects delay risk.
These curves go directly in the blog as clean interpretable visuals.

**Why GAM over logistic regression:** GAM fits smooth nonlinear functions
to each predictor rather than assuming linearity. The visibility-to-delay
relationship is not linear — there's a step change at IFR threshold that
a logistic regression would smooth over but a GAM captures correctly.

**Why GAM over XGBoost/Random Forest:** You already used tree models in
Kabe's Maybes. GAM is interpretable by construction — no SHAP needed,
the partial dependence IS the model. Each term is directly readable.

**Steps:**

```python
from pygam import LogisticGAM, s, f
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
import numpy as np

# Derive columns not guaranteed to be in flights_featured
gam_data = operated.copy()
gam_data['is_weekend'] = gam_data['FlightDate'].dt.dayofweek.isin([5, 6]).astype(int)

def _holiday_week(dt):
    m, d = dt.month, dt.day
    if m == 11 and d >= 20: return 1   # Thanksgiving week
    if m == 12 and d >= 23: return 1   # Christmas week
    if m == 1  and d <= 3:  return 1   # New Year's
    if m == 7  and d <= 7:  return 1   # July 4th week
    return 0

gam_data['is_holiday_week'] = gam_data['FlightDate'].apply(_holiday_week).astype(int)

# Select feature columns and drop rows with any null
gam_data = gam_data[[
    'is_late', 'Origin', 'season', 'dep_hour_bucket',
    'Reporting_Airline', 'Distance', 'wx_min_vis',
    'wx_had_ts', 'wx_had_snow', 'wx_had_fog',
    'is_weekend', 'is_holiday_week', 't100_carrier_share'
]].dropna()

# Encode categoricals as integer codes
for col in ['Origin', 'season', 'dep_hour_bucket', 'Reporting_Airline']:
    gam_data[col] = gam_data[col].astype('category').cat.codes

X = gam_data.drop('is_late', axis=1).values
y = gam_data['is_late'].values.astype(int)

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# Fit GAM — s() = smooth spline term, f() = factor/categorical term
gam = LogisticGAM(
    f(0) +   # Origin (categorical)
    f(1) +   # season (categorical)
    f(2) +   # dep_hour_bucket (categorical)
    f(3) +   # airline (categorical)
    s(4) +   # Distance (smooth)
    s(5) +   # wx_min_vis (smooth — will show IFR step)
    f(6) +   # wx_had_ts (binary)
    f(7) +   # wx_had_snow (binary)
    f(8) +   # wx_had_fog (binary)
    f(9) +   # is_weekend (binary)
    f(10) +  # is_holiday_week (binary)
    s(11)    # carrier_share (smooth)
).fit(X_train, y_train)

print(gam.summary())
print(f'Test AUC: {roc_auc_score(y_test, gam.predict_proba(X_test)):.3f}')
```

**Partial dependence export:**
```python
# Term indices correspond to position in the GAM formula above:
#   0=Origin  1=season  2=dep_hour_bucket  3=Reporting_Airline
#   4=Distance  5=wx_min_vis  6=wx_had_ts  7=wx_had_snow
#   8=wx_had_fog  9=is_weekend  10=is_holiday_week  11=t100_carrier_share
CONT_TERMS = {'Distance': 4, 'wx_min_vis': 5, 't100_carrier_share': 11}

partials = {}
for col, term_idx in CONT_TERMS.items():
    XX = gam.generate_X_grid(term=term_idx)
    pdep, confi = gam.partial_dependence(term=term_idx, X=XX, width=0.95)
    partials[col] = pd.DataFrame({
        'x':      XX[:, term_idx],
        'effect': pdep,
        'lower':  confi[:, 0],
        'upper':  confi[:, 1],
    })

pd.concat(partials).reset_index(level=0).rename(
    columns={'level_0': 'feature'}
).to_parquet('data/exports/gam_partials.parquet', index=False)
```

The visibility partial dependence curve is your clearest visual finding —
it will show a steep slope downward between 3 miles (IFR threshold)
and 1 mile (LIFR threshold), confirming and quantifying what EDA showed
in discrete buckets. That curve goes in the blog with one sentence of
explanation.

**Checks to run:**
- AUC on test set should be 0.65-0.75. Higher may indicate data leakage.
  Lower means the features genuinely don't predict well, which is itself
  an honest finding worth noting.
- `gam.summary()` prints p-values per term — flag any non-significant
  terms and consider removing them. A leaner model is more defensible.
- Check that `wx_min_vis` partial dependence shows the expected
  step-change shape. If it's flat, visibility isn't a significant
  predictor after controlling for others.

---

## Section 5 — Isolation Forest Anomaly Detection

**Goal:** Flag routes whose delay profile in 2023-2025 was statistically
anomalous relative to their own 2015-2019 baseline. These anomalous
routes are the granular evidence for the NAS staffing crisis narrative
and map directly onto the CesiumJS globe as a toggleable red layer.

**Key distinction from global outlier detection:** You're not looking
for routes that are always bad. You're looking for routes that got
significantly worse after 2022 relative to their own history.
Route-specific anomaly detection controls for the fact that
IAD-SFO is always going to have different base delay rates than DCA-BOS.

**Steps:**

```python
from sklearn.ensemble import IsolationForest
import numpy as np

# Build annual route-level summaries
# nas_share: post-agg ratio to avoid outer-scope lambda and division-by-zero
# cancel_rate: from feat (full dataset) — operated has Cancelled=0 always
annual_routes = (
    operated.assign(year=operated['FlightDate'].dt.year)
    .groupby(['Origin', 'Dest', 'year'])
    .agg(
        late_rate    = ('is_late',         'mean'),
        nas_minutes  = ('NASDelay',        'sum'),
        pos_delay    = ('ArrDelayMinutes', lambda x: x[x > 0].sum()),
        mean_delay   = ('ArrDelayMinutes', 'mean'),
        n_flights    = ('is_late',         'count'),
    )
    .reset_index()
)
annual_routes['nas_share'] = (annual_routes['nas_minutes']
                               / annual_routes['pos_delay'].replace(0, np.nan))
annual_routes = annual_routes.drop(columns=['nas_minutes', 'pos_delay'])

cancel_annual = (
    feat.assign(year=feat['FlightDate'].dt.year)
    .groupby(['Origin', 'Dest', 'year'])['Cancelled']
    .mean()
    .reset_index()
    .rename(columns={'Cancelled': 'cancel_rate'})
)
annual_routes = (
    annual_routes
    .merge(cancel_annual, on=['Origin', 'Dest', 'year'], how='left')
    .dropna()
)

anomalous_routes = []

for (origin, dest), grp in annual_routes.groupby(['Origin', 'Dest']):
    if len(grp) < 5:
        continue  # need enough years for meaningful baseline

    baseline = grp[grp['year'] <= 2019]
    recent   = grp[grp['year'] >= 2022]
    
    if len(baseline) < 3 or len(recent) < 1:
        continue

    features = ['late_rate', 'nas_share', 'cancel_rate', 'mean_delay']
    
    clf = IsolationForest(contamination=0.1, random_state=42)
    clf.fit(baseline[features])
    
    scores = clf.decision_function(recent[features])
    recent = recent.copy()
    recent['anomaly_score'] = scores
    recent['is_anomalous'] = (scores < 0).astype(int)
    recent['Origin'] = origin
    recent['Dest'] = dest
    anomalous_routes.append(recent)

anomaly_df = pd.concat(anomalous_routes, ignore_index=True)

# Routes anomalous in 2+ recent years are the most meaningful signal
persistent = (
    anomaly_df[anomaly_df['year'] >= 2022]
    .groupby(['Origin', 'Dest'])['is_anomalous']
    .sum()
    .reset_index()
    .rename(columns={'is_anomalous': 'anomalous_years'})
    .query('anomalous_years >= 2')
    .sort_values('anomalous_years', ascending=False)
)

print(f'Routes persistently anomalous post-2022: {len(persistent)}')
print(persistent.head(20))

anomaly_df.to_parquet('data/exports/anomalous_routes.parquet', index=False)
```

**Caveat on statistical reliability:**
Isolation Forest is fitted on 3-5 annual data points per route (2015-2019
baseline). With that few observations the anomaly scores will be noisy —
a single unusual year can swing the model. Present persistent anomalies
(2+ years flagged) as directionally interesting, not statistically rigorous.
Routes with `n_flights < 100` in the baseline years are especially
unreliable — consider filtering them out before fitting.

**What to look for in results:**
- Are the persistently anomalous routes concentrated at one airport?
  If IAD has disproportionate anomalous routes that maps to the
  United hub dependency story.
- Do the anomalous routes share characteristics — similar distance band,
  similar NAS share profile?
- Are any routes anomalous in 2023 but recovered by 2025? That's the
  recovery arc story.

**Globe integration:**
The `anomalous_routes.parquet` feeds a toggleable red arc layer on the
CesiumJS globe. Routes flagged as persistently anomalous draw in red
when the "Post-2022 degradation" toggle is enabled. This is the most
direct visual connection between the modeling output and the globe
centerpiece.

---

## Section 6 — Modeling Summary

**Goal:** Document every finding from all four models in one place.
This section is the direct input to the blog narrative — every
claim in the blog that comes from modeling should be traceable
to a specific number in this section.

**Template:**

```
=== Modeling Summary: three-airports ===

HDBSCAN Route Clustering
  Clusters found: X  (Y% noise)
  Cluster names and defining characteristics:
    [0] Name — key features
    [1] Name — key features
    [-1] Noise — X routes, characteristics

Prophet Forecasting
  IAD late_rate: forecast YYYY = X%, actual = Y%, gap = +Z pp
  DCA late_rate: forecast YYYY = X%, actual = Y%, gap = +Z pp
  BWI late_rate: forecast YYYY = X%, actual = Y%, gap = +Z pp
  Interpretation: [what the gap means in plain English]

GAM Delay Predictor
  Test AUC: X.XX
  Most significant predictors (by p-value):
    1. [predictor] — direction and magnitude of effect
    2. [predictor] — direction and magnitude of effect
  Visibility partial dependence: IFR step-change confirmed/not confirmed
  
Isolation Forest Anomaly Detection
  Persistently anomalous routes post-2022: X
  Airport breakdown: IAD=X, DCA=X, BWI=X
  Most anomalous route: [Origin-Dest], anomalous in X of Y recent years

Next: 10_exports.ipynb
```

---

## Critical Notes

**Do not overstate model results in the blog.**
The GAM predicts delay with AUC ~0.70 — that's useful but not
highly accurate. Write "the model identifies thunderstorms as
the strongest weather predictor of delays" not "the model can
predict whether your flight will be late." The distinction matters
and a technical reader will notice if you overclaim.

**HDBSCAN noise points are a feature, not a failure.**
Routes labeled -1 (noise) didn't fit any cluster. That's honest.
Mention noise points in the blog — "roughly X% of routes were too
idiosyncratic to fit any cluster pattern" is a real finding.

**Prophet is not a causal model.**
The gap between forecast and actual is evidence of degradation
relative to pre-COVID trend, not proof that ATC staffing caused it.
Write "performance fell further below pre-COVID forecasts than
recovery would predict" not "the staffing crisis caused X% of delays."
The data supports the former, not the latter.

**Document all decisions in `knowledge/decisions.md`:**
- HDBSCAN hyperparameters chosen and why
- GAM terms included and any dropped for non-significance
- Contamination parameter for Isolation Forest and rationale
- Whether MAPIE conformal prediction was implemented or skipped
