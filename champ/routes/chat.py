from flask import Blueprint, request
from champ.agents.router import route
from champ.agents.sql_agent import generate_db_sql_for_intent
from champ.db.fetch import run_query
from champ.llm.provider import safe_call_llm
from champ.brand.context import BRAND_CONTEXT

# RAG imports
from champ.rag.service import RAGService
from champ.rag.prompt import build_cited_context, system_prompt as rag_system_prompt

import json
from decimal import Decimal

champ_bp = Blueprint("champ", __name__)
PREFERRED_MODEL = "gemini-2.0-flash"

# --------------- Brand/context helpers ---------------
def _bc():
    return (BRAND_CONTEXT or "").strip()

def _fmt_dt(dt):
    try:
        return str(dt).replace("T", " ")
    except Exception:
        return str(dt)

def _round(v, n=2):
    try:
        if isinstance(v, (int, float, Decimal)):
            return round(float(v), n)
    except Exception:
        pass
    return v

def _to_serializable(x):
    try:
        if isinstance(x, Decimal):
            return float(x)
    except Exception:
        pass
    return x

# --------------- LLM freehand ---------------
def llm_freehand_answer(question: str) -> str:
    system_prompt = (
        f"{_bc()}\n"
        "You are Champ, the energetic and caring AI assistant for PhysioChamp. "
        "Greet and acknowledge the user’s question, then answer clearly and helpfully. "
        "Offer practical suggestions when asked; keep the tone friendly and confident."
    )
    answer, unavail = safe_call_llm(system_prompt, question, model=PREFERRED_MODEL)
    if unavail or not answer:
        return "Hi! I’m Champ. I couldn’t reach AI just now—please try again in a moment."
    return answer

# --------------- DB helpers/formatters ---------------
def _format_session_detail(row: dict) -> str:
    parts = []
    add = lambda label, key: parts.append(f"{label}: {row.get(key)}") if row.get(key) is not None else None
    add("Id", "id")
    add("Status", "status")
    if row.get("start_time"): parts.append(f"Start: {_fmt_dt(row['start_time'])}")
    if row.get("end_time"): parts.append(f"End: {_fmt_dt(row['end_time'])}")
    if row.get("posture_score") is not None: parts.append(f"Posture: {_round(row['posture_score'],1)}")
    if row.get("gait_symmetry") is not None: parts.append(f"Gait symmetry: {_round(row['gait_symmetry'],1)}")
    if row.get("balance_score") is not None: parts.append(f"Balance: {_round(row['balance_score'],1)}")
    if row.get("step_count") is not None: parts.append(f"Steps: {row['step_count']}")
    if row.get("cadence_spm") is not None: parts.append(f"Cadence: {_round(row['cadence_spm'],1)} spm")
    if row.get("stride_time_s") is not None: parts.append(f"Stride time: {_round(row['stride_time_s'],3)} s")
    if row.get("contact_time_s") is not None: parts.append(f"Contact time: {_round(row['contact_time_s'],3)} s")
    return ", ".join(parts)

def _format_session_listing(rows: list) -> str:
    lines = []
    for r in rows[:10]:
        line = []
        line.append(f"Id:{r.get('id')}")
        if r.get("start_time"): line.append(f"Start:{_fmt_dt(r['start_time'])}")
        if r.get("end_time"): line.append(f"End:{_fmt_dt(r['end_time'])}")
        if r.get("status"): line.append(f"Status:{r['status']}")
        if r.get("posture_score") is not None: line.append(f"Posture:{_round(r['posture_score'],1)}")
        if r.get("gait_symmetry") is not None: line.append(f"Gait:{_round(r['gait_symmetry'],1)}")
        if r.get("balance_score") is not None: line.append(f"Balance:{_round(r['balance_score'],1)}")
        if r.get("step_count") is not None: line.append(f"Steps:{r['step_count']}")
        lines.append(" ".join(line))
    return "\n".join(lines)

def db_data_answer(intent: str, meta: dict, user_id: int) -> str:
    try:
        sql, params = generate_db_sql_for_intent(intent, meta, user_id)
    except Exception as e:
        return f"Hi! I can fetch your data and analyze it too. Try asking for insights or trends. ({str(e)})"

    rows = run_query(sql, params)
    if not rows:
        return "Hi! I couldn’t find matching records for that request."

    if isinstance(rows, dict):
        rows = [rows]

    if intent == "session_detail":
        text = _format_session_detail(rows[0])
        return f"Hi! Here’s your session summary: {text}"

    if intent == "session_listing":
        text = _format_session_listing(rows)
        return f"Hi! Here are your recent sessions:\n{text}"

    return f"Hi! I fetched {len(rows)} rows."

