# scripts/ingest_docs.py
import os
import glob
import json
from typing import List, Dict
from champ.rag.chunker import load_markdown_file, chunk_text
from champ.rag.embeddings import GeminiEmbedder
from champ.rag.faiss_store import FaissStore

def collect_docs(content_dir: str) -> List[Dict]:
    files = sorted(glob.glob(os.path.join(content_dir, "*.md")))
    docs = []
    for fp in files:
        title, text = load_markdown_file(fp)
        docs.append({"id": os.path.basename(fp), "title": title, "path": fp, "text": text})
    return docs

def main():
    content_dir = os.environ.get("CONTENT_DIR", "content")
    index_dir = os.environ.get("FAISS_INDEX_DIR", ".faiss_index")
    os.makedirs(index_dir, exist_ok=True)

    docs = collect_docs(content_dir)
    if not docs:
        print(f"No .md files found in {content_dir}")
        return

    embedder = GeminiEmbedder()
    store = FaissStore(index_dir=index_dir, dim=embedder.dim())

    all_vectors = []
    all_texts = []
    all_meta = []
    all_ids = []

    chunk_size = int(os.environ.get("CHUNK_SIZE_TOKENS", "10"))
    chunk_overlap = int(os.environ.get("CHUNK_OVERLAP_TOKENS", "5"))

    for d in docs:
        chunks = chunk_text(d["text"], chunk_size=chunk_size, overlap=chunk_overlap)
        for i, ch in enumerate(chunks):
            cid = f"{d['id']}#chunk={i}"
            meta = {"doc_id": d["id"], "title": d["title"], "path": d["path"], "chunk_index": i}
            all_ids.append(cid)
            all_texts.append(ch)
            all_meta.append(meta)

    # Batch embed for efficiency
    vectors = embedder.embed_texts(all_texts)
    all_vectors.extend(vectors)

    store.upsert(all_ids, all_vectors, all_texts, all_meta)
    store.save()

    print(json.dumps({
        "indexed_docs": len(docs),
        "chunks": len(all_ids),
        "index_dir": index_dir
    }, indent=2))

if __name__ == "__main__":
    main()
