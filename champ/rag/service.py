# champ/rag/service.py
import os
from typing import List, Dict
from champ.rag.embeddings import GeminiEmbedder
from champ.rag.faiss_store import FaissStore

class RAGService:
    def __init__(self):
        self.embedder = GeminiEmbedder()
        index_dir = os.environ.get("FAISS_INDEX_DIR", ".faiss_index")
        self.store = FaissStore(index_dir=index_dir, dim=self.embedder.dim())

    def search(self, query: str, top_k: int = 5, min_score: float = 0.6) -> List[Dict]:
        qvec = self.embedder.embed_text(query)
        hits = self.store.query(qvec, top_k=top_k)
        # fetch texts and meta for hits
        ids = [h for h in hits]
        scores = [h[1] for h in hits]
        rows = self.store.fetch_by_ids(ids)
        results = []
        for row, score in zip(rows, scores):
            if score >= min_score:
                row["score"] = float(score)
                results.append(row)
        return results
