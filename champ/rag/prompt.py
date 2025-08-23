# champ/rag/prompt.py
from typing import List, Dict

def build_cited_context(results: List[Dict]) -> str:
    """
    results: [{id, score, meta:{title,...}, text}]
    Returns numbered context like:
    [1] Title — snippet...
    """
    lines = []
    for idx, r in enumerate(results, start=1):
        title = r.get("meta", {}).get("title") or r.get("id")
        snippet = r.get("text", "").strip().replace("\n", " ")
        if len(snippet) > 800:
            snippet = snippet[:800] + "..."
        lines.append(f"[{idx}] {title} — {snippet}")
    return "\n".join(lines)

def system_prompt(brand_context: str) -> str:
    return (
        f"{brand_context}\n"
        "You are Champ. Answer using ONLY the provided context.\n"
        "Cite facts with inline references like [1],  that match the numbered context items.\n"
        "If the answer is not in the context, say you don’t have that information.\n"
        "Be concise, helpful, and non-medical.\n"
    )
