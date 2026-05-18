"""Re-exports crossfilter_data.json with fine-grained delay and distance bins."""
import json, sys, warnings
from pathlib import Path

warnings.filterwarnings('ignore')
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from config import PROCESSED_DATA_PATH, EXPORTS_PATH

PROC    = PROJECT_ROOT / PROCESSED_DATA_PATH
EXPORTS = PROJECT_ROOT / EXPORTS_PATH
EXPORTS.mkdir(parents=True, exist_ok=True)

AIRPORTS   = ['IAD', 'DCA', 'BWI']
ORIGIN_IDX = {ap: i for i, ap in enumerate(AIRPORTS)}

print('Loading flights_featured.parquet …')
feat = pd.read_parquet(PROC / 'flights_featured.parquet')
feat['FlightDate'] = pd.to_datetime(feat['FlightDate'])
print(f'  {len(feat):,} total rows')

feat2 = feat.copy()
feat2['year']     = feat2['FlightDate'].dt.year
feat2['month']    = feat2['FlightDate'].dt.month
feat2['dep_hour'] = (feat2['CRSDepTime'] // 100).clip(0, 23)

# 14 delay bins  — left edge is label, right=False (left-closed intervals)
# bins: <-60, -60, -45, -30, -15, -5, 0, 5, 15, 30, 45, 60, 90, 120+
DELAY_EDGES = [-np.inf, -60, -45, -30, -15, -5, 0, 5, 15, 30, 45, 60, 90, 120, np.inf]
DB_N = len(DELAY_EDGES) - 1  # 14

# 15 distance bins  — even 200-mile steps 0 through 2800+
DIST_EDGES = [0, 200, 400, 600, 800, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400, 2600, 2800, np.inf]
XB_N = len(DIST_EDGES) - 1  # 15

feat2['delay_bin'] = pd.cut(feat2['ArrDelay'], bins=DELAY_EDGES, right=False, labels=False)
feat2['dist_bin']  = pd.cut(feat2['Distance'],        bins=DIST_EDGES,  right=False, labels=False)

KEY = ['Origin', 'year', 'month', 'dep_hour']

counts = (
    feat2.groupby(KEY, observed=True)
    .agg(n=('Cancelled', 'count'), nc=('Cancelled', 'sum'), nl=('is_late', 'sum'))
    .reset_index()
)

op2 = feat2[(feat2['Cancelled'] == 0) & feat2['delay_bin'].notna()].copy()
op2['delay_bin'] = op2['delay_bin'].astype(int)
delay_agg = (
    op2.groupby(KEY + ['delay_bin'])
    .size()
    .unstack('delay_bin', fill_value=0)
    .reindex(columns=range(DB_N), fill_value=0)
    .rename(columns={i: f'db{i}' for i in range(DB_N)})
    .reset_index()
)

feat2_dist = feat2[feat2['dist_bin'].notna()].copy()
feat2_dist['dist_bin'] = feat2_dist['dist_bin'].astype(int)
dist_agg = (
    feat2_dist.groupby(KEY + ['dist_bin'])
    .size()
    .unstack('dist_bin', fill_value=0)
    .reindex(columns=range(XB_N), fill_value=0)
    .rename(columns={i: f'xb{i}' for i in range(XB_N)})
    .reset_index()
)

merged = (
    counts
    .merge(delay_agg, on=KEY, how='left')
    .merge(dist_agg,  on=KEY, how='left')
    .fillna(0)
)

db_cols = [f'db{i}' for i in range(DB_N)]
xb_cols = [f'xb{i}' for i in range(XB_N)]

records = []
for _, r in merged.iterrows():
    records.append([
        ORIGIN_IDX[r['Origin']],
        int(r['year']), int(r['month']), int(r['dep_hour']),
        int(r['n']), int(r['nc']), int(r['nl']),
        *[int(r[c]) for c in db_cols],
        *[int(r[c]) for c in xb_cols],
    ])

out_data = {
    'airports': AIRPORTS,
    'cols': ['o', 'y', 'm', 'h', 'n', 'nc', 'nl'] + db_cols + xb_cols,
    'rows': records,
}

out = EXPORTS / 'crossfilter_data.json'
with open(out, 'w') as f:
    json.dump(out_data, f, separators=(',', ':'))

sz = out.stat().st_size
print(f'Rows:      {len(records):,}')
print(f'Columns:   {len(out_data["cols"])}  (7 base + {DB_N} delay + {XB_N} dist)')
print(f'Size:      {sz/1e3:.1f} KB')
print(f'Saved:     {out}')

# Early arrival summary (bins 0-5 = ArrDelay < 0)
early_n = sum(sum(r[7 + i] for i in range(6)) for r in records)
all_op  = sum(sum(r[7 + i] for i in range(DB_N)) for r in records)
if all_op:
    print(f'\nEarly arrivals (ArrDelay < 0): {early_n:,}  ({early_n/all_op*100:.1f}% of operated)')
