# champ/agents/tools.py
from typing import Dict, Any
from champ.db.fetch import run_query

def resp(ok: bool, data: Any = None, error: str | None = None) -> Dict[str, Any]:
    return {"ok": ok, "data": data, "error": error}

def get_overview(user_id: str) -> Dict[str, Any]:
    # Use your deterministic broad health SQL
    from champ.agents.sql_agent import _deterministic_broad_health_sql
    sql = _deterministic_broad_health_sql()
    try:
        rows = run_query(sql, [user_id, user_id])
        return resp(True, {"rows": rows})
    except Exception as e:
        return resp(False, error=str(e))

def get_last10_series(user_id: str) -> Dict[str, Any]:
    # Optionally call your metrics route logic directly
    # or re-implement here using SQL
    try:
        # Minimal: call DB directly or reuse code
        # For brevity, pretend we return a dict like your /overview_series
        return resp(True, {"series": {}})
    except Exception as e:
        return resp(False, error=str(e))

ALLOWED_TEMPLATES = {"session_listing", "session_detail"}

def run_sql_template(template_id: str, user_id: str, **meta) -> Dict[str, Any]:
    if template_id not in ALLOWED_TEMPLATES:
        return resp(False, error="template_not_allowed")
    from champ.agents.sql_agent import generate_db_sql_for_intent
    try:
        sql, params = generate_db_sql_for_intent(template_id, meta, user_id)
        rows = run_query(sql, params)
        return resp(True, {"rows": rows, "sql": sql, "params": params})
    except Exception as e:
        return resp(False, error=str(e))

# Placeholder: wire to your future vector DB
def retrieve_knowledge(query: str, k: int = 4, tags: list[str] | None = None) -> Dict[str, Any]:
    # Return a list[ {title, chunk, tags} ]
    return resp(True, {"docs": []})

# Deterministic mapping from trends -> exercises (rule-based, extend later)
def recommend_exercises(profile: Dict[str, Any]) -> Dict[str, Any]:
    # Example profile: {"declines": ["balance","gait"], "fatigue": True}
    suggestions = []
    if "balance" in (profile.get("declines") or []):
        suggestions += [
            {"name": "Tandem Stance", "minutes": 5, "tags": ["balance","beginner"]},
            {"name": "Single-leg Stance (support)", "minutes": 5, "tags": ["balance","beginner"]},
        ]
    if "gait" in (profile.get("declines") or []):
        suggestions += [{"name": "Heel-to-Toe Walk (line)", "minutes": 5, "tags": ["gait","beginner"]}]
    if profile.get("fatigue"):
        suggestions = [{"name": x["name"], "minutes": max(3, x["minutes"] - 2), "tags": x["tags"]} for x in suggestions]
    return resp(True, {"exercises": suggestions[:5]})
