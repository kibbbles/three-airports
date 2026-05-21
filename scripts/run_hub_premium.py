"""Export hub_premium.json: within-carrier IAD-vs-BWI and DCA-vs-BWI fare premium per route."""
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

def filtered_pairs(ap: str) -> pd.DataFrame:
    """Routes where carrier has >= MIN_TICKETS at both `ap` and BWI."""
    df2 = fares_wide.dropna(subset=[ap, 'BWI']).copy()
    t   = tickets_wide.reindex(df2.index)
    df2 = df2[(t[[ap, 'BWI']].min(axis=1) >= MIN_TICKETS)].copy()
    df2['prem'] = (df2[ap] - df2['BWI']).round(1)
    return df2.reset_index()

iad_df = filtered_pairs('IAD')
dca_df = filtered_pairs('DCA')

# Per-carrier summary — sorted by IAD median premium ascending
carrier_rows = []
for c in CARRIERS:
    iad_sub = iad_df[iad_df['TkCarrier'] == c]['prem']
    dca_sub = dca_df[dca_df['TkCarrier'] == c]['prem']
    if len(iad_sub) == 0 and len(dca_sub) == 0:
        continue
    carrier_rows.append({
        'carrier':         c,
        'name':            CARRIER_NAMES[c],
        'color':           CARRIER_COLORS[c],
        'n_iad':           int(len(iad_sub)),
        'n_dca':           int(len(dca_sub)),
        'iad_median_prem': round(float(iad_sub.median()), 1) if len(iad_sub) else None,
        'dca_median_prem': round(float(dca_sub.median()), 1) if len(dca_sub) else None,
        'pct_iad_cheaper': round(float((iad_sub < 0).mean() * 100), 1) if len(iad_sub) else None,
        'pct_dca_cheaper': round(float((dca_sub < 0).mean() * 100), 1) if len(dca_sub) else None,
    })
carrier_rows.sort(key=lambda r: (r['iad_median_prem'] or 0))

# Route-level points — ap field distinguishes IAD vs DCA
route_rows = []
for src_df, ap_code in [(iad_df, 'IAD'), (dca_df, 'DCA')]:
    ap_col = ap_code
    for _, row in src_df.iterrows():
        route_rows.append({
            'ap':      ap_code,
            'carrier': row['TkCarrier'],
            'dest':    row['Dest'],
            'ap_fare': int(round(row[ap_col])),
            'bwi':     int(round(row['BWI'])),
            'prem':    int(round(row['prem'])),
        })

out = {'carriers': carrier_rows, 'routes': route_rows}

out_path = EXPORTS / 'hub_premium.json'
with open(out_path, 'w') as f:
    json.dump(out, f, separators=(',', ':'))

print(f'\nSaved: {out_path}  ({out_path.stat().st_size / 1e3:.1f} KB)')
iad_n = sum(r['n_iad'] for r in carrier_rows)
dca_n = sum(r['n_dca'] for r in carrier_rows)
print(f'{len(carrier_rows)} carriers  |  IAD: {iad_n} routes  |  DCA: {dca_n} routes\n')
for r in carrier_rows:
    i_s = f"+{r['iad_median_prem']:.0f}" if (r['iad_median_prem'] or 0) >= 0 else f"{r['iad_median_prem']:.0f}"
    d_s = f"+{r['dca_median_prem']:.0f}" if (r['dca_median_prem'] or 0) >= 0 else f"{r['dca_median_prem']:.0f}"
    print(f"  {r['name']:10}  IAD med={i_s:5s} (n={r['n_iad']:3d})  DCA med={d_s:5s} (n={r['n_dca']:3d})")
