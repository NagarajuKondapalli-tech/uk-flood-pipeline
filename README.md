# UK River & Rainfall Pipeline

## The question

**Which UK rivers respond fastest to heavy rain, and can we spot rising flood risk earlier?**

## Who it is for

A council flood-response team (or an informed resident) who needs to know which
river stations react quickly to rainfall, so warnings and sandbags go to the
right places first.

## Data source

[Environment Agency Real Time flood-monitoring API](https://environment.data.gov.uk/flood-monitoring/doc/reference)
(free, no key, England only). Readings arrive roughly every 15 minutes from
thousands of river-level and rainfall stations.

## Architecture (planned)

```
EA API -> Python ingest -> raw JSON (local, then Azure Blob)
       -> Postgres (staging) -> dbt models + tests
       -> PySpark job (response-time analysis over full history)
       -> Streamlit dashboard
Orchestration: Prefect or Airflow, packaged with Docker
```

## Status

- [x] Week 1: raw ingestion script (Extract), code on GitHub
- [x] Week 2 (done so far): clean + load into SQLite (Transform + Load), automatic 15-minute collection on Windows (since 10 Oct 2026), first SQL checks, first data bug found and fixed
- [ ] Week 2: collect more data, answer the first SQL questions, move SQLite to Postgres
- [ ] Week 3: dbt models, data tests, failure handling
- [ ] Week 4: Azure Blob storage, orchestrator
- [ ] Week 5: PySpark job, Streamlit dashboard
- [ ] Week 6: Docker, diagram, final README

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python ingest_flood.py
```

Raw files appear in `data/raw/<date>/`.

### The full ETL, step by step

```bash
python ingest_flood.py     # E: fetch from the API, save raw JSON
python etl_load.py         # T+L: clean and load into data/flood.db (safe to re-run)
sqlite3 data/flood.db < queries.sql    # or open data/flood.db in DB Browser for SQLite
python upload_to_cloud.py  # copy raw files to Azure Blob (needs .env, see below)
```

`sample_readings.json` is a tiny fake file with awkward cases (a list-valued
reading, a missing value, a row with no measure). Copy it into
`data/raw/<any-date>/readings_000000.json` to try `etl_load.py` without waiting
for real data.

### Cloud setup (Azure for Students)

1. Create a Storage Account and a container called `raw`.
2. Copy its connection string into a `.env` file (copy `.env.example`). `.env` is git-ignored.
3. Run `python upload_to_cloud.py`. Files already in the cloud are skipped.

### Run every 15 minutes (until the orchestrator is built)

- Mac/Linux: add `*/15 * * * * cd /path/to/project && .venv/bin/python ingest_flood.py` via `crontab -e`
- Windows: `run_pipeline.bat` runs both scripts in order. Register it with
  `schtasks /create /tn "FloodPipeline" /sc minute /mo 15 /tr "C:\path\to\run_pipeline.bat"`

Tip: your laptop must be awake for this to run. A free-tier cloud VM later
avoids gaps. By default a task created this way will not start on battery
power (see "Problems I hit").

## Design decisions (fill in as I go)

| Decision | Choice | Why | What I tried that failed |
|---|---|---|---|
| Batch vs streaming | Batch every 15 min | Source updates every 15 min, streaming adds nothing | |
| Raw storage | Untouched JSON files | Can always reprocess | |
| Load idempotency | Primary key (measure_id, reading_time) + `INSERT OR IGNORE`, and a `loaded_files` table | Re-running never creates duplicates | |
| First database | SQLite | No install needed, standard SQL, so I can start today | |
| Warehouse (later) | Postgres | | |

## Problems I hit and how I fixed them

- **List-valued readings:** for some stations (tidal ones) the API returns a
  list of numbers in `value` instead of one number. The transform step takes
  the first value so the column stays numeric.
- **Wrong measurement type for some stations (found 13 Oct):** a SQL count by
  type showed values like `anglian`, `thames`, `north_west` and `southern`
  where `level`, `rainfall` or `flow` should be. Some station IDs have an
  Environment Agency region name in second place (for example
  `E1901-anglian-level-stage-i-15_min-mASD`), and my code assumed the type was
  always second. I fixed the parsing, then rebuilt the database from the raw
  JSON files, which is only possible because the raw data is kept untouched.
  A few readings (about 6 of 35,000) still carry an odd label (`T_TG_341`) and
  are still to be investigated.
- **Gaps in the data:** the laptop is switched off at night, and the Windows task
  created with `schtasks` defaults to "No Start On Batteries", so runs were
  skipped when unplugged. Nothing was collected between 7 and 10 Oct, before
  the schedule existed. The API only returns the latest reading, so missed
  runs cannot simply be re-fetched.
- **Stations that stop reporting:** each fetch includes around 80 to 100
  readings that are identical to ones already stored (stations that have not
  updated). The primary key on (measure_id, reading_time) skips them, so no
  duplicates are created.

(Add one entry whenever something breaks: duplicates, rate limits, schema
changes. These are your best interview stories.)

## What I'd improve next

- Run the pipeline on an always-on cloud machine so there are no gaps
- Add a backfill step to fill gaps (to be checked against the API documentation)
- Look into the remaining odd `T_TG_341` rows
- Add automated data quality tests
