"""
upload_to_cloud.py
------------------
Copies the raw JSON files to Azure Blob Storage (the "data lake" part).

Why: local files are fine to start, but a cloud copy means the data survives
if my laptop dies, and later steps (Spark, a scheduled job) can read it from
there. Cloud storage is also a skill UK job descriptions ask for.

Setup (once):
1. Create an Azure for Students account (free credit, uses your uni email).
2. In the Azure portal: create a Storage Account, then a container named "raw".
3. Storage Account -> Access keys -> copy the Connection string.
4. Copy .env.example to .env and paste the connection string in.
   NEVER commit .env to GitHub (it is already in .gitignore).

Run:  python upload_to_cloud.py
"""

import logging
import os
from pathlib import Path

from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

RAW_DIR = Path("data/raw")
CONTAINER = os.getenv("AZURE_CONTAINER", "raw")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("upload_to_cloud")


def main() -> None:
    load_dotenv()  # reads the .env file into environment variables
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        raise SystemExit("Set AZURE_STORAGE_CONNECTION_STRING in your .env file first.")

    service = BlobServiceClient.from_connection_string(conn_str)
    container = service.get_container_client(os.getenv("AZURE_CONTAINER", CONTAINER))

    uploaded = skipped = 0
    for path in sorted(RAW_DIR.glob("*/readings_*.json")):
        blob_name = path.relative_to(RAW_DIR).as_posix()   # e.g. 2026-10-06/readings_120000.json
        blob = container.get_blob_client(blob_name)
        if blob.exists():
            skipped += 1                                   # already in the cloud
            continue
        with path.open("rb") as f:
            blob.upload_blob(f)
        uploaded += 1

    log.info("Uploaded %d new files, skipped %d already in the cloud.", uploaded, skipped)


if __name__ == "__main__":
    main()
