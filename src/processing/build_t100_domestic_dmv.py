"""
Build domestic T-100 parquet for IAD/DCA/BWI.

The raw T-100 zips (FMG, cboGeography=All) contain both domestic and
international segments. This script keeps only domestic rows (ORIGIN_COUNTRY
== DEST_COUNTRY == 'US') where the origin is one of our three airports.

No new download needed — uses the same data/raw/t100/ files as the
international build.
"""
import sys
import time
import zipfile
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import RAW_DATA_PATH, PROCESSED_DATA_PATH, AIRPORTS

ZIPS_DIR = Path(RAW_DATA_PATH) / "t100"
OUT_PATH = Path(PROCESSED_DATA_PATH) / "t100_domestic_dmv.parquet"

COLUMNS = [
    "YEAR", "QUARTER", "MONTH",
    "UNIQUE_CARRIER", "UNIQUE_CARRIER_NAME",
    "ORIGIN", "ORIGIN_CITY_NAME", "ORIGIN_WAC",
    "DEST", "DEST_CITY_NAME", "DEST_WAC",
    "DEPARTURES_PERFORMED", "SEATS", "PASSENGERS", "FREIGHT", "DISTANCE",
    "AIRCRAFT_GROUP", "AIRCRAFT_TYPE", "CLASS",
]

zips = sorted(ZIPS_DIR.glob("t100_*.zip"))
print(f"Found {len(zips)} zip files")
print(f"Filtering to domestic routes originating at: {AIRPORTS}\n")

frames = []
skipped = []
t0 = time.time()

for i, zp in enumerate(zips, 1):
    try:
        with zipfile.ZipFile(zp) as z:
            csv_name = next(n for n in z.namelist() if n.endswith(".csv"))
            with z.open(csv_name) as f:
                df = pd.read_csv(f, low_memory=False)

        domestic = (df["ORIGIN_COUNTRY"] == "US") & (df["DEST_COUNTRY"] == "US")
        dmv = df["ORIGIN"].isin(AIRPORTS)
        df = df[domestic & dmv][COLUMNS].reset_index(drop=True)

        frames.append(df)
        print(f"  [{i:2d}/{len(zips)}] {zp.name}  ->  {len(df):,} rows")

    except Exception as e:
        print(f"  [{i:2d}/{len(zips)}] {zp.name}  ERROR: {e}")
        skipped.append(zp.name)

print(f"\nConcatenating {len(frames)} files...")
result = pd.concat(frames, ignore_index=True)

elapsed = time.time() - t0
print(f"Done in {elapsed:.0f}s")
print(f"Shape: {result.shape[0]:,} rows × {result.shape[1]} columns")
print(f"Year range: {result['YEAR'].min()} – {result['YEAR'].max()}")
print(f"Memory: {result.memory_usage(deep=True).sum() / 1e6:.1f} MB")

if skipped:
    print(f"\nSkipped ({len(skipped)}): {skipped}")

print(f"\nSaving to {OUT_PATH} ...")
result.to_parquet(OUT_PATH, index=False, engine="pyarrow")
print(f"Parquet size: {OUT_PATH.stat().st_size / 1e6:.1f} MB")
print("Done.")
