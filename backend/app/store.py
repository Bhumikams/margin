"""Vector stores.

AtlasStore  -> MongoDB Atlas Vector Search ($vectorSearch with metadata pre-filter)
MemoryStore -> numpy cosine search, same interface; used for tests and offline demos.

Collections (Atlas):
  chunks     : {chunk_id, doc_id, file_name, subject, module, page_start, page_end, text, embedding}
  documents  : {_id: doc_id, file_name, subject, module, pages, chunks, uploaded_at}
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

import numpy as np


class VectorStore(Protocol):
    def has_document(self, doc_id: str) -> bool: ...
    def add(self, doc_meta: dict, chunks: list[dict], vectors: np.ndarray) -> None: ...
    def search(self, vector: np.ndarray, k: int, filters: dict | None = None) -> list[dict]: ...
    def list_documents(self) -> list[dict]: ...
    def subjects(self) -> list[dict]: ...
    def get_chunks(self, filters: dict | None = None, limit: int = 40) -> list[dict]: ...
    def delete_document(self, doc_id: str) -> int: ...


def _clean_filters(filters: dict | None) -> dict:
    return {k: v for k, v in (filters or {}).items() if v not in (None, "", "all")}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
class MemoryStore:
    def __init__(self):
        self.docs: dict[str, dict] = {}
        self.chunks: list[dict] = []
        self.vectors = np.zeros((0, 0), dtype=np.float32)

    def has_document(self, doc_id: str) -> bool:
        return doc_id in self.docs

    def add(self, doc_meta, chunks, vectors):
        self.docs[doc_meta["doc_id"]] = {**doc_meta, "uploaded_at": _now()}
        self.chunks.extend(chunks)
        vectors = np.asarray(vectors, dtype=np.float32)
        self.vectors = vectors if self.vectors.size == 0 else np.vstack([self.vectors, vectors])

    def _mask(self, filters: dict) -> np.ndarray:
        f = _clean_filters(filters)
        return np.array(
            [all(c.get(k) == v for k, v in f.items()) for c in self.chunks], dtype=bool
        )

    def search(self, vector, k, filters=None):
        if not self.chunks:
            return []
        scores = self.vectors @ np.asarray(vector, dtype=np.float32)
        scores = np.where(self._mask(filters), scores, -np.inf)
        order = np.argsort(-scores)[:k]
        return [
            {**self.chunks[i], "score": float(scores[i])}
            for i in order
            if np.isfinite(scores[i])
        ]

    def list_documents(self):
        return sorted(self.docs.values(), key=lambda d: d["uploaded_at"], reverse=True)

    def subjects(self):
        out: dict[str, set] = {}
        for c in self.chunks:
            out.setdefault(c["subject"], set())
            if c.get("module"):
                out[c["subject"]].add(c["module"])
        return [
            {"subject": s, "modules": sorted(m, key=lambda x: (len(x), x))}
            for s, m in sorted(out.items())
        ]

    def get_chunks(self, filters=None, limit=40):
        mask = self._mask(filters)
        picked = [c for c, keep in zip(self.chunks, mask) if keep]
        picked.sort(key=lambda c: (c["file_name"], c["page_start"]))
        return picked[:limit]

    def delete_document(self, doc_id):
        keep = [i for i, c in enumerate(self.chunks) if c["doc_id"] != doc_id]
        removed = len(self.chunks) - len(keep)
        self.chunks = [self.chunks[i] for i in keep]
        self.vectors = self.vectors[keep] if keep else np.zeros((0, 0), dtype=np.float32)
        self.docs.pop(doc_id, None)
        return removed


# --------------------------------------------------------------------------- #
class AtlasStore:
    def __init__(self, uri: str, db_name: str, index_name: str):
        from pymongo import MongoClient

        if not uri:
            raise RuntimeError(
                "MONGODB_URI is not set. Add it to backend/.env, or set VECTOR_STORE=memory."
            )
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.chunks = self.db["chunks"]
        self.documents = self.db["documents"]
        self.index_name = index_name
        self.chunks.create_index("chunk_id", unique=True)
        self.chunks.create_index([("doc_id", 1), ("page_start", 1)])

    def has_document(self, doc_id):
        return self.documents.count_documents({"_id": doc_id}, limit=1) > 0

    def add(self, doc_meta, chunks, vectors):
        rows = [
            {**c, "embedding": [float(x) for x in v]} for c, v in zip(chunks, vectors)
        ]
        if rows:
            self.chunks.insert_many(rows, ordered=False)
        self.documents.replace_one(
            {"_id": doc_meta["doc_id"]},
            {**doc_meta, "_id": doc_meta["doc_id"], "uploaded_at": _now()},
            upsert=True,
        )

    def search(self, vector, k, filters=None):
        stage: dict = {
            "index": self.index_name,
            "path": "embedding",
            "queryVector": [float(x) for x in vector],
            "numCandidates": max(k * 20, 100),
            "limit": k,
        }
        f = _clean_filters(filters)
        if f:
            stage["filter"] = {key: {"$eq": val} for key, val in f.items()}
        pipeline = [
            {"$vectorSearch": stage},
            {"$set": {"score": {"$meta": "vectorSearchScore"}}},
            {"$unset": ["embedding", "_id"]},
        ]
        return list(self.chunks.aggregate(pipeline))

    def list_documents(self):
        docs = self.documents.find({}).sort("uploaded_at", -1)
        return [{**d, "doc_id": d.pop("_id")} for d in docs]

    def subjects(self):
        pipeline = [
            {"$group": {"_id": "$subject", "modules": {"$addToSet": "$module"}}},
            {"$sort": {"_id": 1}},
        ]
        out = []
        for row in self.chunks.aggregate(pipeline):
            mods = sorted((m for m in row["modules"] if m), key=lambda x: (len(x), x))
            out.append({"subject": row["_id"], "modules": mods})
        return out

    def get_chunks(self, filters=None, limit=40):
        cur = (
            self.chunks.find(_clean_filters(filters), {"embedding": 0, "_id": 0})
            .sort([("file_name", 1), ("page_start", 1)])
            .limit(limit)
        )
        return list(cur)

    def delete_document(self, doc_id):
        res = self.chunks.delete_many({"doc_id": doc_id})
        self.documents.delete_one({"_id": doc_id})
        return res.deleted_count
