# champ/rag/faiss_store.py
import os
import json
import faiss
import numpy as np
from typing import List, Dict, Tuple

class FaissStore:
    def __init__(self, index_dir: str, dim: int):
        self.index_dir = index_dir
        self.dim = dim
        self.index_path = os.path.join(index_dir, "index.faiss")
        self.meta_path = os.path.join(index_dir, "meta.jsonl")
        self.text_path = os.path.join(index_dir, "texts.jsonl")
        self._index = None
        self._ids = []  # parallel to meta/text lines

        if os.path.exists(self.index_path) and os.path.exists(self.meta_path) and os.path.exists(self.text_path):
            self._load()
        else:
            os.makedirs(index_dir, exist_ok=True)
            self._index = faiss.IndexFlatIP(dim)  # cosine-like if vectors normalized
            self._ids = []

    def _load(self):
        self._index = faiss.read_index(self.index_path)
        self._ids = []
        with open(self.meta_path, "r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line)
                self._ids.append(obj["id"])

    def save(self):
        faiss.write_index(self._index, self.index_path)

    def _append_jsonl(self, path: str, rows: List[Dict]):
        with open(path, "a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def upsert(self, ids: List[str], vectors: List[List[float]], texts: List[str], metas: List[Dict]):
        # Normalize vectors for inner product similarity
        arr = np.array(vectors, dtype="float32")
        norms = np.linalg.norm(arr, axis=1, keepdims=True) + 1e-12
        arr = arr / norms

        # Add to index
        self._index.add(arr)

        # Persist aligned metadata and texts
        meta_rows = []
        text_rows = []
        for i, _id in enumerate(ids):
            meta_rows.append({"id": _id, "meta": metas[i]})
            text_rows.append({"id": _id, "text": texts[i]})
            self._ids.append(_id)

        self._append_jsonl(self.meta_path, meta_rows)
        self._append_jsonl(self.text_path, text_rows)

    def query(self, vector: List[float], top_k: int = 5) -> List[Tuple[str, float]]:
        v = np.array([vector], dtype="float32")
        v = v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-12)
        D, I = self._index.search(v, top_k)
        out = []
        for score, idx in zip(D[0], I):
            if idx < 0 or idx >= len(self._ids):
                continue
            out.append((self._ids[idx], float(score)))
        return out

    def fetch_by_ids(self, ids: List[str]) -> List[Dict]:
        # Read meta and text jsonl quickly by scanning — fine for small corpora
        meta_map = {}
        with open(self.meta_path, "r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line)
                meta_map[obj["id"]] = obj["meta"]
        text_map = {}
        with open(self.text_path, "r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line)
                text_map[obj["id"]] = obj["text"]
        results = []
        for _id in ids:
            results.append({
                "id": _id,
                "meta": meta_map.get(_id, {}),
                "text": text_map.get(_id, "")
            })
        return results
