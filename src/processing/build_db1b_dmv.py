"""
Concatenate quarterly DB1B parquets into a single processed parquet.
Run after db1b_download.py has completed.
"""
import sys
import time
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import RAW_DATA_PATH, PROCESSED_DATA_PATH

DB1B_DIR = Path(RAW_DATA_PATH) / "db1b"
OUT_PATH = Path(PROCESSED_DATA_PATH) / "db1b_dmv.parquet"

files = sorted(DB1B_DIR.glob("db1b_*.parquet"))
print(f"Found {len(files)} quarterly parquet files\n")

frames = []
t0 = time.time()

for i, f in enumerate(files, 1):
    df = pd.read_parquet(f)
    frames.append(df)
    print(f"  [{i:2d}/{len(files)}] {f.name}  {len(df):,} rows")

print(f"\nConcatenating...")
result = pd.concat(frames, ignore_index=True)

print(f"Shape: {result.shape[0]:,} rows x {result.shape[1]} columns")
print(f"Memory: {result.memory_usage(deep=True).sum() / 1e6:.1f} MB")
print(f"Year range: {result['Year'].min()} Q{result[result['Year']==result['Year'].min()]['Quarter'].min()} "
      f"to {result['Year'].max()} Q{result[result['Year']==result['Year'].max()]['Quarter'].max()}")
print(f"MktFare median: ${result[result['BulkFare']==0]['MktFare'].median():.0f}")

print(f"\nSaving to {OUT_PATH} ...")
result.to_parquet(OUT_PATH, index=False, engine="pyarrow")
print(f"Parquet size: {OUT_PATH.stat().st_size / 1e6:.1f} MB")
print("Done.")
