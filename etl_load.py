"""
etl_load.py
-----------
The T (transform) and L (load) of the pipeline.

    ingest_flood.py  ->  data/raw/<date>/readings_*.json   (Extract)
    etl_load.py      ->  data/flood.db  table "readings"   (Transform + Load)

What it does:
1. Finds raw JSON files that have not been loaded yet.
2. Cleans each reading (parses the measure ID, handles odd values).
3. Inserts into a SQL table. Duplicates are ignored, so running this script
   twice never creates double rows (this property is called "idempotent",
   and interviewers like it).

I use SQLite now because it needs no installation. The SQL is standard, so
moving to Postgres later is a small change (see README).

Run:  python etl_load.py
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

RAW_DIR = Path("data/raw")
DB_PATH = Path("data/flood.db")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("etl_load")

# Environment Agency region names that can appear inside a measure ID.
# If a new one shows up as a "parameter" in the data, add it here.
REGIONS = {
    "anglian", "thames", "southern", "north_west", "north_east",
    "midlands", "south_west", "south_east", "wessex", "yorkshire",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    measure_id   TEXT NOT NULL,   -- e.g. 3680-level-stage-i-15_min-m
    station_ref  TEXT NOT NULL,   -- e.g. 3680
    parameter    TEXT NOT NULL,   -- level, rainfall, flow, ...
    reading_time TEXT NOT NULL,   -- ISO 8601 UTC, e.g. 2026-10-06T12:00:00Z
    value        REAL,            -- NULL when the API gave no usable number
    PRIMARY KEY (measure_id, reading_time)   -- this is what blocks duplicates
);

-- Remember which files are done, so a re-run skips them.
CREATE TABLE IF NOT EXISTS loaded_files (
    file_path    TEXT PRIMARY KEY,
    loaded_at    TEXT NOT NULL,
    rows_in_file INTEGER NOT NULL,
    rows_new     INTEGER NOT NULL
);
"""


def transform_item(item: dict):
    """Turn one raw API item into a clean row (a tuple), or None if unusable."""
    measure_url = item.get("measure")
    reading_time = item.get("dateTime")
    if not measure_url or not reading_time:
        return None  # cannot identify the reading, so skip it

    # The measure is a URL; the last part is the ID, e.g. "3680-level-stage-i-15_min-m".
    # Assumption: it starts with <station_ref>-<parameter>-...
    measure_id = str(measure_url).rsplit("/", 1)[-1]
    parts = measure_id.split("-")
    station_ref = parts[0]
    # Bug found on 13 Oct: some IDs have an EA region name in second place,
    # e.g. "E1901-anglian-level-stage-...". The real type is then the third part.
    type_index = 1
    if len(parts) > 2 and parts[1].lower() in REGIONS:
        type_index = 2
    parameter = parts[type_index] if len(parts) > type_index else "unknown"

    # Quirk: for some stations the API returns a LIST of values instead of one number.
    value = item.get("value")
    if isinstance(value, list):
        value = value[0] if value else None
    try:
        value = float(value) if value is not None else None
    except (TypeError, ValueError):
        value = None

    return (measure_id, station_ref, parameter, str(reading_time), value)


def load_file(conn: sqlite3.Connection, path: Path) -> None:
    """Load one raw JSON file into the readings table."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as err:
        log.error("Skipping unreadable file %s: %s", path, err)
        return

    items = payload.get("items", [])
    rows = [r for r in (transform_item(i) for i in items) if r is not None]

    before = conn.total_changes
    conn.executemany(
        "INSERT OR IGNORE INTO readings "
        "(measure_id, station_ref, parameter, reading_time, value) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    rows_new = conn.total_changes - before   # ignored duplicates are not counted

    conn.execute(
        "INSERT INTO loaded_files (file_path, loaded_at, rows_in_file, rows_new) VALUES (?, ?, ?, ?)",
        (path.as_posix(), datetime.now(timezone.utc).isoformat(), len(items), rows_new),
    )
    conn.commit()
    log.info("%s: %d items, %d clean, %d new rows", path.name, len(items), len(rows), rows_new)


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)

    done = {r[0] for r in conn.execute("SELECT file_path FROM loaded_files")}
    files = [f for f in sorted(RAW_DIR.glob("*/readings_*.json")) if f.as_posix() not in done]

    if not files:
        log.info("Nothing new to load.")
    for f in files:
        load_file(conn, f)

    total = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    log.info("Table 'readings' now has %d rows.", total)
    conn.close()


if __name__ == "__main__":
    main()
