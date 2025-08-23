# champ/routes/insights.py

from flask import Blueprint, request
from champ.db.fetch import run_query
from champ.llm.provider import safe_call_llm
from champ.brand.context import BRAND_CONTEXT

insights_bp = Blueprint("insights", __name__)
PREFERRED_MODEL = "gemini-2.0-flash"

def _bc():
    return (BRAND_CONTEXT or "").strip()

def _stringify_rows(rows, limit=10):
    if not rows:
        return "No data."
    if isinstance(rows, dict):
        rows = [rows]
    lines = []
    for r in rows[:limit]:
        parts = []
        for k, v in r.items():
            if v is not None:
                parts.append(f"{k}:{v}")
        lines.append(", ".join(parts))
    return "\n".join(lines)

def _fetch_last_n_sessions(user_id: int, n: int = 10):
    sql = f"""
      SELECT id, start_time, end_time, status,
             posture_score, gait_symmetry, balance_score, step_count,
             stride_time_s, contact_time_s, cadence_spm
      FROM sessions
      WHERE user_id = %s
      ORDER BY end_time DESC
      LIMIT {n}
    """
    return run_query(sql, [user_id])

def _fetch_this_session(user_id: int, session_id: int):
    sql = """
      SELECT id, user_id, start_time, end_time, status,
             posture_score, gait_symmetry, balance_score, step_count,
             stride_time_s, contact_time_s, cadence_spm, swing_stance_ratio
      FROM sessions
      WHERE user_id = %s AND id = %s
      LIMIT 1
    """
    rows = run_query(sql, [user_id, session_id])
    return rows[0] if rows else None

def _fetch_aggregates(user_id: int):
    # Simple aggregates: all vs last10
    sql = """
    WITH last10 AS (
      SELECT posture_score, gait_symmetry, balance_score, step_count
      FROM sessions
      WHERE user_id = %s
      ORDER BY end_time DESC
      LIMIT 10
    )
    SELECT
      (SELECT COUNT(*) FROM sessions WHERE user_id = %s) AS total_sessions,
      (SELECT AVG(posture_score) FROM sessions WHERE user_id = %s) AS avg_posture_all,
      (SELECT AVG(gait_symmetry) FROM sessions WHERE user_id = %s) AS avg_gait_all,
      (SELECT AVG(balance_score) FROM sessions WHERE user_id = %s) AS avg_balance_all,
      (SELECT AVG(step_count) FROM sessions WHERE user_id = %s) AS avg_steps_all,
      (SELECT AVG(posture_score) FROM last10) AS avg_posture_10,
      (SELECT AVG(gait_symmetry) FROM last10) AS avg_gait_10,
      (SELECT AVG(balance_score) FROM last10) AS avg_balance_10,
      (SELECT AVG(step_count) FROM last10) AS avg_steps_10
    """
    params = [user_id, user_id, user_id, user_id, user_id, user_id]
    rows = run_query(sql, params)
    return rows[0] if rows else {}

def _insights_prompt_start(data_block: str) -> str:
    # Strict, clinically aware guardrails
    return (
        f"{_bc()}\n"
        "You are Champ, the PhysioChamp assistant. Generate insights for the start of a session.\n"
        "Rules:\n"
        "- Use ONLY the provided numbers and facts; do not invent or assume missing details.\n"
        "- Provide 2-3 concise, clinically appropriate observations about posture, gait, balance, and steps trends.\n"
        "- Provide 2 specific, non-medical, safety-aware recommendations suited for a warm-up phase.\n"
        "- Avoid diagnoses or therapeutic claims; keep within general wellness and physiotherapy-safe guidance.\n"
        "- If data is insufficient for a point, explicitly say so.\n"
        "Data:\n"
        f"{data_block}\n"
    )

def _insights_prompt_end(session_block: str) -> str:
    return (
        f"{_bc()}\n"
        "You are Champ, the PhysioChamp assistant. Generate insights for the end of a session based on THIS session only.\n"
        "Rules:\n"
        "- Use ONLY the data provided; do not infer beyond it.\n"
        "- Provide 2-3 concise observations specific to this session (posture, gait symmetry, balance, step count, cadence, stride/contact times as relevant).\n"
        "- Provide 2 specific, non-medical, safety-aware recommendations for the next session or cooldown.\n"
        "- Avoid clinical diagnoses; focus on posture form, consistency, pacing, rest, hydration, warm-up/cooldown, and adherence.\n"
        "- If any value is missing, do not speculate; skip it.\n"
        "Session data:\n"
        f"{session_block}\n"
    )

def _package_response(text: str, used: dict):
    # Simple JSON suited for Flutter
    return {
        "ok": bool(text),
        "insights": text or "",
        "used": used  # include data snapshot for auditing
    }

@insights_bp.route("/api/insights/start", methods=["POST"])
def insights_start():
    """
    Input JSON: { "user_id": 123 }
    Output JSON: { "ok": true, "insights": "...", "used": { "type": "start", ... } }
    """
    body = request.get_json(force=True)
    user_id = body.get("user_id")
    if not user_id:
        return {"ok": False, "error": "Missing user_id"}, 400

    last10 = _fetch_last_n_sessions(int(user_id), 10)
    aggs = _fetch_aggregates(int(user_id))

    data_block = "Aggregates:\n" + _stringify_rows(aggs) + "\n\nRecent sessions:\n" + _stringify_rows(last10)
    system_prompt = _insights_prompt_start(data_block)

    # Safety: If no sessions, short response without LLM
    if not last10:
        return _package_response(
            "No recent sessions found. Try a gentle warm-up and maintain comfortable pacing.",
            {"type": "start", "rows": 0}
        )

    answer, unavail = safe_call_llm(system_prompt, "Generate start-of-session insights.", model=PREFERRED_MODEL)
    if unavail or not answer:
        return _package_response(
            "Insights temporarily unavailable. Consider gentle warm-up, posture checks, and even pacing.",
            {"type": "start", "rows": len(last10)}
        )

    return _package_response(answer, {"type": "start", "rows": len(last10), "aggregates": aggs})

@insights_bp.route("/api/insights/end", methods=["POST"])
def insights_end():
    """
    Input JSON: { "user_id": 123, "session_id": 456 }
    Output JSON: { "ok": true, "insights": "...", "used": { "type": "end", "session_id": 456 } }
    """
    body = request.get_json(force=True)
    user_id = body.get("user_id")
    session_id = body.get("session_id")
    if not user_id or not session_id:
        return {"ok": False, "error": "Missing user_id or session_id"}, 400

    session_row = _fetch_this_session(int(user_id), int(session_id))
    if not session_row:
        return {"ok": False, "error": "Session not found"}, 404

    session_block = _stringify_rows(session_row)
    system_prompt = _insights_prompt_end(session_block)

    answer, unavail = safe_call_llm(system_prompt, "Generate end-of-session insights.", model=PREFERRED_MODEL)
    if unavail or not answer:
        return _package_response(
            "Insights temporarily unavailable. For next time: keep a steady cadence, check posture alignment, and hydrate.",
            {"type": "end", "session_id": session_id}
        )

    return _package_response(answer, {"type": "end", "session_id": session_id})
