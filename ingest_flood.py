"""
ingest_flood.py
---------------
Fetches the latest readings from ALL Environment Agency monitoring stations
(river levels, rainfall, flow, etc.) and saves the response untouched as JSON.

Why save it untouched? Keeping the "raw" data exactly as received means that if
I make a mistake in cleaning later, I can always re-run the transformations
from the original. This is a core data engineering habit.

Run it once:      python ingest_flood.py
Run every 15 min: see the scheduling note in README.md
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# --- Settings ---------------------------------------------------------------
# This endpoint returns the most recent reading for every station. No API key needed.
API_URL = "https://environment.data.gov.uk/flood-monitoring/data/readings"
PARAMS = {"latest": ""}        # "?latest" asks for only the newest reading per measure
RAW_DIR = Path("data/raw")     # raw files are written here
MAX_RETRIES = 4                # how many times to try if the API fails
TIMEOUT_SECONDS = 30           # give up on a single request after this long

# --- Logging ----------------------------------------------------------------
# Logging (instead of print) gives timestamps and levels. Useful when the
# script runs unattended and you need to see what went wrong later.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("ingest_flood")


def fetch_latest_readings() -> dict:
    """Call the API, retrying with a growing wait if it fails."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(API_URL, params=PARAMS, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()   # raises an error for 4xx/5xx status codes
            return response.json()
        except requests.RequestException as err:
            wait = 2 ** attempt           # 2, 4, 8, 16 seconds (exponential backoff)
            log.warning("Attempt %d/%d failed: %s", attempt, MAX_RETRIES, err)
            if attempt == MAX_RETRIES:
                raise                     # out of retries, let the failure be visible
            log.info("Waiting %d seconds before retrying", wait)
            time.sleep(wait)


def save_raw(payload: dict) -> Path:
    """Write the payload to data/raw/YYYY-MM-DD/readings_HHMMSS.json."""
    now = datetime.now(timezone.utc)      # always store time in UTC, convert later
    folder = RAW_DIR / now.strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"readings_{now.strftime('%H%M%S')}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def main() -> None:
    payload = fetch_latest_readings()
    items = payload.get("items", [])
    path = save_raw(payload)
    log.info("Saved %d readings to %s", len(items), path)


if __name__ == "__main__":
    main()
