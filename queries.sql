-- queries.sql
-- Starter queries for data/flood.db. Run them with any SQLite tool, for example:
--   sqlite3 data/flood.db < queries.sql
-- or open data/flood.db in "DB Browser for SQLite" (free) and paste them in.

-- 1. How much data do I have, by type of measurement?
SELECT parameter,
       COUNT(*)                       AS readings,
       COUNT(DISTINCT station_ref)    AS stations
FROM readings
GROUP BY parameter
ORDER BY readings DESC;

-- 2. Data volume per day (shows if my collection had gaps).
SELECT substr(reading_time, 1, 10) AS day,
       COUNT(*)                    AS readings
FROM readings
GROUP BY day
ORDER BY day;

-- 3. Data quality check: how many readings have no usable value?
SELECT parameter,
       COUNT(*)                                          AS total,
       SUM(CASE WHEN value IS NULL THEN 1 ELSE 0 END)    AS missing_value
FROM readings
GROUP BY parameter;

-- 4. Highest river levels seen so far (top 10 stations).
SELECT station_ref, MAX(value) AS max_level
FROM readings
WHERE parameter = 'level'
GROUP BY station_ref
ORDER BY max_level DESC
LIMIT 10;

-- 5. The question behind the project (a first, simple version):
--    which stations saw their level rise the most within a single day?
--    Later this becomes a rain-vs-level response-time analysis in PySpark.
SELECT station_ref,
       substr(reading_time, 1, 10)      AS day,
       MAX(value) - MIN(value)          AS daily_rise
FROM readings
WHERE parameter = 'level' AND value IS NOT NULL
GROUP BY station_ref, day
ORDER BY daily_rise DESC
LIMIT 20;
