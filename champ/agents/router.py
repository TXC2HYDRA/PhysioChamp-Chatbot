from typing import Dict, Any, Optional
import re

def route(question: str) -> Dict[str, Any]:
    q = normalize(question)
    meta: Dict[str, Any] = {}

    # 1) Specific session by ID
    sid = _extract_session_id(q)
    if sid is not None:
        meta["session_id"] = sid
        return _make("db", "session_detail", meta)

    # 2) Latest / previous / most recent session
    if _asks_for_last_session(q):
        meta["latest"] = True
        return _make("db", "session_detail", meta)

    # 3) Session listing (optionally last N)
    if _mentions_list_sessions(q) or _asks_for_last_n_sessions(q):
        n = _extract_last_n(q)
        if n:
            meta["last_n"] = n
        return _make("db", "session_listing", meta)

    # 4) Health overview/summary -> hybrid (DB + LLM)
    if _asks_health_overview(q):
        n = _extract_last_n(q)
        if n:
            meta["last_n"] = n
        return _make("hybrid", "health_summary", meta)

    # 4.5) Personalized exercise plan -> hybrid (must come before analysis/general)
    if _asks_for_plan(q):
        goal = _extract_goal(q)
        meta["goal"] = goal
        n = _extract_last_n(q)
        if n:
            meta["last_n"] = n
        return _make("hybrid", "generate_personal_plan", meta)

    # 4.6) Knowledge/How-to/FAQ -> RAG (must come before general help)
    if _asks_knowledge(q):
        return _make("rag", "knowledge_answer", {})

    # 5) Open personal analysis / insights / recommendations -> hybrid
    if _asks_open_personal_analysis(q):
        sid2 = _extract_session_id(q)
        if sid2 is not None:
            meta["session_id"] = sid2
        elif "last" in q or "previous" in q or "recent" in q:
            meta["latest"] = True
        n = _extract_last_n(q)
        if n:
            meta["last_n"] = n
        return _make("hybrid", "open_personal_analysis", meta)

    # 6) General help -> LLM
    if _asks_general_help(q):
        return _make("llm", "general_help", meta)

    # Default: general LLM response
    return _make("llm", "general", meta)

# ----------------- Helpers -----------------

def normalize(text: Optional[str]) -> str:
    return (text or "").strip().lower()

def _make(mode: str, intent: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    return {"mode": mode, "intent": intent, "meta": meta}

def _extract_session_id(q: str) -> Optional[int]:
    patterns = [
        r"\bsession\s*id\s*[:#]?\s*(\d+)\b",
        r"\bsession\s*[:#]?\s*(\d+)\b",
        r"\bget\s+my\s+session\s+(\d+)\b",
        r"\bshow\s+session\s+(\d+)\b",
        r"\bgive\s+me\s+data\s+of\s+session\s+(\d+)\b",
        r"\bdata\s+of\s+session\s+(\d+)\b",
    ]
    for pat in patterns:
        m = re.search(pat, q)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                pass
    return None

def _asks_for_last_session(q: str) -> bool:
    keywords = [
        r"\blast\s+session\b",
        r"\bprevious\s+session\b",
        r"\bmost\s+recent\s+session\b",
        r"\brecent\s+session\b",
        r"\bmy\s+last\s+session\b",
        r"\bthe\s+last\s+session\b",
        r"\bprevious\s+one\b",
    ]
    return any(re.search(kw, q) for kw in keywords)

def _mentions_list_sessions(q: str) -> bool:
    return any(k in q for k in [
        "list sessions", "show sessions", "sessions list", "session list",
        "show my sessions", "display sessions", "view sessions", "last 10 sessions"
    ])

def _asks_for_last_n_sessions(q: str) -> bool:
    return bool(re.search(r"\blast\s+(\d+)\s+sessions?\b", q))

def _extract_last_n(q: str) -> Optional[int]:
    m = re.search(r"\blast\s+(\d+)\s+sessions?\b", q)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None

def _asks_health_overview(q: str) -> bool:
    trigger_any = [
        "describe my health", "health overview", "health summary",
        "overall health", "summarize my health", "summarise my health",
        "health status", "my health summary", "health report", "health analysis"
    ]
    if any(k in q for k in trigger_any):
        return True
    return ("describe" in q and ("session" in q or "sessions" in q))

def _asks_open_personal_analysis(q: str) -> bool:
    analysis_terms = [
        "insight", "insights", "analyze", "analyse", "analysis",
        "explain", "interpret", "comment", "opinion",
        "recommendation", "recommendations", "tips", "advice", "coach",
        "trend", "trends", "compare", "comparison", "improvement", "improvements"
    ]
    data_terms = [
        "my session", "my sessions", "my data", "from my",
        "last session", "previous session", "gait", "posture", "balance"
    ]
    return any(t in q for t in analysis_terms) and any(d in q for d in data_terms)

def _asks_general_help(q: str) -> bool:
    help_triggers = [
        "how to", "how do i", "what is", "explain", "help", "guide",
        "instructions", "steps to", "best way to", "tips for", "benefits of", "why does",
        "how can i use", "how to use", "what is physiochamp", "who are you"
    ]
    return any(k in q for k in help_triggers)

# --------- Plan detectors ---------
def _asks_for_plan(q: str) -> bool:
    terms = [
        "exercise plan",
        "personalized exercise plan",
        "personalised exercise plan",
        "my personalized exercise plan",
        "create my personalized exercise plan",
        "create my exercise plan",
        "workout plan",
        "training plan",
        "plan for core",
        "plan for balance",
        "plan for posture",
        "plan for gait",
    ]
    return any(t in q for t in terms)

def _extract_goal(q: str) -> str:
    q = q.lower()
    if "core" in q:
        return "core strength"
    if "balance" in q:
        return "balance"
    if "posture" in q:
        return "posture"
    if "gait" in q:
        return "gait efficiency"
    return "core strength"

# --------- RAG (knowledge) detector ---------
def _asks_knowledge(q: str) -> bool:
    terms = [
        "what is", "how to", "how do i", "benefits of",
        "exercises for", "tips for", "explain cadence",
        "stride time", "wear insoles", "care for insoles"
    ]
    return any(t in q for t in terms)
