"""Export carrier_ontime.json: late-arrival rate per carrier per airport."""
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

# Carriers to include — mainlines + notable regionals (excludes defunct US/VX/EV)
INCLUDE = {'WN', 'UA', 'AA', 'DL', 'B6', 'NK', 'AS', 'F9', 'OH', 'YX'}
MIN_FLIGHTS_AP = 1000  # minimum flights at a specific airport to show a dot

CARRIER_NAMES = {
    'AA': 'American',    'WN': 'Southwest', 'DL': 'Delta',
    'UA': 'United',      'B6': 'JetBlue',   'AS': 'Alaska',
    'F9': 'Frontier',    'NK': 'Spirit',    'OH': 'PSA Airlines',
    'YX': 'Republic',
}

CARRIER_COLORS = {
    'UA': '#5b8fd4',  'AA': '#e05a4a',  'WN': '#f5a623',
    'DL': '#a569bd',  'B6': '#2ec4d5',  'AS': '#48c97e',
    'NK': '#f7d44c',  'F9': '#8bc34a',  'OH': '#fb7185',
    'YX': '#94a3b8',
}

print('Loading ontime_dmv.parquet ...')
df = pd.read_parquet(PROC / 'ontime_dmv.parquet')
print(f'  {len(df):,} rows')

# Non-cancelled flights for late-rate computation
active = df[df['Cancelled'] != 1].copy()
active['late'] = (active['ArrDelay'] >= 15).astype(int)

grp = active.groupby(['Reporting_Airline', 'Origin']).agg(
    flights=('late', 'count'),
    late_count=('late', 'sum'),
    median_delay=('ArrDelay', 'median'),
).reset_index()
grp['late_rate'] = grp['late_count'] / grp['flights']

# Cancellation rate (across all flights including cancelled)
canc = df.groupby(['Reporting_Airline', 'Origin']).agg(
    total=('Cancelled', 'count'),
    cancelled=('Cancelled', 'sum'),
).reset_index()
canc['cancel_rate'] = canc['cancelled'] / canc['total']

out_carriers = []
for c in INCLUDE:
    c_grp  = grp[grp['Reporting_Airline'] == c]
    c_canc = canc[canc['Reporting_Airline'] == c]

    airports_data = {}
    total_flights = 0
    total_late    = 0

    for ap in AIRPORTS:
        row = c_grp[c_grp['Origin'] == ap]
        n   = int(row['flights'].iloc[0]) if len(row) > 0 else 0
        if n < MIN_FLIGHTS_AP:
            airports_data[ap] = None
            continue

        lr = round(float(row['late_rate'].iloc[0]), 4)
        md = round(float(row['median_delay'].iloc[0]), 1)
        crow = c_canc[c_canc['Origin'] == ap]
        cr   = round(float(crow['cancel_rate'].iloc[0]), 4) if len(crow) > 0 else None

        airports_data[ap] = {'flights': n, 'late_rate': lr, 'median_delay': md, 'cancel_rate': cr}
        total_flights += n
        total_late    += int(row['late_count'].iloc[0])

    if total_flights == 0:
        continue

    overall_lr = round(total_late / total_flights, 4)
    out_carriers.append({
        'carrier':          c,
        'name':             CARRIER_NAMES.get(c, c),
        'color':            CARRIER_COLORS.get(c, '#7a8099'),
        'airports':         airports_data,
        'overall_late_rate': overall_lr,
        'total_flights':    total_flights,
    })

# Sort worst to best
out_carriers.sort(key=lambda x: x['overall_late_rate'], reverse=True)

out = {'carriers': out_carriers}
out_path = EXPORTS / 'carrier_ontime.json'
with open(out_path, 'w') as f:
    json.dump(out, f, separators=(',', ':'))

print(f'\nFile size: {out_path.stat().st_size / 1e3:.1f} KB')
print(f'Saved:     {out_path}')

print('\nResults (worst → best):')
for c in out_carriers:
    print(f"\n  {c['name']:14} overall {c['overall_late_rate']*100:.1f}%")
    for ap in AIRPORTS:
        d = c['airports'][ap]
        if d:
            print(f"    {ap}: {d['late_rate']*100:.1f}%  ({d['flights']:,} flights)")
        else:
            print(f"    {ap}: —")
