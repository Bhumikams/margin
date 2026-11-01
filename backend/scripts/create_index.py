"""Create the Atlas Vector Search index (run once after setting MONGODB_URI).

    python -m scripts.create_index

The index stores 384-dim cosine vectors and lets you pre-filter by subject and module.
"""
import sys
import time

from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

from app.config import settings

DEFINITION = {
    "fields": [
        {
            "type": "vector",
            "path": "embedding",
            "numDimensions": settings.embed_dim,
            "similarity": "cosine",
        },
        {"type": "filter", "path": "subject"},
        {"type": "filter", "path": "module"},
    ]
}


def main() -> None:
    if not settings.mongodb_uri:
        sys.exit("Set MONGODB_URI in backend/.env first.")
    db = MongoClient(settings.mongodb_uri)[settings.mongodb_db]
    if "chunks" not in db.list_collection_names():
        db.create_collection("chunks")  # search indexes need an existing collection
    coll = db["chunks"]

    existing = {ix["name"] for ix in coll.list_search_indexes()}
    if settings.vector_index_name in existing:
        print(f"Index '{settings.vector_index_name}' already exists.")
        return

    coll.create_search_index(
        SearchIndexModel(
            definition=DEFINITION, name=settings.vector_index_name, type="vectorSearch"
        )
    )
    print("Index requested. Waiting for it to become queryable", end="", flush=True)
    for _ in range(60):
        ix = next(iter(coll.list_search_indexes(settings.vector_index_name)), {})
        if ix.get("queryable"):
            print("\nReady.")
            return
        print(".", end="", flush=True)
        time.sleep(5)
    print("\nStill building; check the Atlas UI (Search & Vector Search tab).")


if __name__ == "__main__":
    main()
