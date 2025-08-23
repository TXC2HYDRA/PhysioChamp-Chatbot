import os
import re
from typing import Tuple, Dict, Any, List
from champ.llm.provider import call_llm_text
from champ.utils.schema_cache import load_schema


MODEL = os.getenv("LLM_MODEL", "gemini-2.0-flash")


SYSTEM_PROMPT = (
    "You are an expert MySQL SQL generator. "
    "Given a user question and a database schema, write ONE safe MySQL SELECT query only.\n"
    "Rules:\n"
    "- Use MySQL 8.0 syntax only.\n"
    "- Only use tables/columns that exist in the provided schema.\n"
    "- Prefer filtering once in a CTE for 'last N sessions' and reuse the CTE; "
    "avoid placing ORDER BY or LIMIT directly before UNION ALL.\n"
    "- Do not use PERCENTILE_CONT or WITHIN GROUP.\n"
    "- Always scope by user_id = %s when the question relates to a specific user's data.\n"
    "- Use %s placeholders for parameters.\n"
    "- Never modify data (no INSERT/UPDATE/DELETE/DDL).\n"
    "- Limit results sensibly (e.g., LIMIT 100) if large.\n"
    "- Return only the SQL, no explanations."
)


def _build_schema_context(schema: dict) -> str:
    lines = [f"Database: {schema.get('database')}"]
    for t in schema.get("tables", []):
        tname = t.get("table")
        cols = ", ".join(c.get("name") for c in (t.get("columns") or []))
        lines.append(f"Table {tname} columns: {cols}")
    return "\n".join(lines)


def _needs_user_scope(question: str) -> bool:
    q = f" {(question or '').lower()} "
    return any(k in q for k in [" my ", " me ", "mine", "show", "trend", "history", "stats", "summary"])


def _extract_sql(text: str) -> str:
    s = (text or "").strip()
    s = re.sub(r'^```[a-zA-Z]*', '', s).strip()
    # Remove trailing ```
    s = re.sub(r'$', '', s).strip()
    m = re.search(r'(?is)\bselect\b.*?;', s)
    if m:
        return m.group(0).strip()
    semi = s.find(";")
    if semi != -1:
        return s[:semi+1].strip()
    return s


def _enforce_guards(sql: str, require_user_scope: bool) -> str:
    s = (sql or "").strip().rstrip(";")
    if not s:
        raise ValueError("Empty SQL from LLM.")
    if re.search(r'(?i)\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE)\b', s):
        raise ValueError("Unsafe SQL verb detected.")
    if re.search(r'(?i)\bPERCENTILE_CONT\b|\bWITHIN\s+GROUP\b', s):
        raise ValueError("Unsupported percentile syntax for MySQL 8.0.")
    if re.search(r'(?is)ORDER\s+BY.+?LIMIT\s+\d+\s*UNION\s+ALL', s):
        raise ValueError("ORDER BY/LIMIT must be isolated before UNION ALL.")
    if (" from sessions " in s.lower()) and (" limit " not in s.lower()):
        s += " LIMIT 100"
    if require_user_scope and "user_id" not in s.lower():
        if re.search(r'(?i)\bWHERE\b', s):
            s += " AND user_id = %s"
        else:
            s += " WHERE user_id = %s"
    return s + ";"


def _collect_params(require_user_scope: bool, user_id: str):
    return [user_id] if require_user_scope else []


