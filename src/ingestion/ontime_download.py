import os
import time
import zipfile
import requests
from config import START_YEAR, END_YEAR, END_MONTH, RAW_DATA_PATH

OUTPUT_FOLDER = os.path.join(RAW_DATA_PATH, "zips")
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

BASE_URL = (
    "https://transtats.bts.gov/PREZIP/"
    "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{year}_{month}.zip"
)

REQUIRED_COLUMNS = {
    "Month", "DayOfWeek", "FlightDate",
    "Reporting_Airline", "Flight_Number_Reporting_Airline",
    "Origin", "OriginCityName", "OriginStateName",
    "Dest", "DestCityName", "DestState",
    "CRSDepTime", "DepTime", "DepDelay", "DepDelayMinutes", "TaxiOut",
    "CRSArrTime", "ArrTime", "ArrDelay", "ArrDelayMinutes", "TaxiIn",
    "Cancelled", "CancellationCode", "Diverted",
    "CRSElapsedTime", "ActualElapsedTime", "AirTime", "Distance",
    "CarrierDelay", "WeatherDelay", "NASDelay", "SecurityDelay", "LateAircraftDelay",
}

MAX_RETRIES = 3
RETRY_DELAY = 10


def _csv_columns(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        csv_name = next(n for n in z.namelist() if n.endswith(".csv"))
        with z.open(csv_name) as f:
            header = f.readline().decode("utf-8").strip()
            return {c.strip('"') for c in header.split(",")}


def _download(url, filepath):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, stream=True, timeout=120)
            r.raise_for_status()
            with open(filepath, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
            return True
        except requests.exceptions.HTTPError as e:
            print(f"    HTTP {e.response.status_code} — skipping")
            return False
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < MAX_RETRIES:
                print(f"    Attempt {attempt} failed ({e.__class__.__name__}), retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"    Failed after {MAX_RETRIES} attempts: {e}")
                return False
    return False


# Build the full list of (year, month) pairs
targets = [
    (y, m)
    for y in range(START_YEAR, END_YEAR + 1)
    for m in range(1, 13)
    if not (y == END_YEAR and m > END_MONTH)
]

print(f"Scope: {len(targets)} files  ({START_YEAR}-01 through {END_YEAR}-{END_MONTH:02d})\n")

skipped, downloaded, failed, schema_warnings = 0, 0, [], []

for year, month in targets:
    filename = f"ontime_{year}_{month:02d}.zip"
    filepath = os.path.join(OUTPUT_FOLDER, filename)

    if os.path.exists(filepath):
        print(f"  [skip]  {filename}")
        skipped += 1
        continue

    url = BASE_URL.format(year=year, month=month)
    print(f"  [fetch] {filename} ...", end=" ", flush=True)

    ok = _download(url, filepath)
    if not ok:
        failed.append(filename)
        # Remove partial file if it was created
        if os.path.exists(filepath):
            os.remove(filepath)
        continue

    # Validate schema immediately after download
    try:
        cols = _csv_columns(filepath)
        missing = REQUIRED_COLUMNS - cols
        if missing:
            print(f"SCHEMA MISMATCH — missing: {sorted(missing)}")
            schema_warnings.append((filename, sorted(missing)))
        else:
            print(f"OK ({len(cols)} cols in file)")
    except Exception as e:
        print(f"Could not read zip: {e}")
        schema_warnings.append((filename, ["unreadable"]))

    downloaded += 1

print(f"\n--- Summary ---")
print(f"  Downloaded : {downloaded}")
print(f"  Skipped    : {skipped}")
print(f"  Failed     : {len(failed)}")
print(f"  Schema warn: {len(schema_warnings)}")

if failed:
    print("\nFailed downloads:")
    for f in failed:
        print(f"  {f}")

if schema_warnings:
    print("\nSchema warnings (these files need attention):")
    for fname, missing in schema_warnings:
        print(f"  {fname}: {missing}")