# --------------- Hybrid DB helpers ---------------
def _fetch_session(user_id: int, session_id: int = None, latest: bool = False):
    if session_id is not None:
        sql = "SELECT * FROM sessions WHERE user_id = %s AND id = %s"
        params = [user_id, int(session_id)]
    else:
        sql = "SELECT * FROM sessions WHERE user_id = %s ORDER BY end_time DESC LIMIT 1"
        params = [user_id]
    rows = run_query(sql, params)
    if isinstance(rows, list) and rows:
        return rows[0]
    if isinstance(rows, dict):
        return rows
    return None

def _fetch_all_avg(user_id: int):
    sql = """
      SELECT
        AVG(posture_score) AS posture_all,
        AVG(gait_symmetry) AS gait_all,
        AVG(balance_score) AS balance_all,
        AVG(step_count)    AS steps_all
      FROM sessions
      WHERE user_id = %s
    """
    rows = run_query(sql, [user_id])
    if isinstance(rows, dict):
        return rows
    if isinstance(rows, list) and rows:
        return rows[0] if isinstance(rows, dict) else {}
    return {}

def _fetch_last10_avg(user_id: int, last_n: int = 10):
    sql = f"""
      SELECT
        AVG(posture_score) AS posture_last{last_n},
        AVG(gait_symmetry) AS gait_last{last_n},
        AVG(balance_score) AS balance_last{last_n},
        AVG(step_count)    AS steps_last{last_n}
      FROM (
        SELECT posture_score, gait_symmetry, balance_score, step_count
        FROM sessions
        WHERE user_id = %s
        ORDER BY end_time DESC
        LIMIT {last_n}
      ) t
    """
    rows = run_query(sql, [user_id])
    if isinstance(rows, dict):
        return rows
    if isinstance(rows, list) and rows:
        return rows[0] if isinstance(rows, dict) else {}
    return {}

def _compute_deltas(a: dict, b: dict, keys: list) -> dict:
    deltas = {}
    for k in keys:
        va = a.get(k)
        vb = b.get(k)
        try:
            if va is not None and vb is not None:
                deltas[f"delta_{k}"] = _round(float(va) - float(vb), 2)
        except Exception:
            pass
    return deltas

def _compact_context_text(ctx: dict) -> str:
    lines = []
    if "session" in ctx and ctx["session"]:
        s = ctx["session"]
        lines.append("Session:")
        for k in ["id","status","start_time","end_time","posture_score","gait_symmetry","balance_score","step_count","cadence_spm","stride_time_s","contact_time_s"]:
            if k in s and s[k] is not None:
                val = s[k]
                if isinstance(val,(int,float,Decimal)): val = _round(val, 2)
                lines.append(f"  {k}: {val}")
    if "all_avg" in ctx and ctx["all_avg"]:
        a = ctx["all_avg"]
        lines.append("All-time averages:")
        for lk, sk in [("posture_all","posture_all"),("gait_all","gait_all"),("balance_all","balance_all"),("steps_all","steps_all")]:
            if sk in a and a[sk] is not None:
                lines.append(f"  {lk}: {_round(a[sk],2)}")
    if "last_avg" in ctx and ctx["last_avg"]:
        l = ctx["last_avg"]
        lines.append("Last-N averages:")
        for k, v in l.items():
            if v is not None:
                lines.append(f"  {k}: {_round(v,2)}")
    if "deltas" in ctx and ctx["deltas"]:
        d = ctx["deltas"]
        lines.append("Deltas (A - B as noted):")
        for k, v in d.items():
            lines.append(f"  {k}: {_round(v,2)}")
    return "\n".join(lines[:60])

def _analysis_prompt(context_text: str, mode: str) -> str:
    header = (
        f"{_bc()}\n"
        "You are Champ, the friendly and expert AI assistant for PhysioChamp.\n"
        "Use ONLY the data provided. Do not invent numbers; if data is missing, say so.\n"
        "Format:\n"
        "- Summary: 1–2 sentences.\n"
        "- Observations: 2–3 points with the actual numbers (e.g., posture 64.1 vs all 66.8).\n"
        "- Recommendations: 2 specific, non-medical tips tied to the observations.\n"
        "- Safety: 1 sentence (e.g., stop if pain/dizziness).\n"
    )
    if mode == "session":
        header += "Focus on this single session and its relation to all-time averages if available.\n"
    else:
        header += "Focus on last-N trends vs all-time averages.\n"
    return f"{header}\nData:\n{context_text}\n"

