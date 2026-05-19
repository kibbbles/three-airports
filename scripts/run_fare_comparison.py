"""Export fare_comparison.json: annual fare trends + shared-route fare by airport."""
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
AP_COLORS  = {'IAD': '#4e9af1', 'DCA': '#f97316', 'BWI': '#22c55e'}

print('Loading flights_featured.parquet ...')
feat = pd.read_parquet(PROC / 'flights_featured.parquet')
feat['FlightDate'] = pd.to_datetime(feat['FlightDate'])
feat['year']  = feat['FlightDate'].dt.year
operated = feat[feat['Cancelled'] == 0].copy()
fare_op  = operated[operated['db1b_avg_fare'].notna()].copy()
print(f'  {len(fare_op):,} operated flights with fare data')

# ── 1. Annual avg fare trend per airport ─────────────────────────────
print('Computing annual fare trends ...')
trend_raw = (
    fare_op.groupby(['Origin', 'year'])['db1b_avg_fare']
    .mean().reset_index(name='avg_fare')
)
years = sorted(fare_op['year'].unique().tolist())

trend = {'years': years}
for ap in AIRPORTS:
    ap_rows = trend_raw[trend_raw['Origin'] == ap].set_index('year')['avg_fare']
    trend[ap] = [
        round(float(ap_rows[y]), 0) if y in ap_rows.index else None
        for y in years
    ]

# ── 2. Shared-destination fare comparison ────────────────────────────
print('Finding shared destinations ...')
route_counts = operated.groupby(['Origin', 'Dest']).size().reset_index(name='n')
pivot_n = route_counts.pivot(index='Dest', columns='Origin', values='n').fillna(0)

# Destinations with 500+ flights from every DMV airport
shared_mask = (pivot_n.get('IAD', pd.Series(dtype=float)) > 500) & \
              (pivot_n.get('DCA', pd.Series(dtype=float)) > 500) & \
              (pivot_n.get('BWI', pd.Series(dtype=float)) > 500)
shared_dests = pivot_n[shared_mask].index.tolist()
print(f'  {len(shared_dests)} shared destinations')

# Avg fare and flight count per airport for shared destinations
fare_shared = (
    fare_op[fare_op['Dest'].isin(shared_dests)]
    .groupby(['Origin', 'Dest'])
    .agg(avg_fare=('db1b_avg_fare', 'mean'), n=('db1b_avg_fare', 'count'))
    .reset_index()
)
fare_piv = fare_shared.pivot(index='Dest', columns='Origin', values='avg_fare')
n_piv    = fare_shared.pivot(index='Dest', columns='Origin', values='n').fillna(0)

# Dest city names from routes.geojson
geo_path = EXPORTS / 'routes.geojson'
dest_city: dict[str, str] = {}
if geo_path.exists():
    geo = json.loads(geo_path.read_text())
    for f in geo['features']:
        p = f['properties']
        dest_city[p['dest']] = p.get('dest_city') or p['dest']

shared_routes = []
for dest in shared_dests:
    if dest not in fare_piv.index:
        continue
    row: dict = {'dest': dest, 'city': dest_city.get(dest, dest)}
    ok = True
    for ap in AIRPORTS:
        val = fare_piv.loc[dest, ap] if ap in fare_piv.columns else np.nan
        if np.isnan(val):
            ok = False; break
        row[ap]         = round(float(val), 0)
        row[f'n_{ap}']  = int(n_piv.loc[dest, ap]) if ap in n_piv.columns else 0
    if ok:
        shared_routes.append(row)

# Sort by total flight volume
shared_routes.sort(
    key=lambda r: r.get('n_IAD', 0) + r.get('n_DCA', 0) + r.get('n_BWI', 0),
    reverse=True,
)

# ── Output ────────────────────────────────────────────────────────────
out = {
    'airports':      AIRPORTS,
    'colors':        AP_COLORS,
    'trend':         trend,
    'shared_routes': shared_routes,
}

out_path = EXPORTS / 'fare_comparison.json'
with open(out_path, 'w') as f:
    json.dump(out, f, separators=(',', ':'))

sz = out_path.stat().st_size
print(f'\nTrend years:    {len(years)}')
print(f'Shared routes:  {len(shared_routes)}')
print(f'File size:      {sz/1e3:.1f} KB')
print(f'Saved:          {out_path}')

print('\nSample trend (IAD):')
for y, v in zip(years, trend['IAD']):
    print(f'  {y}: ${v:.0f}' if v is not None else f'  {y}: —')

print('\nTop 5 shared routes:')
for r in shared_routes[:5]:
    print(f"  {r['dest']} ({r['city']}): IAD=${r['IAD']:.0f}  DCA=${r['DCA']:.0f}  BWI=${r['BWI']:.0f}")
