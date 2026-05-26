# =============================================================================
# ingest_db.py  —  STEP 1: Load all CSVs into SQLite
# =============================================================================
# Handles large files like sales.csv by reading in CHUNKS instead of
# loading the entire file into memory at once.
#
# How chunking works:
#   Instead of: read ALL 3 million rows at once → crash
#   We do:      read 50,000 rows → write to DB → read next 50,000 → repeat
#   The DB table builds up gradually and your RAM stays happy.
#
# Run this FIRST before anything else.
# =============================================================================

import os
import time
import logging
import pandas as pd
from sqlalchemy import create_engine

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR  = os.path.join(BASE_DIR, "data")
LOG_DIR   = os.path.join(BASE_DIR, "logs")
DB_PATH   = os.path.join(BASE_DIR, "inventory.db")

os.makedirs(LOG_DIR, exist_ok=True)

# ── Logging: writes to file AND prints to screen ──────────────────────────────
logging.basicConfig(
    filename = os.path.join(LOG_DIR, "ingestion.log"),
    level    = logging.DEBUG,
    format   = "%(asctime)s | %(levelname)-8s | %(message)s",
    filemode = "a",
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s"))
logging.getLogger("").addHandler(console)

# ── Database engine ───────────────────────────────────────────────────────────
engine = create_engine(f"sqlite:///{DB_PATH}")
logging.info("Database: %s", DB_PATH)

# ── Settings ──────────────────────────────────────────────────────────────────
CHUNK_SIZE       = 50_000          # rows per chunk
LARGE_FILE_LIMIT = 50 * 1024 * 1024   # 50 MB threshold — anything bigger gets chunked


# =============================================================================
# INGEST SMALL FILE — load whole CSV at once
# =============================================================================
def ingest_small(path, table_name, engine):
    """Read the whole CSV into memory and write to SQLite in one shot."""
    df = pd.read_csv(path, encoding="utf-8", low_memory=False)
    logging.debug("  Columns: %s", list(df.columns))
    df.to_sql(table_name, engine, index=False, if_exists="replace")
    logging.info("  OK %-32s  %8d rows  %d cols  [single load]",
                 table_name, len(df), df.shape[1])
    return len(df), df.shape[1]


# =============================================================================
# INGEST LARGE FILE — read in chunks, append chunk by chunk
# =============================================================================
def ingest_chunked(path, table_name, engine, chunksize=CHUNK_SIZE):
    """
    Read CSV in chunks of `chunksize` rows.
    First chunk  → if_exists='replace'  (creates the table fresh)
    Later chunks → if_exists='append'   (adds rows without wiping the table)
    This way only 50,000 rows are ever in memory at one time.
    """
    total_rows = 0
    chunk_num  = 0
    num_cols   = 0

    logging.info("  Chunked mode — %s rows per chunk", f"{chunksize:,}")

    for chunk in pd.read_csv(
        path, encoding="utf-8", low_memory=False, chunksize=chunksize
    ):
        write_mode = "replace" if chunk_num == 0 else "append"
        chunk.to_sql(table_name, engine, index=False, if_exists=write_mode)

        total_rows += len(chunk)
        num_cols    = chunk.shape[1]
        chunk_num  += 1

        # Live progress bar in the terminal
        print(f"    chunk {chunk_num:>4}  |  rows loaded: {total_rows:>10,}", end="\r")

    print()  # move to new line after progress
    logging.info("  OK %-32s  %8d rows  %d cols  [%d chunks]",
                 table_name, total_rows, num_cols, chunk_num)
    return total_rows, num_cols


# =============================================================================
# MAIN — loop every CSV in data/
# =============================================================================
def load_raw_data():
    start = time.time()
    logging.info("=" * 60)
    logging.info("INGESTION STARTED")
    logging.info("=" * 60)

    # Validate data folder
    if not os.path.exists(DATA_DIR):
        logging.error("data/ folder not found: %s", DATA_DIR)
        return

    csv_files = sorted([f for f in os.listdir(DATA_DIR) if f.endswith(".csv")])

    if not csv_files:
        logging.error("No CSV files found in %s", DATA_DIR)
        return

    logging.info("Files found (%d): %s", len(csv_files), csv_files)
    print(f"\n{'='*60}")
    print(f"  Loading {len(csv_files)} CSV files into inventory.db")
    print(f"  Files > 50 MB are automatically read in {CHUNK_SIZE:,}-row chunks")
    print(f"{'='*60}\n")

    success, failed = [], []

    for file in csv_files:
        path       = os.path.join(DATA_DIR, file)
        table_name = os.path.splitext(file)[0].replace(" ", "_").lower()
        size_mb    = os.path.getsize(path) / (1024 * 1024)
        mode       = "CHUNKED" if os.path.getsize(path) > LARGE_FILE_LIMIT else "SINGLE"

        print(f"  [{mode:6}]  {file:45s}  {size_mb:6.1f} MB")
        logging.info("Loading [%s]: %s  (%.1f MB)", mode, file, size_mb)

        try:
            if os.path.getsize(path) > LARGE_FILE_LIMIT:
                rows, cols = ingest_chunked(path, table_name, engine)
            else:
                rows, cols = ingest_small(path, table_name, engine)

            success.append({
                "table"  : table_name,
                "rows"   : rows,
                "cols"   : cols,
                "size_mb": round(size_mb, 1),
                "mode"   : mode,
            })
            print(f"           ✅  {rows:>10,} rows written\n")

        except Exception as e:
            logging.error("FAILED — %s: %s", file, e)
            failed.append(file)
            print(f"           ❌  FAILED: {e}\n")

    # ── Final summary ─────────────────────────────────────────────────────────
    elapsed = round(time.time() - start, 2)

    logging.info("=" * 60)
    logging.info("INGESTION COMPLETE — %.2fs", elapsed)
    for s in success:
        logging.info("  %-35s  %9d rows  %d cols  [%s]",
                     s["table"], s["rows"], s["cols"], s["mode"])
    if failed:
        logging.warning("  FAILED: %s", failed)
    logging.info("=" * 60)

    print(f"{'='*60}")
    print(f"  INGESTION COMPLETE  ({elapsed}s)")
    print(f"{'='*60}")
    print(f"  {'Table':<35}  {'Rows':>10}  {'Size':>8}  Mode")
    print(f"  {'-'*60}")
    for s in success:
        print(f"  {s['table']:<35}  {s['rows']:>10,}  {s['size_mb']:>6.1f} MB  {s['mode']}")
    if failed:
        print(f"\n  ⚠️  Failed: {failed}")
    print(f"\n  DB  : {DB_PATH}")
    print(f"  Log : {os.path.join(LOG_DIR, 'ingestion.log')}")
    print(f"{'='*60}")
   


if __name__ == "__main__":
    load_raw_data()