def _build_session_context(user_id: int, meta: dict) -> dict:
    if meta.get("session_id") is not None:
        session = _fetch_session(user_id, session_id=int(meta["session_id"]))
    else:
        session = _fetch_session(user_id, latest=True)
    all_avg = _fetch_all_avg(user_id)
    if session:
        for k in ["posture_score","gait_symmetry","balance_score","step_count","cadence_spm","stride_time_s","contact_time_s"]:
            if k in session and session[k] is not None:
                session[k] = _round(session[k], 2)
    if all_avg:
        if not isinstance(all_avg, dict):
            all_avg = {}
        else:
            for k in list(all_avg.keys()):
                if all_avg[k] is not None:
                    all_avg[k] = _round(all_avg[k], 2)
    deltas = {}
    if session and all_avg:
        mapping = {"posture_score": "posture_all", "gait_symmetry": "gait_all", "balance_score": "balance_all", "step_count": "steps_all"}
        a = {}
        b = {}
        for sk, ak in mapping.items():
            if session.get(sk) is not None:
                a[sk] = session.get(sk)
            if all_avg.get(ak) is not None:
                b[sk] = all_avg.get(ak)
        deltas = _compute_deltas(a, b, list(a.keys()))
    return {"session": session or {}, "all_avg": all_avg or {}, "deltas": deltas or {}}

def _build_trends_context(user_id: int, meta: dict) -> dict:
    last_n = int(meta.get("last_n", 10))
    all_avg = _fetch_all_avg(user_id)
    last_avg = _fetch_last10_avg(user_id, last_n)
    if not isinstance(all_avg, dict):
        all_avg = {}
    if not isinstance(last_avg, dict):
        last_avg = {}
    a = {}
    b = {}
    if last_avg:
        for k, v in list(last_avg.items()):
            if v is not None:
                a[k] = _round(v, 2)
    if all_avg:
        mapping = {"posture_last10": "posture_all", "gait_last10": "gait_all", "balance_last10": "balance_all", "steps_last10": "steps_all"}
        if str(last_n) != "10":
            mapping = {k.replace("10", str(last_n)): v for k, v in mapping.items()}
        for lk, ak in mapping.items():
            if lk in a and all_avg.get(ak) is not None:
                b[lk] = _round(all_avg.get(ak), 2)
    deltas = _compute_deltas(a, b, list(a.keys()))
    return {"all_avg": all_avg or {}, "last_avg": a or {}, "deltas": deltas or {}}

# --------------- Plan helpers ---------------
def _fetch_last10_rows(user_id: int, last_n: int = 10):
    sql = f"""
      SELECT id, start_time, end_time, status,
             posture_score, gait_symmetry, balance_score, step_count,
             stride_time_s, contact_time_s, cadence_spm
      FROM sessions
      WHERE user_id = %s
      ORDER BY end_time DESC
      LIMIT {last_n}
    """
    rows = run_query(sql, [user_id])
    if isinstance(rows, dict):
        return [rows]
    return rows or []

def _build_plan_context(user_id: int, meta: dict) -> dict:
    last_n = int(meta.get("last_n", 10))
    goal = (meta.get("goal") or "core strength").strip().lower()

    all_avg = _fetch_all_avg(user_id) or {}
    last_avg = _fetch_last10_avg(user_id, last_n) or {}
    last_rows = _fetch_last10_rows(user_id, last_n) or []

    all_avg_clean = {}
    for k, v in (all_avg.items() if isinstance(all_avg, dict) else []):
        if v is not None:
            all_avg_clean[k] = _round(_to_serializable(v), 2)

    last_avg_clean = {}
    for k, v in (last_avg.items() if isinstance(last_avg, dict) else []):
        if v is not None:
            last_avg_clean[k] = _round(_to_serializable(v), 2)

    compact_rows = []
    for r in last_rows[:5]:
        compact_rows.append({
            "id": _to_serializable(r.get("id")),
            "posture": _round(_to_serializable(r.get("posture_score")), 2) if r.get("posture_score") is not None else None,
            "gait": _round(_to_serializable(r.get("gait_symmetry")), 2) if r.get("gait_symmetry") is not None else None,
            "balance": _round(_to_serializable(r.get("balance_score")), 2) if r.get("balance_score") is not None else None,
            "steps": _to_serializable(r.get("step_count")),
        })

    ctx = {
        "goal": goal,
        "all_avg": all_avg_clean,
        "last_avg": last_avg_clean,
        "recent": compact_rows,
        "count_recent": len(last_rows)
    }
    return ctx

