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

- [x] Week 1: raw ingestion script (Extract)
- [x] Week 2 (started): clean + load into SQLite (Transform + Load), starter SQL queries, Azure upload script
- [ ] Week 2: collect data for a few days, answer the first SQL questions, move SQLite to Postgres
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
- Windows: Task Scheduler, repeat the task every 15 minutes

Tip: your laptop must be awake for this to run. A free-tier cloud VM later
avoids gaps.

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

(Add one entry whenever something breaks: duplicates, rate limits, schema
changes. These are your best interview stories.)

## What I'd improve next

(Fill in at the end.)
