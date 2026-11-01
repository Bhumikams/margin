"""Retrieval evaluation: does the right page show up in the top-k results?

    python -m scripts.eval eval/questions.json --k 5

Each item in the JSON file:
    {"question": "...", "file_name": "nosql_module2.pdf", "page": 14, "subject": "NoSQL"}

Reports Hit@k (the expected page is in the top k) and MRR (how high it ranks).
Use it to compare chunk sizes, top_k or embedding models with real numbers.
"""
import argparse
import json
import statistics

from app.config import settings
from app.main import get_embedder, get_store


def matches(src: dict, item: dict) -> bool:
    return (
        src["file_name"] == item["file_name"]
        and src["page_start"] <= item["page"] <= src["page_end"]
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--k", type=int, default=settings.top_k)
    args = ap.parse_args()

    items = json.load(open(args.path, encoding="utf-8"))
    store, embedder = get_store(), get_embedder()

    hits, rr, misses = [], [], []
    for item in items:
        vec = embedder.embed([item["question"]])[0]
        results = store.search(vec, args.k, {"subject": item.get("subject")})
        rank = next((i for i, r in enumerate(results, 1) if matches(r, item)), None)
        hits.append(rank is not None)
        rr.append(1 / rank if rank else 0.0)
        if rank is None:
            misses.append(item["question"])

    print(f"Questions : {len(items)}")
    print(f"Hit@{args.k}    : {sum(hits) / len(items):.0%}")
    print(f"MRR       : {statistics.mean(rr):.3f}")
    if misses:
        print("\nMissed:")
        for q in misses:
            print("  -", q)


if __name__ == "__main__":
    main()
