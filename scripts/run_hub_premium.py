"""Export hub_premium.json: within-carrier IAD-vs-BWI fare premium per shared route."""
import json, sys
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from config import PROCESSED_DATA_PATH, EXPORTS_PATH

PROC    = PROJECT_ROOT / PROCESSED_DATA_PATH
EXPORTS = PROJECT_ROOT / EXPORTS_PATH
EXPORTS.mkdir(parents=True, exist_ok=True)

AIRPORTS = ['IAD', 'DCA', 'BWI']
CARRIER_NAMES = {
    'AA': 'American', 'WN': 'Southwest', 'DL': 'Delta',
    'UA': 'United',   'AS': 'Alaska',    'F9': 'Frontier',
}
CARRIER_COLORS = {
    'UA': '#5b8fd4', 'AA': '#e05a4a', 'WN': '#f5a623',
    'DL': '#a569bd', 'AS': '#48c97e', 'F9': '#8bc34a',
}
CARRIERS    = list(CARRIER_NAMES.keys())
MIN_TICKETS = 500

print('Loading db1b_dmv.parquet ...')
df = pd.read_parquet(PROC / 'db1b_dmv.parquet')
fare = df[
    (df['BulkFare'] == 0) &
    (df['MktFare'] > 0) &
    (~df['TkCarrier'].isin(['99', '--']))
].copy()
outbound = fare[fare['Origin'].isin(AIRPORTS) & fare['TkCarrier'].isin(CARRIERS)]
print(f'  {len(outbound):,} outbound records (top 6 carriers)')

grp = (
    outbound.groupby(['TkCarrier', 'Origin', 'Dest'])
    .agg(med_fare=('MktFare', 'median'), tickets=('Passengers', 'sum'))
    .reset_index()
)
fares_wide   = grp.pivot_table(index=['TkCarrier', 'Dest'], columns='Origin', values='med_fare')
tickets_wide = grp.pivot_table(index=['TkCarrier', 'Dest'], columns='Origin', values='tickets')

# IAD+BWI pairs with sufficient volume at both airports
ib = fares_wide.dropna(subset=['IAD', 'BWI'])
ib_t = tickets_wide.reindex(ib.index)
ib = ib[(ib_t[['IAD', 'BWI']].min(axis=1) >= MIN_TICKETS)].copy()
ib['premium'] = (ib['IAD'] - ib['BWI']).round(1)
ib = ib.reset_index()

# Per-carrier summary (sorted ascending by median premium)
carrier_rows = []
for c in CARRIERS:
    sub = ib[ib['TkCarrier'] == c]
    prems = sub['premium']
    if len(prems) == 0:
        continue
    carrier_rows.append({
        'carrier':         c,
        'name':            CARRIER_NAMES[c],
        'color':           CARRIER_COLORS[c],
        'n':               int(len(prems)),
        'median_prem':     round(float(prems.median()), 1),
        'pct_iad_cheaper': round(float((prems < 0).mean() * 100), 1),
    })
carrier_rows.sort(key=lambda r: r['median_prem'])

# Route-level data for strip dots in chart
route_rows = []
for _, row in ib.iterrows():
    route_rows.append({
        'carrier': row['TkCarrier'],
        'dest':    row['Dest'],
        'iad':     int(round(row['IAD'])),
        'bwi':     int(round(row['BWI'])),
        'prem':    int(round(row['premium'])),
    })

out = {'carriers': carrier_rows, 'routes': route_rows}

out_path = EXPORTS / 'hub_premium.json'
with open(out_path, 'w') as f:
    json.dump(out, f, separators=(',', ':'))

print(f'\nSaved: {out_path}  ({out_path.stat().st_size / 1e3:.1f} KB)')
print(f'{len(carrier_rows)} carriers, {len(route_rows)} (carrier, dest) pairs\n')
for r in carrier_rows:
    sign = '+' if r['median_prem'] >= 0 else ''
    print(f"  {r['name']:10}  n={r['n']:3d}  median={sign}{r['median_prem']:.0f}  {r['pct_iad_cheaper']:.0f}% IAD cheaper")