# ---------- Deterministic SQL builders (hybrid) ----------
def _deterministic_last10_trend_sql() -> str:
    # Uses start_time/end_time for duration; fields aligned to your schema
    return """
WITH last10 AS (
  SELECT id, start_time, end_time, posture_score, gait_symmetry, balance_score
  FROM sessions
  WHERE user_id = %s
  ORDER BY start_time DESC
  LIMIT 10
),
dur AS (
  SELECT
    id,
    TIMESTAMPDIFF(SECOND, start_time, end_time) AS dur_sec,
    ROW_NUMBER() OVER (ORDER BY TIMESTAMPDIFF(SECOND, start_time, end_time)) AS rn,
    COUNT(*) OVER () AS cnt
  FROM last10
),
median_dur AS (
  SELECT AVG(dur_sec) AS med_sec
  FROM dur
  WHERE rn IN (FLOOR((cnt+1)/2), CEIL((cnt+1)/2))
)
SELECT 'Posture Score Trend' AS Analysis, AVG(posture_score) AS TrendValue FROM last10
UNION ALL
SELECT 'Gait Symmetry Trend' AS Analysis, AVG(gait_symmetry) AS TrendValue FROM last10
UNION ALL
SELECT 'Balance Score Trend' AS Analysis, AVG(balance_score) AS TrendValue FROM last10
UNION ALL
SELECT 'Short Sessions Count' AS Analysis, COUNT(*) AS TrendValue
FROM dur, median_dur
WHERE dur.dur_sec < median_dur.med_sec
UNION ALL
SELECT 'Recent Alerts Count' AS Analysis, COUNT(*) AS TrendValue
FROM alerts
WHERE session_id IN (SELECT id FROM last10)
UNION ALL
SELECT 'Recent Recommendations Count' AS Analysis, COUNT(*) AS TrendValue
FROM recommendations
WHERE session_id IN (SELECT id FROM last10)
;""".strip()


def _deterministic_broad_health_sql() -> str:
    # Aligned with your schema; alerts/recommendations present
    return """
WITH last10 AS (
  SELECT id, start_time, end_time, posture_score, gait_symmetry, balance_score, step_count
  FROM sessions
  WHERE user_id = %s
  ORDER BY start_time DESC
  LIMIT 10
),
dur AS (
  SELECT
    id,
    TIMESTAMPDIFF(SECOND, start_time, end_time) AS dur_sec,
    ROW_NUMBER() OVER (ORDER BY TIMESTAMPDIFF(SECOND, start_time, end_time)) AS rn,
    COUNT(*) OVER () AS cnt
  FROM last10
),
median_dur AS (
  SELECT AVG(dur_sec) AS med_sec
  FROM dur
  WHERE rn IN (FLOOR((cnt+1)/2), CEIL((cnt+1)/2))
),
long_hist AS (
  SELECT
    COUNT(*) AS total_sessions,
    AVG(posture_score) AS avg_posture_all,
    AVG(gait_symmetry) AS avg_gait_all,
    AVG(balance_score) AS avg_balance_all,
    AVG(step_count) AS avg_steps_all
  FROM sessions
  WHERE user_id = %s
),
last10_stats AS (
  SELECT
    AVG(posture_score) AS avg_posture_10,
    AVG(gait_symmetry) AS avg_gait_10,
    AVG(balance_score) AS avg_balance_10,
    AVG(step_count) AS avg_steps_10
  FROM last10
),
short_sess AS (
  SELECT COUNT(*) AS short_sessions_10
  FROM dur, median_dur
  WHERE dur.dur_sec < median_dur.med_sec
),
alerts_10 AS (
  SELECT COUNT(*) AS recent_alerts
  FROM alerts
  WHERE session_id IN (SELECT id FROM last10)
),
recs_10 AS (
  SELECT COUNT(*) AS recent_recs
  FROM recommendations
  WHERE session_id IN (SELECT id FROM last10)
)
SELECT
  lh.total_sessions,
  lh.avg_posture_all, lh.avg_gait_all, lh.avg_balance_all, lh.avg_steps_all,
  l10.avg_posture_10, l10.avg_gait_10, l10.avg_balance_10, l10.avg_steps_10,
  ss.short_sessions_10,
  a10.recent_alerts,
  r10.recent_recs
FROM long_hist lh
JOIN last10_stats l10 ON 1=1
JOIN short_sess ss ON 1=1
JOIN alerts_10 a10 ON 1=1
JOIN recs_10 r10 ON 1=1
;""".strip()


