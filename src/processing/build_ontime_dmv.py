import sys
import time
import zipfile
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import RAW_DATA_PATH, PROCESSED_DATA_PATH, AIRPORTS

ZIPS_DIR = Path(RAW_DATA_PATH) / "zips"
OUT_PATH = Path(PROCESSED_DATA_PATH) / "ontime_dmv.parquet"

COLUMNS = [
    "Month", "DayOfWeek", "FlightDate",
    "Reporting_Airline", "Flight_Number_Reporting_Airline",
    "Origin", "OriginCityName", "OriginStateName",
    "Dest", "DestCityName", "DestState",
    "CRSDepTime", "DepTime", "DepDelay", "DepDelayMinutes", "TaxiOut",
    "CRSArrTime", "ArrTime", "ArrDelay", "ArrDelayMinutes", "TaxiIn",
    "Cancelled", "CancellationCode", "Diverted",
    "CRSElapsedTime", "ActualElapsedTime", "AirTime", "Distance",
    "CarrierDelay", "WeatherDelay", "NASDelay", "SecurityDelay", "LateAircraftDelay",
]

zips = sorted(ZIPS_DIR.glob("ontime_*.zip"))
print(f"Found {len(zips)} zip files")
print(f"Filtering to: {AIRPORTS}\n")

frames = []
skipped = []
t0 = time.time()

for i, zp in enumerate(zips, 1):
    try:
        with zipfile.ZipFile(zp) as z:
            csv_name = next(n for n in z.namelist() if n.endswith(".csv"))
            with z.open(csv_name) as f:
                df = pd.read_csv(f, usecols=COLUMNS, low_memory=False)

        df = df[df["Origin"].isin(AIRPORTS)].reset_index(drop=True)
        frames.append(df)
        print(f"  [{i:3d}/{len(zips)}] {zp.name}  ->  {len(df):,} rows")

    except Exception as e:
        print(f"  [{i:3d}/{len(zips)}] {zp.name}  ERROR: {e}")
        skipped.append(zp.name)

print(f"\nConcatenating {len(frames)} files...")
result = pd.concat(frames, ignore_index=True)

elapsed = time.time() - t0
print(f"Done in {elapsed:.0f}s")
print(f"Shape: {result.shape[0]:,} rows × {result.shape[1]} columns")
print(f"Memory: {result.memory_usage(deep=True).sum() / 1e6:.1f} MB")

if skipped:
    print(f"\nSkipped ({len(skipped)}): {skipped}")

print(f"\nSaving to {OUT_PATH} ...")
result.to_parquet(OUT_PATH, index=False, engine="pyarrow")
print(f"Parquet size: {OUT_PATH.stat().st_size / 1e6:.1f} MB")
print("Done.")
