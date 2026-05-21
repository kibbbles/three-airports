"""Export carrier_breakdown.json: market share + median fares by carrier per airport."""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from config import PROCESSED_DATA_PATH, EXPORTS_PATH

PROC    = PROJECT_ROOT / PROCESSED_DATA_PATH
EXPORTS = PROJECT_ROOT / EXPORTS_PATH
EXPORTS.mkdir(parents=True, exist_ok=True)

AIRPORTS = ['IAD', 'DCA', 'BWI']
TOP_N    = 6   # carriers per airport in each chart

CARRIER_NAMES = {
    'AA': 'American',      'WN': 'Southwest',  'DL': 'Delta',
    'UA': 'United',        'B6': 'JetBlue',    'AS': 'Alaska',
    'F9': 'Frontier',      'NK': 'Spirit',     'G4': 'Allegiant',
    'VX': 'Virgin America','US': 'US Airways', 'SY': 'Sun Country',
}

# Colors chosen for legibility on dark backgrounds, distinct from airport colors
CARRIER_COLORS = {
    'UA': '#5b8fd4',  # United — blue
    'AA': '#e05a4a',  # American — red
    'WN': '#f5a623',  # Southwest — amber
    'DL': '#a569bd',  # Delta — purple
    'B6': '#2ec4d5',  # JetBlue — teal
    'AS': '#48c97e',  # Alaska — emerald
    'NK': '#f7d44c',  # Spirit — yellow
    'F9': '#8bc34a',  # Frontier — lime
    'G4': '#e67e22',  # Allegiant — orange
    'VX': '#e91e8c',  # Virgin America — pink
    'US': '#95a5a6',  # US Airways — silver
    'SY': '#3498db',  # Sun Country — sky
}
OTHER_COLOR = '#3d4455'

print('Loading db1b_dmv.parquet ...')
df = pd.read_parquet(PROC / 'db1b_dmv.parquet')
fare = df[
    (df['BulkFare'] == 0) &
    (df['MktFare'] > 0) &
    (~df['TkCarrier'].isin(['99', '--']))
].copy()
outbound = fare[fare['Origin'].isin(AIRPORTS)]
print(f'  {len(outbound):,} outbound fare records')

share_out: dict = {}
fares_out: dict = {}

for ap in AIRPORTS:
    sub = outbound[outbound['Origin'] == ap]

    # ── Market share by passenger count ──────────────────────────
    pax       = sub.groupby('TkCarrier')['Passengers'].sum().sort_values(ascending=False)
    total_pax = pax.sum()
    top_c     = pax.head(TOP_N).index.tolist()

    rows = []
    for c in top_c:
        n = int(pax[c])
        rows.append({
            'carrier': c,
            'name':    CARRIER_NAMES.get(c, c),
            'pax':     n,
            'pct':     round(float(n / total_pax), 4),
            'color':   CARRIER_COLORS.get(c, OTHER_COLOR),
        })
    other_pax = int(pax.iloc[TOP_N:].sum())
    if other_pax > 0:
        rows.append({
            'carrier': 'Other',
            'name':    'Other',
            'pax':     other_pax,
            'pct':     round(float(other_pax / total_pax), 4),
            'color':   OTHER_COLOR,
        })
    share_out[ap] = rows

    # ── Median fare for those same top carriers ───────────────────
    fare_rows = []
    for c in top_c:
        med = float(sub[sub['TkCarrier'] == c]['MktFare'].median())
        fare_rows.append({
            'carrier':     c,
            'name':        CARRIER_NAMES.get(c, c),
            'median_fare': round(med, 0),
            'color':       CARRIER_COLORS.get(c, OTHER_COLOR),
        })
    fare_rows.sort(key=lambda r: r['median_fare'])   # ascending: cheapest first
    fares_out[ap] = fare_rows

out = {
    'carrier_names':  CARRIER_NAMES,
    'carrier_colors': CARRIER_COLORS,
    'other_color':    OTHER_COLOR,
    'share':          share_out,
    'fares':          fares_out,
}

out_path = EXPORTS / 'carrier_breakdown.json'
with open(out_path, 'w') as f:
    json.dump(out, f, separators=(',', ':'))

print(f'\nFile size: {out_path.stat().st_size / 1e3:.1f} KB')
print(f'Saved:     {out_path}')

for ap in AIRPORTS:
    print(f'\n{ap} share (top {TOP_N}):')
    for r in share_out[ap]:
        print(f"  {r['name']:20} {r['pct']*100:5.1f}%  {r['pax']:>10,}")
    print(f'{ap} median fares:')
    for r in fares_out[ap]:
        print(f"  {r['name']:20} ${r['median_fare']:.0f}")
