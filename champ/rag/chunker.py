# champ/rag/chunker.py
from typing import Tuple, List
import re

def load_markdown_file(path: str) -> Tuple[str, str]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    # Title = first H1 if present
    m = re.search(r"^\s*#\s+(.*)$", text, flags=re.M)
    title = m.group(1).strip() if m else path
    return title, text

def split_paragraphs(text: str) -> List[str]:
    # Split on double newlines
    parts = re.split(r"\n\s*\n", text.strip())
    # Clean extra whitespace
    return [p.strip() for p in parts if p.strip()]

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
    """
    Approximate token chunking by paragraph grouping. chunk_size and overlap here are in characters,
    which is acceptable for a first pass. You can swap in a tokenizer later.
    """
    paras = split_paragraphs(text)
    chunks = []
    current = ""
    for p in paras:
        if len(current) + len(p) + 2 <= chunk_size:
            current = (current + "\n\n" + p) if current else p
        else:
            if current:
                chunks.append(current)
                # simple char overlap
                if overlap > 0 and len(current) > overlap:
                    current = current[-overlap:] + "\n\n" + p
                else:
                    current = p
            else:
                # very long single paragraph: hard split
                for i in range(0, len(p), chunk_size):
                    chunks.append(p[i:i+chunk_size])
                current = ""
    if current:
        chunks.append(current)
    return chunks