# ---------- Deterministic SQL builders (DB-only intents) ----------
def build_session_listing_sql(user_id: str, last_n: int | None) -> Tuple[str, List[Any]]:
    n = last_n or 10
    sql = f"""
SELECT
  id, start_time, end_time, status,
  posture_score, gait_symmetry, balance_score, step_count,
  stride_time_s, stride_length_m, contact_time_s, cadence_spm, swing_stance_ratio
FROM sessions
WHERE user_id = %s
ORDER BY start_time DESC
LIMIT {int(n)};
""".strip()
    return sql, [user_id]


def build_session_detail_sql(user_id: str, session_id: int) -> Tuple[str, List[Any]]:
    # session_scores table may not exist in your schema dump; we omit join here.
    sql = """
SELECT
  s.id, s.user_id, s.status,
  s.start_time, s.end_time,
  s.posture_score AS session_posture_score,
  s.gait_symmetry, s.balance_score, s.step_count,
  s.stride_time_s, s.stride_length_m, s.contact_time_s, s.cadence_spm, s.swing_stance_ratio,
  s.heel_toe_timing,
  a.level AS alert_level, a.message AS alert_message,
  r.title AS recommendation_title, r.category AS recommendation_category, r.description AS recommendation_description
FROM sessions s
LEFT JOIN alerts a ON a.session_id = s.id
LEFT JOIN recommendations r ON r.session_id = s.id
WHERE s.user_id = %s AND s.id = %s
ORDER BY a.id DESC, r.id DESC
LIMIT 100;
""".strip()
    return sql, [user_id, session_id]


# ---------- Exposed helpers ----------
def generate_db_sql_for_intent(intent: str, meta: Dict[str, Any], user_id: int) -> Tuple[str, List[Any]]:
    # DB-only intents
    if intent == "session_detail":
        if meta.get("session_id") is not None:
            sql = "SELECT * FROM sessions WHERE user_id = %s AND id = %s"
            return sql, [user_id, int(meta["session_id"])]
        if meta.get("latest"):
            sql = "SELECT * FROM sessions WHERE user_id = %s ORDER BY end_time DESC LIMIT 1"
            return sql, [user_id]
        raise ValueError("Missing session_id or latest for session_detail intent")

    if intent == "session_listing":
        last_n = int(meta.get("last_n", 10))
        sql = f"""
        SELECT id, user_id, status, start_time, end_time,
               posture_score, gait_symmetry, balance_score, step_count,
               stride_time_s, contact_time_s, cadence_spm
        FROM sessions
        WHERE user_id = %s
        ORDER BY end_time DESC
        LIMIT {last_n}
        """.strip()
        return sql, [user_id]

    # Hybrid-only intents should not land here
    raise ValueError(f"Unsupported DB-only intent: {intent}")


def generate_sql_from_prompt(question: str, user_id: str):
    ql = (question or "").lower()
    if ("last 10" in ql or "last ten" in ql) and any(k in ql for k in ["trend", "analyze", "instability", "posture", "gait", "balance"]):
        return _deterministic_last10_trend_sql(), [user_id]
    if ("describe my health" in ql or "health summary" in ql or "overall health" in ql
        or "summarize my health" in ql or "summarise my health" in ql
        or ("describe" in ql and ("session" in ql or "sessions" in ql))):
        return _deterministic_broad_health_sql(), [user_id, user_id]


    schema = load_schema()
    schema_ctx = _build_schema_context(schema)
    require_user_scope = _needs_user_scope(question)
    user_prompt = (
        f"Question:\n{question}\n\n"
        f"Schema:\n{schema_ctx}\n\n"
        "Write one MySQL SELECT statement."
    )
    llm_sql = call_llm_text(SYSTEM_PROMPT, user_prompt, model=MODEL)
    sql = _extract_sql(llm_sql)
    sql = _enforce_guards(sql, require_user_scope)
    params = _collect_params(require_user_scope, user_id)
    return sql, params
