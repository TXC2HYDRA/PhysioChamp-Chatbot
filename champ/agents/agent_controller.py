# champ/agents/agent_controller.py
from typing import Dict, Any
from champ.agents import tools
from champ.llm.provider import safe_call_llm

FORMAT_SYSTEM = (
    "You are a helpful assistant. Use only the provided CONTEXT. "
    "Do not invent numeric values. Plain text only; no markdown bullets or italics."
)

def _fmt_answer(context: Dict[str, Any], question: str) -> str:
    user = f"Question:\n{question}\n\nCONTEXT (JSON):\n{context}\n\nInstructions:\n- Be concise and actionable.\n- If recommendations exist, show 2–3. If none, skip that part."
    txt, unavail = safe_call_llm(FORMAT_SYSTEM, user)
    if unavail:
        return "AI is temporarily unavailable. Here are key figures:\n" + str(context.get("aggregates") or context)[:800]
    return txt or "No response."

def run(user_id: str, question: str, intent: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simple, guarded agent:
    - Cap at 3 tool calls.
    - Allowed sequences per intent.
    """
    trace = []
    context: Dict[str, Any] = {}

    try:
        if intent in ("health_summary", "open_personal_analysis", "trend_analysis"):
            # 1) Get aggregates
            r1 = tools.get_overview(user_id)
            trace.append({"tool": "get_overview", "ok": r1["ok"]})
            if not r1["ok"]:
                return {"ok": False, "answer": f"Could not load data: {r1['error']}", "trace": trace}

            rows = r1["data"]["rows"]
            ag = rows[0] if rows else {}
            context["aggregates"] = ag

            # 2) Optional: retrieve knowledge based on issues
            declines = []
            try:
                if ag.get("avg_balance_10", 0) + 2 < ag.get("avg_balance_all", 0):
                    declines.append("balance")
                if ag.get("avg_gait_10", 0) + 2 < ag.get("avg_gait_all", 0):
                    declines.append("gait")
                if ag.get("avg_posture_10", 0) + 2 < ag.get("avg_posture_all", 0):
                    declines.append("posture")
            except Exception:
                pass

            fatigue = (ag.get("short_sessions_10") or 0) >= 3
            profile = {"declines": declines, "fatigue": fatigue}

            r2 = tools.recommend_exercises(profile)
            trace.append({"tool": "recommend_exercises", "ok": r2["ok"]})
            context["exercise_recs"] = (r2["data"]["exercises"] if r2["ok"] else [])

            # 3) Optional RAG
            rq = "beginner balance drills" if "balance" in declines else "adherence tips"
            r3 = tools.retrieve_knowledge(rq, k=3, tags=["patient_edu"])
            trace.append({"tool": "retrieve_knowledge", "ok": r3["ok"]})
            context["docs"] = (r3["data"]["docs"] if r3["ok"] else [])

            answer = _fmt_answer(context, question)
            return {"ok": True, "answer": answer, "trace": trace}

        elif intent in ("session_listing", "session_detail"):
            r = tools.run_sql_template(intent, user_id, **meta)
            trace.append({"tool": "run_sql_template", "ok": r["ok"]})
            if not r["ok"]:
                # One retry: default last_n=10 if missing
                if intent == "session_listing" and "last_n" not in meta:
                    r = tools.run_sql_template(intent, user_id, last_n=10)
                    trace.append({"tool": "run_sql_template_retry", "ok": r["ok"]})
                if not r["ok"]:
                    return {"ok": False, "answer": f"Could not fetch sessions: {r['error']}", "trace": trace}

            rows = r["data"]["rows"]
            context["rows"] = rows[:10]
            answer = _fmt_answer(context, question)
            return {"ok": True, "answer": answer, "trace": trace}

        else:
            # Default: treat like hybrid-lite (aggregates + format)
            r1 = tools.get_overview(user_id)
            trace.append({"tool": "get_overview", "ok": r1["ok"]})
            if not r1["ok"]:
                return {"ok": False, "answer": f"Could not load data: {r1['error']}", "trace": trace}
            context["aggregates"] = (r1["data"]["rows"] if r1["data"]["rows"] else {})
            answer = _fmt_answer(context, question)
            return {"ok": True, "answer": answer, "trace": trace}
    except Exception as e:
        trace.append({"error": str(e)})
        return {"ok": False, "answer": "Something went wrong while planning this request.", "trace": trace}
