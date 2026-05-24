import sqlite3
import pandas as pd
import os
from backend.config import DB_PATH, DATA_RAW_DIR, CSV_FILES
from backend.cleaner import run_all_cleaners

def load_raw_csvs():
    dfs = {}
    for table_name, filename in CSV_FILES.items():
        path = os.path.join(DATA_RAW_DIR, filename)
        if os.path.exists(path):
            dfs[table_name] = pd.read_csv(path, dtype=str)
            print(f"  Loaded {filename}: {len(dfs[table_name])} rows")
        else:
            print(f"  WARNING: {filename} not found")
    return dfs

def write_to_sqlite(clean_dfs):
    conn = sqlite3.connect(DB_PATH)
    for table_name, df in clean_dfs.items():
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        print(f"  Written: {table_name} ({len(df)} rows)")
    conn.close()

def get_connection():
    return sqlite3.connect(DB_PATH)

def get_schema():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    schema = {}
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [{"name": row[1], "type": row[2]} for row in cursor.fetchall()]
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = cursor.fetchone()[0]
        schema[table] = {"columns": columns, "row_count": row_count}
    conn.close()
    return schema

def get_sample_rows(table, n=2):
    conn = get_connection()
    try:
        df = pd.read_sql(f"SELECT * FROM {table} LIMIT {n}", conn)
        conn.close()
        return df.to_dict(orient="records")
    except Exception:
        conn.close()
        return []

def run_query(sql):
    conn = get_connection()
    try:
        df = pd.read_sql(sql, conn)
        conn.close()
        return df
    except Exception as e:
        conn.close()
        raise e

def ingest_pipeline():
    print("\n[EduPulse] Starting ingestion pipeline...")
    raw_dfs = load_raw_csvs()
    clean_dfs, audit = run_all_cleaners(raw_dfs)
    write_to_sqlite(clean_dfs)
    print(f"\n✅ Done. DB at: {DB_PATH}")
    return audit

def db_exists():
    return os.path.exists(DB_PATH)
