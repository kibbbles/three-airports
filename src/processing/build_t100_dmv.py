"""
Build parquet of international T-100 segments for DMV airports (IAD, DCA, BWI).

Keeps rows where:
  - ORIGIN or DEST is one of the three airports, AND
  - ORIGIN_COUNTRY != 'US' or DEST_COUNTRY != 'US'  (at least one leg is international)

Output: data/processed/t100_intl_dmv.parquet
"""
import sys
import time
import zipfile
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import RAW_DATA_PATH, PROCESSED_DATA_PATH, AIRPORTS

T100_DIR = Path(RAW_DATA_PATH) / "t100"
OUT_PATH = Path(PROCESSED_DATA_PATH) / "t100_intl_dmv.parquet"

zips = sorted(T100_DIR.glob("t100_*.zip"))
print(f"Found {len(zips)} T-100 zip files")
print(f"Filtering to airports: {AIRPORTS}, international routes only\n")

frames = []
skipped = []
t0 = time.time()

for i, zp in enumerate(zips, 1):
    try:
        with zipfile.ZipFile(zp) as z:
            csv_name = next(n for n in z.namelist() if n.endswith(".csv"))
            with z.open(csv_name) as f:
                df = pd.read_csv(f, low_memory=False)

        dmv_mask  = df["ORIGIN"].isin(AIRPORTS) | df["DEST"].isin(AIRPORTS)
        intl_mask = (df["ORIGIN_COUNTRY"] != "US") | (df["DEST_COUNTRY"] != "US")
        df = df[dmv_mask & intl_mask].reset_index(drop=True)

        frames.append(df)
        print(f"  [{i:2d}/{len(zips)}] {zp.name}  ->  {len(df):,} rows")

    except Exception as e:
        print(f"  [{i:2d}/{len(zips)}] {zp.name}  ERROR: {e}")
        skipped.append(zp.name)

print(f"\nConcatenating {len(frames)} files...")
result = pd.concat(frames, ignore_index=True)

elapsed = time.time() - t0
print(f"Done in {elapsed:.0f}s")
print(f"Shape: {result.shape[0]:,} rows x {result.shape[1]} columns")
print(f"Memory: {result.memory_usage(deep=True).sum() / 1e6:.1f} MB")
print(f"Year range: {result['YEAR'].min()} - {result['YEAR'].max()}")
print(f"Airports in ORIGIN: {sorted(result[result['ORIGIN'].isin(AIRPORTS)]['ORIGIN'].unique())}")
print(f"Top dest countries: {result['DEST_COUNTRY'].value_counts().head(10).to_dict()}")

if skipped:
    print(f"\nSkipped ({len(skipped)}): {skipped}")

print(f"\nSaving to {OUT_PATH} ...")
result.to_parquet(OUT_PATH, index=False, engine="pyarrow")
print(f"Parquet size: {OUT_PATH.stat().st_size / 1e6:.1f} MB")
print("Done.")
