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
thousands of river-level, groundwater, tidal and rainfall stations.

## Architecture

```
EA API -> ingest_flood.py -> raw JSON (data/raw/<date>/)        [Extract]
       -> etl_load.py     -> SQLite (data/flood.db, table readings)  [Transform + Load]
       -> SQL queries (queries.sql)                             [Analysis]

Planned: Postgres, Azure Blob storage, dbt tests, orchestrator, PySpark, dashboard, Docker
```

## Status

- [x] Extract: ingestion script fetches the API and saves untouched raw JSON
- [x] Transform and load: idempotent loader (safe to re-run, no duplicate rows)
- [x] Scheduling: runs every 15 minutes on Windows (Task Scheduler, since 10 Oct 2026)
- [x] First data quality checks in SQL, and several real data bugs found and fixed
- [x] First analysis query: which river stations rise most in a day
- [ ] Fix the laptop battery setting so collection continues on battery
- [ ] Postgres, cloud storage, dbt tests, orchestrator (next version)

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate           # Windows
pip install -r requirements.txt
python ingest_flood.py           # Extract: fetch from the API, save raw JSON
python etl_load.py               # Transform + Load: clean into data/flood.db (safe to re-run)
```

Raw files appear in `data/raw/<date>/`. Open `data/flood.db` in DB Browser for
SQLite (read-only mode recommended) and run the queries in `queries.sql`.

### Run every 15 minutes (Windows)

`run_pipeline.bat` runs both scripts in order. It is registered with Task Scheduler:

```
schtasks /create /tn "FloodPipeline" /sc minute /mo 15 /tr "C:\path\to\run_pipeline.bat"
```

By default this task will not start on battery power. The laptop must also be
awake and online for runs to happen.

## Design decisions

| Decision | Choice | Why | What I tried that failed |
|---|---|---|---|
| Batch vs streaming | Batch every 15 min | The source updates every 15 min, so streaming adds nothing | |
| Raw storage | Untouched JSON files | The database can always be rebuilt from raw data | |
| Load idempotency | Primary key (measure_id, reading_time) + `INSERT OR IGNORE`, plus a `loaded_files` table | Re-running never creates duplicates | |
| First database | SQLite | No install needed, standard SQL | |
| Next database | Postgres | Closer to production use | |

## Data quality findings

These problems were found in the stored data. Each one has a rule used in analysis.

| Problem | Example | Rule used |
|---|---|---|
| Sentinel value for flow | Station E2834 reports -10.0 when it has no reading | Treated as missing |
| Sentinel value for temperature | Station 3275 reports -25.0 in all 7 of its readings | Treated as missing; temperature is not used in the analysis |
| Impossible levels from broken sensors | E27464 (-92 m), ST99_74 (-20 to 92 m), E72825 (5,289 to 12,556 m) | Station excluded from river analysis |
| "level" mixes several kinds of sensor | Groundwater (`groundwater`), tidal (`tidal_level`), and river stage (`stage`, `downstage`) all use the name "level" | Analysis keeps only `stage` and `downstage` |
| Mixed units under one name | `flow` has m3/s and Ml/d; `level` has mASD, mAOD and m | Unit must be filtered before comparing values; not yet split into a column |
| Wind direction and speed in one type | `wind` mixes degrees and speed | Not used in the analysis; to be split later |
| Gaps in collection | Laptop off at night; battery default skips runs | Only partly fixed; see "Next steps" |
| Stations that stop updating | Each fetch includes repeated old readings | Primary key skips duplicates |

## Problems I hit and how I fixed them

- **List-valued readings:** some tidal stations return a list of numbers in `value`
  instead of one number. The transform takes the first value.
- **Wrong measurement type (found 13 Oct):** some station IDs have a region name in
  second place (for example `E1901-anglian-level-stage-...`), so my parser read the
  region as the type. I fixed the parser and rebuilt the database from the raw JSON,
  which was possible because the raw data is kept untouched. About 6 of 35,000
  readings still carry an odd label (`T_TG_341`) that I have not investigated.
- **Sentinel and impossible values (found 20 Oct):** I found -10.0 flow, -25.0
  temperature, and river levels of -92 m and 12,556 m. My first outlier check used a
  fixed range (-5 to 20 m), which was too crude: it flagged 552 stations, most of them
  correct, because levels are reported against different datums. The fix was to check
  each station against itself and to filter by sensor type.
- **Gaps in the data:** nothing was collected between 7 and 10 Oct, before the
  schedule existed. Runs are skipped when the laptop is off or on battery. The API
  returns only the latest reading, so missed runs cannot be re-fetched.
- **Stations that stop reporting:** each fetch includes around 80 to 100 readings
  identical to ones already stored. The primary key skips them.

## Next steps

- Fix the Task Scheduler battery setting, so collection continues on battery
- Split `flow` and `level` by unit into their own column (`unit`)
- Add a `fetched_at` column, so the time of collection is kept separately from sensor time
- Investigate `T_TG_341` and the odd station 48143 downstage reading (-13 m)
- Build the next version: Postgres, cloud storage, dbt tests, orchestrator
