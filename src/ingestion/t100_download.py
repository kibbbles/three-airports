"""
Download BTS T-100 Segment All Carriers data (table FMG) for 2015–2026 Jan.

Downloads one zip per year (all months) for 2015–2025, then January 2026 separately.
Saves to data/raw/t100/. Skips files that already exist and are valid zips.
"""
import re
import sys
import time
import zipfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import RAW_DATA_PATH, START_YEAR, END_YEAR, END_MONTH

FORM_URL = (
    "https://www.transtats.bts.gov/DL_SelectFields.aspx"
    "?gnoyr_VQ=FMG&QO_fu146_anzr=Nv4+Pn44vr45"
)

FIELDS = [
    "YEAR", "QUARTER", "MONTH",
    "UNIQUE_CARRIER", "UNIQUE_CARRIER_NAME",
    "ORIGIN", "ORIGIN_CITY_NAME", "ORIGIN_COUNTRY", "ORIGIN_COUNTRY_NAME", "ORIGIN_WAC",
    "DEST",  "DEST_CITY_NAME",   "DEST_COUNTRY",   "DEST_COUNTRY_NAME",   "DEST_WAC",
    "PASSENGERS", "SEATS", "FREIGHT", "DISTANCE", "DEPARTURES_PERFORMED",
    "AIRCRAFT_GROUP", "AIRCRAFT_TYPE", "CLASS",
]

OUT_DIR = Path(RAW_DATA_PATH) / "t100"
OUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.transtats.bts.gov/",
}


def extract_hidden(html, name):
    m = re.search(rf'id="{name}"[^>]*value="([^"]*)"', html)
    if not m:
        m = re.search(rf'name="{name}"[^>]*value="([^"]*)"', html)
    return m.group(1) if m else ""


def download_one(year: int, period: str, out_path: Path, retries: int = 3) -> bool:
    """
    Download one T-100 zip for the given year and period ("All" or "1"–"12").
    Returns True on success.
    """
    for attempt in range(1, retries + 1):
        try:
            session = requests.Session()
            session.headers.update(HEADERS)

            r = session.get(FORM_URL, timeout=30)
            r.raise_for_status()

            viewstate   = extract_hidden(r.text, "__VIEWSTATE")
            vsgenerator = extract_hidden(r.text, "__VIEWSTATEGENERATOR")
            eventval    = extract_hidden(r.text, "__EVENTVALIDATION")

            post_data = {
                "affiliate":            "dot-bts",
                "__EVENTTARGET":        "",
                "__EVENTARGUMENT":      "",
                "__LASTFOCUS":          "",
                "__VIEWSTATE":          viewstate,
                "__VIEWSTATEGENERATOR": vsgenerator,
                "__EVENTVALIDATION":    eventval,
                "cboGeography":         "All",
                "cboYear":              str(year),
                "cboPeriod":            period,
                "btnDownload":          "Download",
            }
            for field in FIELDS:
                post_data[field] = field

            r2 = session.post(FORM_URL, data=post_data, timeout=180, stream=True)
            r2.raise_for_status()

            if "application/zip" not in r2.headers.get("content-type", ""):
                raise ValueError(
                    f"Unexpected content-type: {r2.headers.get('content-type')}"
                )

            tmp = out_path.with_suffix(".tmp")
            with open(tmp, "wb") as f:
                for chunk in r2.iter_content(chunk_size=65536):
                    f.write(chunk)

            with zipfile.ZipFile(tmp) as z:
                z.namelist()  # raises if not a valid zip

            tmp.rename(out_path)
            return True

        except Exception as e:
            print(f"    attempt {attempt}/{retries} failed: {e}")
            if tmp.exists():
                tmp.unlink()
            if attempt < retries:
                time.sleep(5 * attempt)

    return False


def is_valid_zip(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path):
            return True
    except Exception:
        return False


def build_work_list():
    """Build list of (year, period, filename) to download."""
    work = []
    for year in range(START_YEAR, END_YEAR):        # 2015–2025 full years
        work.append((year, "All", f"t100_{year}.zip"))
    # END_YEAR = 2026, END_MONTH = 1
    work.append((END_YEAR, str(END_MONTH), f"t100_{END_YEAR}_{END_MONTH:02d}.zip"))
    return work


work_list = build_work_list()
total = len(work_list)
print(f"T-100 downloader: {total} files to check in {OUT_DIR}\n")

ok, skipped, failed = 0, 0, []

for i, (year, period, fname) in enumerate(work_list, 1):
    out_path = OUT_DIR / fname
    label = f"[{i:2d}/{total}] {fname}"

    if out_path.exists() and is_valid_zip(out_path):
        size = out_path.stat().st_size
        print(f"  {label}  SKIP (already downloaded, {size:,} bytes)")
        skipped += 1
        continue

    print(f"  {label}  downloading year={year} period={period} ...")
    success = download_one(year, period, out_path)

    if success:
        size = out_path.stat().st_size
        print(f"  {label}  OK  {size:,} bytes")
        ok += 1
    else:
        print(f"  {label}  FAILED after all retries")
        failed.append(fname)

    time.sleep(2)  # polite delay between requests

print(f"\nDone: {ok} downloaded, {skipped} skipped, {len(failed)} failed")
if failed:
    print(f"Failed files: {failed}")
