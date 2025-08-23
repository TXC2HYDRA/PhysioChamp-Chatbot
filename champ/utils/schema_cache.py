import json
import os

DEFAULT_PATH = os.getenv("SCHEMA_SNAPSHOT_PATH", "champ/data/schema_snapshot.json")

_cache = None
_tables_index = None

def load_schema(path: str = None):
    global _cache, _tables_index
    p = path or DEFAULT_PATH
    if _cache is not None:
        return _cache
    with open(p, "r", encoding="utf-8") as f:
        _cache = json.load(f)
    # Build a quick index: {table_name: {columns:[...], ddl:str}}
    _tables_index = {}
    for t in _cache.get("tables", []):
        name = t.get("table")
        cols = [c.get("name") for c in (t.get("columns") or [])]
        _tables_index[name] = {
            "columns": cols,
            "ddl": t.get("create_table"),
        }
    return _cache

def tables_index():
    if _tables_index is None:
        load_schema()
    return _tables_index

def table_columns(table_name: str):
    idx = tables_index()
    meta = idx.get(table_name, {})
    return meta.get("columns", [])

def known_tables():
    return list(tables_index().keys())