def _plan_prompt(context: dict) -> str:
    spec = (
        f"{_bc()}\n"
        "You are Champ, the PhysioChamp assistant.\n"
        "Task: Create a simple, safe, personalized 2-week exercise plan aligned to the user’s goal.\n"
        "Rules:\n"
        "- Use ONLY the provided data; do not invent numbers or diagnoses.\n"
        "- Non-medical guidance only; default to gentle/moderate intensity if data is limited.\n"
        "- Alternate light/medium sessions; include 1–2 rest/active-recovery days per week.\n"
        "- Include warm-up/cool-down ideas in notes where helpful.\n"
        "- Make it actionable and readable by patients.\n"
        "Return ONLY valid JSON (no extra text) with this exact shape:\n"
        "{\n"
        '  "summary": "one-line overview",\n'
        '  "weekly_plan": [\n'
        '    {"day": 1, "focus": "core|balance|posture|gait|active-recovery|rest",\n'
        '     "exercises": [\n'
        '        {"name":"...", "sets":2, "reps":"8 each", "notes":"..."}\n'
        '     ]},\n'
        '    ... exactly 14 entries, day 1..14 ...\n'
        "  ],\n"
        '  "safety": "single sentence safety note",\n'
        '  "progression": "how to scale up safely over the 2 weeks",\n'
        '  "measures": ["which app metrics to watch (e.g., posture, balance, cadence)"]\n'
        "}\n"
        "weekly_plan must contain exactly 14 items (days 1..14). Each item must include at least one exercise with name, sets, reps, and notes.\n"
        "Adapt intensity with the data: if posture in last-N < all-time, keep core volume moderate; if balance dipped, add stability drills.\n"
        "If data is thin or mixed, keep plan gentle and say so in summary.\n"
    )
    context_text = _compact_context_text({"all_avg": context.get("all_avg"), "last_avg": context.get("last_avg")})
    spec += f"\nGoal: {context.get('goal')}\n"
    spec += f"Recent sessions (first 5, compact): {json.dumps(context.get('recent', []), default=float)}\n"
    spec += f"Counts: recent={context.get('count_recent')}\n"
    return spec

def _try_parse_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        return None

def _plan_fallback_json():
    return json.dumps({
        "summary": "Gentle two-week plan tailored to current data availability. Alternate light core and balance work with rest/active recovery.",
        "weekly_plan": [
            {"day": 1, "focus": "core", "exercises": [{"name":"Dead bug","sets":2,"reps":"6/side","notes":"slow, controlled breathing"}]},
            {"day": 2, "focus": "balance", "exercises": [{"name":"Single-leg stance near support","sets":2,"reps":"20–30s/side","notes":"hold support if needed"}]},
            {"day": 3, "focus": "active-recovery", "exercises": [{"name":"Easy walk","sets":1,"reps":"10–15 min","notes":"comfortable pace"}]},
            {"day": 4, "focus": "posture", "exercises": [{"name":"Wall posture holds","sets":2,"reps":"20–30s","notes":"shoulders relaxed"}]},
            {"day": 5, "focus": "core", "exercises": [{"name":"Bridge","sets":2,"reps":"8–10","notes":"pause at the top"}]},
            {"day": 6, "focus": "rest", "exercises": []},
            {"day": 7, "focus": "balance", "exercises": [{"name":"Tandem stance","sets":2,"reps":"20–30s","notes":"light support available"}]},
            {"day": 8, "focus": "core", "exercises": [{"name":"Dead bug","sets":2,"reps":"8/side","notes":"smooth tempo"}]},
            {"day": 9, "focus": "balance", "exercises": [{"name":"Single-leg stance near support","sets":2,"reps":"20–30s/side","notes":"steady breathing"}]},
            {"day":10, "focus": "active-recovery", "exercises": [{"name":"Easy walk","sets":1,"reps":"10–15 min","notes":"even steps"}]},
            {"day":11, "focus": "posture", "exercises": [{"name":"Wall posture holds","sets":2,"reps":"20–30s","notes":"neutral head"}]},
            {"day":12, "focus": "core", "exercises": [{"name":"Bridge","sets":2,"reps":"10–12","notes":"don’t arch lower back"}]},
            {"day":13, "focus": "rest", "exercises": []},
            {"day":14, "focus": "balance", "exercises": [{"name":"Tandem stance","sets":2,"reps":"20–30s","notes":"light support optional"}]}
        ],
        "safety": "Keep intensity comfortable; stop if you feel pain or dizziness.",
        "progression": "If sessions feel easy in week 2, add 1 set or 2 reps to core/balance drills.",
        "measures": ["posture score", "balance score", "cadence consistency"]
    })

