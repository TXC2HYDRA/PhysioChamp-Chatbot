#!/usr/bin/env python3
import os
import json
import mysql.connector
from mysql.connector import Error

# Environment-driven config
MYSQL_HOST = os.getenv("MYSQL_HOST", "10.173.222.60")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_DB   = os.getenv("MYSQL_DB", "Physiochamp")
MYSQL_USER = os.getenv("MYSQL_USER", "rag_user")
MYSQL_PASS = os.getenv("MYSQL_PASSWORD", "root")

OUTPUT_FILE = os.getenv("SCHEMA_SNAPSHOT_FILE", "schema_snapshot.json")
ROW_SAMPLE_COUNT = int(os.getenv("ROW_SAMPLE_COUNT", "2"))

def get_connection():
    return mysql.connector.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        database=MYSQL_DB,
        user=MYSQL_USER,
        password=MYSQL_PASS,
        autocommit=True,
    )

def rows_to_dicts(cursor):
    """Convert the current cursor resultset into a list of dicts with string keys."""
    cols = [str(desc[0]) for desc in (cursor.description or [])]
    out = []
    for r in cursor.fetchall():
        # Ensure all values are JSON-serializable; fallback to str()
        row_obj = {}
        for c, v in zip(cols, r):
            # Convert bytes/bytearray to string and other non-serializable to str
            if isinstance(v, (bytes, bytearray)):
                try:
                    row_obj[c] = v.decode("utf-8", errors="replace")
                except Exception:
                    row_obj[c] = str(v)
            else:
                try:
                    json.dumps(v, default=str)  # probe
                    row_obj[c] = v
                except TypeError:
                    row_obj[c] = str(v)
        out.append(row_obj)
    return out

def fetch_all_tables(conn):
    sql = """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = %s
    ORDER BY table_name
    """
    cur = conn.cursor()
    cur.execute(sql, (MYSQL_DB,))
    tables = [r[0] for r in cur.fetchall()]
    cur.close()
    return tables

def fetch_columns(conn, table_name):
    sql = f"SHOW COLUMNS FROM `{MYSQL_DB}`.`{table_name}`"
    cur = conn.cursor()
    cur.execute(sql)
    # Columns: Field, Type, Null, Key, Default, Extra
    cols = []
    for field, ctype, nullable, ckey, default, extra in cur.fetchall():
        cols.append({
            "name": str(field),
            "type": str(ctype),
            "nullable": str(nullable),
            "key": str(ckey),
            "default": None if default is None else str(default),
            "extra": str(extra),
        })
    cur.close()
    return cols

def fetch_create_table(conn, table_name):
    sql = f"SHOW CREATE TABLE `{MYSQL_DB}`.`{table_name}`"
    cur = conn.cursor()
    cur.execute(sql)
    row = cur.fetchone()
    cur.close()
    if row and len(row) >= 2:
        # row[0] is table name, row is DDL; ensure string
        return str(row)
    return None

def fetch_sample_rows(conn, table_name, limit=2):
    sql = f"SELECT * FROM `{MYSQL_DB}`.`{table_name}` LIMIT %s"
    cur = conn.cursor()
    cur.execute(sql, (int(limit),))
    data = rows_to_dicts(cur)
    cur.close()
    return data

def safe_dump_json(obj, path):
    # Ensure the whole structure is JSON-safe by converting non-serializable items to str
    def default(o):
        try:
            return str(o)
        except Exception:
            return f"<<unserializable:{type(o).__name__}>>"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=default)

def main():
    snapshot = {
        "database": str(MYSQL_DB),
        "host": str(MYSQL_HOST),
        "port": int(MYSQL_PORT),
        "tables": []
    }
    try:
        conn = get_connection()
    except Error as e:
        print(f"[ERROR] Could not connect to MySQL: {e}")
        return

    try:
        tables = fetch_all_tables(conn)
        for t in tables:
            tname = str(t)
            try:
                cols = fetch_columns(conn, tname)
            except Error as ce:
                print(f"[WARN] Columns for {tname}: {ce}")
                cols = []

            try:
                ddl = fetch_create_table(conn, tname)
            except Error as de:
                print(f"[WARN] DDL for {tname}: {de}")
                ddl = None

            try:
                sample = fetch_sample_rows(conn, tname, ROW_SAMPLE_COUNT)
            except Error as se:
                print(f"[WARN] Sample rows for {tname}: {se}")
                sample = []

            snapshot["tables"].append({
                "table": tname,
                "create_table": ddl,
                "columns": cols,
                "sample_rows": sample
            })

        safe_dump_json(snapshot, OUTPUT_FILE)
        print(f"[OK] Wrote schema snapshot to {OUTPUT_FILE}")

    finally:
        try:
            conn.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
