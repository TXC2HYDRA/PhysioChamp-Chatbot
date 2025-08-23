# champ/rag/embeddings.py
import os
import google.generativeai as genai
from typing import List

GEMINI_EMBED_MODEL = os.environ.get("GEMINI_EMBED_MODEL", "text-embedding-004")

class GeminiEmbedder:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY env var required")
        genai.configure(api_key=api_key)
        self.model = GEMINI_EMBED_MODEL

    def dim(self) -> int:
        # As of Gemini text-embedding-004, dimension is 768
        return 768

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        # Batch embed via embed_content
        # Ensure non-empty strings
        payload = [{"model": self.model, "content": t if t else " " } for t in texts]
        # Gemini API supports batch embedding with embed_content for one-by-one;
        # we'll do a simple loop to avoid hitting undocumented batch limits.
        out = []
        for item in texts:
            resp = genai.embed_content(model=self.model, content=item or " ")
            vec = resp["embedding"]
            out.append(vec)
        return out

    def embed_text(self, text: str) -> List[float]:
        return self.embed_texts([text])[0]
    