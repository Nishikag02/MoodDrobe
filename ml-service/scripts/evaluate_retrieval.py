"""Measure retrieval quality and speed on DeepFashion. No model is run.

Queries are test-split images (their saved vectors); the index searched is
train + val only. A result counts as relevant when it has the same category
as the query. See the project plan for why this is the right protocol here.

Run from ml-service/ after ingest_qdrant.py:
    python -m scripts.evaluate_retrieval
    python -m scripts.evaluate_retrieval --num-queries 500 --ks 1 5 10
    python -m scripts.evaluate_retrieval --label-field subcategory
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ML_ROOT = Path(__file__).resolve().parent.parent
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from vectordb import catalogue, config, store  # noqa: E402
from qdrant_client import models  # noqa: E402

INDEX_SPLITS = ["train", "val"]
QUERY_SPLIT = "test"


def load_query_vectors(embeddings_dir: Path) -> tuple[list[str], np.ndarray]:
    ids, vecs = [], []
    for f in catalogue.list_chunk_files(embeddings_dir, QUERY_SPLIT):
        try:
            ch = catalogue.validate_chunk(catalogue.load_chunk(f))
        except Exception as e:
            print(f"  skipping {f.name}: {e!r}")
            continue
        if ch.errors:
            print(f"  skipping {ch.rel_name}: {'; '.join(ch.errors)}")
            continue
        ids.extend(ch.ids)
        vecs.append(ch.vectors)
    if not vecs:
        raise SystemExit("No valid test-split chunks found. Embed the test split first.")
    return ids, np.concatenate(vecs)


def index_label_counts(client, collection: str, field: str, labels: set[str]) -> Counter:
    """How many indexed (train+val) items carry each label."""
    counts = Counter()
    split_cond = models.FieldCondition(key="dataset_split", match=models.MatchAny(any=INDEX_SPLITS))
    for label in labels:
        flt = models.Filter(must=[split_cond, models.FieldCondition(key=field, match=models.MatchValue(value=label))])
        counts[label] = client.count(collection, count_filter=flt, exact=True).count
    return counts


def pct(values) -> dict:
    a = np.asarray(values, dtype=float)
    return {"mean": round(float(a.mean()), 2), "p50": round(float(np.percentile(a, 50)), 2),
            "p95": round(float(np.percentile(a, 95)), 2), "max": round(float(a.max()), 2)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--embeddings-dir", type=Path, default=config.EMBEDDINGS_DIR)
    ap.add_argument("--products-csv", type=Path, default=config.PRODUCTS_CSV)
    ap.add_argument("--collection", default=config.QDRANT_COLLECTION)
    ap.add_argument("--num-queries", type=int, default=2000)
    ap.add_argument("--ks", type=int, nargs="+", default=[1, 5, 10, 20])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--label-field", default="category", help="products.csv column that defines relevance")
    ap.add_argument("--warmup", type=int, default=20, help="untimed searches before measuring latency")
    args = ap.parse_args()
    ks = sorted(set(args.ks))
    max_k = ks[-1]

    products = catalogue.load_products(args.products_csv)
    client = store.get_client()
    if not client.collection_exists(args.collection):
        raise SystemExit(f"Collection '{args.collection}' not found. Run scripts.ingest_qdrant first.")

    print("Loading test-split query vectors ...")
    q_ids, q_vecs = load_query_vectors(args.embeddings_dir)
    keep = [i for i, pid in enumerate(q_ids) if products.get(pid, {}).get(args.label_field)]
    rng = random.Random(args.seed)
    chosen = sorted(rng.sample(keep, min(args.num_queries, len(keep))))
    print(f"Using {len(chosen):,} of {len(q_ids):,} test images as queries (seed {args.seed})")

    labels = {products[q_ids[i]][args.label_field] for i in chosen}
    label_counts = index_label_counts(client, args.collection, args.label_field, labels)
    index_size = client.count(
        args.collection,
        count_filter=models.Filter(must=[models.FieldCondition(
            key="dataset_split", match=models.MatchAny(any=INDEX_SPLITS))]),
        exact=True,
    ).count
    if index_size == 0:
        raise SystemExit("No train/val points in the collection yet.")
    flt = store.build_filter(include_splits=INDEX_SPLITS)

    for i in chosen[: args.warmup]:
        store.search(q_vecs[i], k=max_k, query_filter=flt, client=client, name=args.collection)

    prec = {k: [] for k in ks}
    hit = {k: [] for k in ks}
    rec = {k: [] for k in ks}
    rr, latencies = [], []
    per_label = defaultdict(list)
    confusions = Counter()
    examples = []

    for n, i in enumerate(chosen, 1):
        qid = q_ids[i]
        label = products[qid][args.label_field]
        t = time.perf_counter()
        results = store.search(q_vecs[i], k=max_k, query_filter=flt, client=client, name=args.collection)
        latencies.append((time.perf_counter() - t) * 1000)
        rel = [r.get(args.label_field) == label for r in results]
        total_rel = max(label_counts[label], 1)
        for k in ks:
            top = rel[:k]
            prec[k].append(sum(top) / k)
            hit[k].append(float(any(top)))
            rec[k].append(sum(top) / total_rel)
        first = next((pos for pos, r in enumerate(rel, 1) if r), None)
        rr.append(1 / first if first else 0.0)
        per_label[label].append(sum(rel[:10]) / 10 if len(rel) >= 10 else sum(rel) / max(len(rel), 1))
        for r in results[:10]:
            if r.get(args.label_field) != label:
                confusions[(label, r.get(args.label_field))] += 1
        if len(examples) < 25:
            examples.append({"query": qid, "label": label,
                             "top5": [(r["product_id"], r.get(args.label_field), round(r["score"], 4)) for r in results[:5]]})
        if n % 250 == 0:
            print(f"  {n}/{len(chosen)} queries")

    # Random baseline: expected precision if results were drawn at random from the index.
    q_label_freq = Counter(products[q_ids[i]][args.label_field] for i in chosen)
    random_p = sum(q_label_freq[l] / len(chosen) * label_counts[l] / index_size for l in q_label_freq)

    summary = {
        "collection": args.collection, "label_field": args.label_field, "num_queries": len(chosen),
        "index_size_train_val": index_size, "seed": args.seed,
        "precision_at_k": {k: round(float(np.mean(prec[k])), 4) for k in ks},
        "hit_rate_at_k": {k: round(float(np.mean(hit[k])), 4) for k in ks},
        "recall_at_k": {k: round(float(np.mean(rec[k])), 6) for k in ks},
        f"mrr_at_{max_k}": round(float(np.mean(rr)), 4),
        "random_baseline_precision": round(random_p, 4),
        "search_latency_ms": pct(latencies),
    }

    print("\nResults (relevant = same " + args.label_field + ")")
    print(f"  {'K':>4} {'Precision@K':>12} {'HitRate@K':>10} {'Recall@K':>10}")
    for k in ks:
        print(f"  {k:>4} {summary['precision_at_k'][k]:>12.3f} {summary['hit_rate_at_k'][k]:>10.3f} "
              f"{summary['recall_at_k'][k]:>10.5f}")
    print(f"  MRR@{max_k}: {summary[f'mrr_at_{max_k}']:.3f}")
    print(f"  Random-guess precision: {random_p:.3f}")
    lat = summary["search_latency_ms"]
    print(f"  Qdrant search latency: p50 {lat['p50']} ms, p95 {lat['p95']} ms")

    worst = sorted(((l, float(np.mean(v)), len(v)) for l, v in per_label.items()), key=lambda x: x[1])
    print("\nWeakest categories (Precision@10, number of queries)")
    for l, p, c in worst[:8]:
        print(f"  {l:<20} {p:.3f}  ({c})")
    print("\nMost common mix-ups (query -> wrong result, count in top 10)")
    for (a, b), c in confusions.most_common(8):
        print(f"  {a} -> {b}: {c}")

    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_json = config.REPORTS_DIR / f"retrieval_eval_{args.label_field}_{stamp}.json"
    out_json.write_text(json.dumps({
        "summary": summary,
        "per_label_precision_at_10": {l: {"precision": round(p, 4), "queries": c} for l, p, c in worst},
        "top_confusions": [{"query_label": a, "result_label": b, "count": c} for (a, b), c in confusions.most_common(30)],
        "examples": examples,
    }, indent=2), encoding="utf-8")
    out_csv = config.REPORTS_DIR / f"retrieval_eval_{args.label_field}_{stamp}_per_label.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([args.label_field, "precision_at_10", "num_queries", "items_in_index"])
        for l, p, c in sorted(worst, key=lambda x: x[0]):
            w.writerow([l, round(p, 4), c, label_counts[l]])
    print(f"\nSaved {out_json}\nSaved {out_csv}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        store.get_client().close()
