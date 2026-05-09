"""
Download NOAA Local Climatological Data (LCD) for IAD, DCA, BWI.

One CSV per station per year (~10 MB each). We stream each file, filter to
FM-15 METAR rows (standard hourly aviation observations), keep only the
columns we need, and save a single parquet per station to data/raw/noaa/.

Station IDs (USAF + WBAN format):
  IAD (Dulles)  : 72403093738
  DCA (Reagan)  : 72405013743
  BWI           : 72406093721

Run time: ~5-10 min depending on connection.
"""
import io
import sys
import time
import requests
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import RAW_DATA_PATH, START_YEAR, END_YEAR

OUT_DIR = Path(RAW_DATA_PATH) / "noaa"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = (
    "https://www.ncei.noaa.gov/data/local-climatological-data/access"
    "/{year}/{station_id}.csv"
)

STATIONS = {
    "IAD": "72403093738",
    "DCA": "72405013743",
    "BWI": "72406093721",
}

# FM-15 = standard hourly METAR (one per hour, at :52 or :56 past)
# FM-16 = special METAR (condition change); excluded to keep one row/hour
REPORT_TYPE = "FM-15"

KEEP_COLS = [
    "STATION",
    "DATE",
    "REPORT_TYPE",
    "HourlyDryBulbTemperature",
    "HourlyVisibility",
    "HourlyWindSpeed",
    "HourlyWindGustSpeed",
    "HourlyPrecipitation",
    "HourlyPresentWeatherType",
    "HourlySkyConditions",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def _clean_numeric(series: pd.Series) -> pd.Series:
    """Replace trace 'T' with 0.005, strip '+' suffixes, coerce to float."""
    s = series.astype(str).str.strip()
    s = s.replace("T", "0.005")
    s = s.str.rstrip("+")
    s = s.str.split("s").str[0]   # "10SM" visibility → "10"
    return pd.to_numeric(s, errors="coerce")


def download_year(airport: str, station_id: str, year: int) -> pd.DataFrame | None:
    url = BASE_URL.format(year=year, station_id=station_id)
    try:
        r = requests.get(url, headers=HEADERS, timeout=120)
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"    HTTP {e.response.status_code} — skipping")
        return None
    except Exception as e:
        print(f"    Error: {e} — skipping")
        return None

    raw = io.BytesIO(r.content)
    df = pd.read_csv(raw, low_memory=False, on_bad_lines="skip")

    # Filter to standard hourly observations only
    df = df[df["REPORT_TYPE"].astype(str).str.strip() == REPORT_TYPE]

    # Keep only columns that exist in this file
    cols = [c for c in KEEP_COLS if c in df.columns]
    df = df[cols].copy()

    # Parse DATE
    df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")

    # Clean numeric columns
    for col in ["HourlyDryBulbTemperature", "HourlyVisibility",
                "HourlyWindSpeed", "HourlyWindGustSpeed", "HourlyPrecipitation"]:
        if col in df.columns:
            df[col] = _clean_numeric(df[col])

    # Tag with airport code for convenience
    df.insert(0, "Airport", airport)

    return df.reset_index(drop=True)


years = list(range(START_YEAR, END_YEAR + 1))
print(f"NOAA LCD downloader: {len(STATIONS)} stations × {len(years)} years\n")

for airport, station_id in STATIONS.items():
    out_path = OUT_DIR / f"noaa_{airport.lower()}.parquet"

    frames = []
    print(f"{'='*50}")
    print(f"{airport}  ({station_id})  ->  {out_path.name}")
    print(f"{'='*50}")

    for year in years:
        print(f"  {year} ...", end=" ", flush=True)
        df = download_year(airport, station_id, year)
        if df is not None:
            frames.append(df)
            print(f"{len(df):,} rows")
        time.sleep(0.5)   # polite delay

    if not frames:
        print(f"  No data downloaded for {airport}")
        continue

    combined = pd.concat(frames, ignore_index=True)
    print(f"\n  Total: {len(combined):,} rows")
    print(f"  Date range: {combined['DATE'].min()} -> {combined['DATE'].max()}")
    print(f"  Saving to {out_path} ...")
    combined.to_parquet(out_path, index=False, engine="pyarrow")
    print(f"  Parquet size: {out_path.stat().st_size / 1e6:.1f} MB\n")

print("Done.")
