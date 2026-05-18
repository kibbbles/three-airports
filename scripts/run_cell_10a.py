"""Standalone runner for notebook cell 10a — route_monthly.json export."""
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
operated = feat[feat['Cancelled'] == 0].copy()
print(f'  {len(operated):,} operated flights loaded')

# ── cell 10a ──────────────────────────────────────────────────────
feat_op2 = operated.copy()
feat_op2['year']  = feat_op2['FlightDate'].dt.year
feat_op2['month'] = feat_op2['FlightDate'].dt.month

print('Computing top-3 carriers per route …')
rc = (
    feat_op2
    .groupby(['Origin', 'Dest', 'Reporting_Airline'])
    .size()
    .reset_index(name='n')
    .sort_values(['Origin', 'Dest', 'n'], ascending=[True, True, False])
)
route_carriers: dict = {}
for (orig, dest), grp in rc.groupby(['Origin', 'Dest']):
    route_carriers[f'{orig}-{dest}'] = grp.head(3)['Reporting_Airline'].tolist()

print('Computing operating hours per route …')
feat_op2['dep_hour'] = (feat_op2['CRSDepTime'] // 100).clip(0, 23)
rh = (
    feat_op2.groupby(['Origin', 'Dest', 'dep_hour'])
    .size()
    .reset_index(name='n')
)
route_hours: dict = {}
for (orig, dest), grp in rh.groupby(['Origin', 'Dest']):
    active = sorted(grp[grp['n'] >= 50]['dep_hour'].tolist())
    route_hours[f'{orig}-{dest}'] = active

print('Aggregating monthly route stats …')
rm = (
    feat_op2
    .groupby(['Origin', 'Dest', 'year', 'month'])
    .agg(
        n          = ('is_late',         'count'),
        late       = ('is_late',         'sum'),
        mean_delay = ('ArrDelay', 'mean'),
        mean_fare  = ('db1b_avg_fare',   'mean'),
    )
    .reset_index()
)

all_dests = sorted(rm['Dest'].unique().tolist())
dest_idx  = {d: i for i, d in enumerate(all_dests)}

records = []
for _, r in rm.iterrows():
    md = round(float(r['mean_delay']), 1) if pd.notna(r['mean_delay']) else None
    mf = round(float(r['mean_fare']),  0) if pd.notna(r['mean_fare'])  else None
    lr = round(float(r['late']) / float(r['n']), 4) if r['n'] > 0 else 0.0
    records.append([
        ORIGIN_IDX[r['Origin']],
        dest_idx[r['Dest']],
        int(r['year']),
        int(r['month']),
        int(r['n']),
        lr, md, mf,
    ])

out = EXPORTS / 'route_monthly.json'
with open(out, 'w') as f:
    json.dump({
        'origins':     AIRPORTS,
        'dests':       all_dests,
        'carriers':    route_carriers,
        'route_hours': route_hours,
        'cols':        ['o', 'd', 'y', 'm', 'n', 'lr', 'md', 'mf'],
        'rows':        records,
    }, f, separators=(',', ':'))

print(f'\nRoute monthly:  {len(records):,} rows  |  {out.stat().st_size/1e3:.1f} KB')
print(f'Unique routes:  {len(route_carriers)}')
print(f'Destinations:   {len(all_dests)}')
print(f'Saved: {out}')
print()
print('Sample carriers:')
for k, v in list(route_carriers.items())[:6]:
    print(f'  {k}: {v}')
