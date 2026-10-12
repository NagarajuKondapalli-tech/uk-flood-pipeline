@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe ingest_flood.py
.venv\Scripts\python.exe etl_load.py