# --------------- HYBRID dispatcher ---------------
def hybrid_db_llm_answer(intent: str, meta: dict, user_id: int, question: str) -> str:
    if intent == "open_personal_analysis":
        ctx = _build_session_context(user_id, meta)
        if not ctx.get("session"):
            return "Hi! I couldn’t retrieve the session needed for analysis."
        context_text = _compact_context_text(ctx)
        system_prompt = _analysis_prompt(context_text, mode="session")
        answer, unavail = safe_call_llm(system_prompt, question, model=PREFERRED_MODEL)
        if unavail or not answer:
            return "Hi! I fetched your data, but AI analysis is momentarily unavailable. Please try again shortly."
        return answer

    if intent == "health_summary":
        ctx = _build_trends_context(user_id, meta)
        if not ctx.get("last_avg") and not ctx.get("all_avg"):
            return "Hi! I couldn’t retrieve enough data to summarize your health."
        context_text = _compact_context_text(ctx)
        system_prompt = _analysis_prompt(context_text, mode="trends")
        answer, unavail = safe_call_llm(system_prompt, question, model=PREFERRED_MODEL)
        if unavail or not answer:
            return "Hi! I summarized your data, but AI analysis is momentarily unavailable. Please try again shortly."
        return answer

    if intent == "generate_personal_plan":
        ctx = _build_plan_context(user_id, meta)
        prompt = _plan_prompt(ctx)

        # Step 1: ask for JSON
        answer, unavail = safe_call_llm(
            prompt,
            "Return only the JSON object. No extra text.",
            model=PREFERRED_MODEL
        )
        if unavail or not answer:
            return _plan_fallback_json()

        parsed = _try_parse_json(answer)

        # Step 2: fix if invalid or empty
        if not parsed or not isinstance(parsed, dict) or "weekly_plan" not in parsed or not parsed.get("weekly_plan"):
            fix_prompt = (
                "You returned an invalid or empty plan. "
                "Fix it and return ONLY valid JSON with the required keys: "
                'summary, weekly_plan (14 entries), safety, progression, measures. '
                "Ensure weekly_plan has 14 day objects (day 1..14), "
                'each with focus and at least 1 exercise with name, sets, reps, notes.'
            )
            fixed, unavail2 = safe_call_llm(
                prompt + "\n\n" + fix_prompt,
                "Return only the corrected JSON. No extra text.",
                model=PREFERRED_MODEL
            )
            parsed = _try_parse_json(fixed)
            if unavail2 or not parsed or not isinstance(parsed, dict) or not parsed.get("weekly_plan"):
                return _plan_fallback_json()

        return json.dumps(parsed)

    return "Hi! I’m not sure which analysis to run. Could you try rephrasing?"

# --------------- RAG handler ---------------
_rag_service = None

def _get_rag() -> RAGService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service

def rag_answer(question: str) -> str:
    svc = _get_rag()
    results = svc.search(question, top_k=5, min_score=0.6)
    if not results:
        return "I couldn’t find this in our docs. Would you like a general overview?"

    context = build_cited_context(results)
    sys = rag_system_prompt(_bc())
    user = f"Question: {question}\n\nContext:\n{context}\n\nRemember: cite facts with [1], ."

    answer, unavail = safe_call_llm(sys, user, model=PREFERRED_MODEL)
    if unavail or not answer:
        return "I couldn’t reach the knowledge service right now. Please try again shortly."
    return answer

# --------------- Route ---------------
@champ_bp.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    question = (data.get("question") or "").strip()
    if not user_id or not question:
        return {"error": "Missing user_id or question"}, 400

    decision = route(question)
    mode, intent, meta = decision["mode"], decision["intent"], decision["meta"]
    print(f"[ROUTER] mode={mode} intent={intent} meta={meta}")

    if mode == "llm":
        answer = llm_freehand_answer(question)
    elif mode == "db":
        answer = db_data_answer(intent, meta, int(user_id))
    elif mode == "hybrid":
        answer = hybrid_db_llm_answer(intent, meta, int(user_id), question)
    elif mode == "rag":
        answer = rag_answer(question)
    else:
        answer = "Hi! I’m not sure I understood that—could you rephrase your question?"

    # Return a structured plan object when the plan generator is used
    if mode == "hybrid" and intent == "generate_personal_plan" and isinstance(answer, str):
        parsed = _try_parse_json(answer)
        if parsed:
            return {"plan": parsed}

    return {"answer": answer}
