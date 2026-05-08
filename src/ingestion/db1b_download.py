"""
Download BTS DB1B Market quarterly files (2015 Q1 – 2026 Q1).

Each quarterly source file is ~88MB compressed / ~500MB uncompressed.
We stream each file, filter immediately to DMV airports, and save a small
per-quarter parquet (~2MB) to data/raw/db1b/ — raw zips are not kept.

Run time: ~60-90 min depending on connection speed.
"""
import io
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import RAW_DATA_PATH, AIRPORTS, START_YEAR, END_YEAR, END_MONTH

BASE_URL = (
    "https://transtats.bts.gov/PREZIP/"
    "Origin_and_Destination_Survey_DB1BMarket_{year}_{quarter}.zip"
)

COLUMNS = [
    "Year", "Quarter",
    "Origin", "OriginCountry", "OriginState", "OriginStateName", "OriginWac",
    "Dest",   "DestCountry",   "DestState",   "DestStateName",   "DestWac",
    "RPCarrier", "TkCarrier", "OpCarrier",
    "BulkFare", "Passengers", "MktFare", "MktDistance", "MktCoupons",
    "NonStopMiles", "ItinGeoType", "MktGeoType",
]

OUT_DIR = Path(RAW_DATA_PATH) / "db1b"
OUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def build_work_list():
    """Quarterly periods from START_YEAR Q1 through END_YEAR Q{ceil(END_MONTH/3)}."""
    work = []
    end_quarter = (END_MONTH - 1) // 3 + 1
    for year in range(START_YEAR, END_YEAR + 1):
        for q in range(1, 5):
            if year == END_YEAR and q > end_quarter:
                break
            work.append((year, q))
    return work


def is_valid_parquet(path: Path) -> bool:
    try:
        pd.read_parquet(path, columns=["Year"])
        return True
    except Exception:
        return False


def download_quarter(year: int, quarter: int, out_path: Path, retries: int = 3) -> bool:
    url = BASE_URL.format(year=year, quarter=quarter)
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, timeout=300, stream=True, headers=HEADERS)
            r.raise_for_status()

            raw = b"".join(r.iter_content(65536))
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                csv_name = next(n for n in z.namelist() if n.endswith(".csv"))
                df = pd.read_csv(z.open(csv_name), low_memory=False)

            # Filter to DMV airports — Origin OR Dest
            df = df[df["Origin"].isin(AIRPORTS) | df["Dest"].isin(AIRPORTS)].reset_index(drop=True)

            # Keep only useful columns (drop any missing from older files)
            keep = [c for c in COLUMNS if c in df.columns]
            df = df[keep]

            df.to_parquet(out_path, index=False, engine="pyarrow")
            return True

        except Exception as e:
            print(f"    attempt {attempt}/{retries} failed: {e}")
            if out_path.exists():
                out_path.unlink()
            if attempt < retries:
                time.sleep(5 * attempt)

    return False


work_list = build_work_list()
total = len(work_list)
print(f"DB1B downloader: {total} quarters to check  ->  {OUT_DIR}\n")

ok, skipped, failed = 0, 0, []
t0 = time.time()

for i, (year, quarter) in enumerate(work_list, 1):
    fname = f"db1b_{year}_Q{quarter}.parquet"
    out_path = OUT_DIR / fname
    label = f"[{i:2d}/{total}] {fname}"

    if out_path.exists() and is_valid_parquet(out_path):
        rows = len(pd.read_parquet(out_path, columns=["Year"]))
        print(f"  {label}  SKIP ({rows:,} rows already)")
        skipped += 1
        continue

    print(f"  {label}  downloading {year} Q{quarter} ...")
    success = download_quarter(year, quarter, out_path)

    if success:
        rows = len(pd.read_parquet(out_path, columns=["Year"]))
        size_kb = out_path.stat().st_size // 1024
        elapsed = time.time() - t0
        rate = i / elapsed * 60
        eta_min = (total - i) / rate if rate > 0 else 0
        print(f"  {label}  OK  {rows:,} rows  {size_kb}KB  (ETA ~{eta_min:.0f} min)")
        ok += 1
    else:
        print(f"  {label}  FAILED after all retries")
        failed.append(fname)

    time.sleep(1)

elapsed = time.time() - t0
print(f"\nDone in {elapsed/60:.1f} min: {ok} downloaded, {skipped} skipped, {len(failed)} failed")
if failed:
    print(f"Failed: {failed}")
