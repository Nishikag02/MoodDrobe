"""Measure what the recommendation layer adds over plain nearest-neighbour search.

No model is run: test-split images (their saved vectors) are the queries and
only train + val items are recommended. For several diversity settings it reports:

- style match: average similarity of results to the query (higher = closer look)
- variety: distinct categories and distinct garment types in the top K,
  and intra-list diversity (1 - average similarity between results)
- same-category precision, to show what variety costs
- garment detection accuracy: does the query's guessed type (top / bottom /
  full body) match its true type? "Complete the look" depends on this.
- latency of a full recommendation

There is no ground truth for "goes well together" in this dataset, so outfit
compatibility itself is not scored here; that needs a user study or an outfit
dataset (see the project plan).

Run from ml-service/ after ingest_qdrant.py:
    python -m scripts.evaluate_recommendations
    python -m scripts.evaluate_recommendations --num-queries 300 --diversities 0 0.3 0.5
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

ML_ROOT = Path(__file__).resolve().parent.parent
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from vectordb import catalogue, config, garments, recommend, store  # noqa: E402
from scripts.evaluate_retrieval import INDEX_SPLITS, load_query_vectors  # noqa: E402


def intra_list_diversity(vectors: list[np.ndarray]) -> float:
    if len(vectors) < 2:
        return 0.0
    m = np.stack([recommend.normalize(v) for v in vectors])
    sims = m @ m.T
    n = len(vectors)
    return float(1 - (sims.sum() - n) / (n * (n - 1)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--embeddings-dir", type=Path, default=config.EMBEDDINGS_DIR)
    ap.add_argument("--products-csv", type=Path, default=config.PRODUCTS_CSV)
    ap.add_argument("--num-queries", type=int, default=500)
    ap.add_argument("--k", type=int, default=12)
    ap.add_argument("--diversities", type=float, nargs="+", default=[0.0, 0.3, 0.5])
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    products = catalogue.load_products(args.products_csv)
    print("Loading test-split query vectors ...")
    q_ids, q_vecs = load_query_vectors(args.embeddings_dir)
    rng = random.Random(args.seed)
    chosen = sorted(rng.sample(range(len(q_ids)), min(args.num_queries, len(q_ids))))
    print(f"Using {len(chosen):,} test images as queries (seed {args.seed})")
    base = {"include_splits": INDEX_SPLITS}

    rows = []
    detect_hits, detect_total = 0, 0
    for d in args.diversities:
        m = Counter()
        times = []
        for n, i in enumerate(chosen, 1):
            qid = q_ids[i]
            true_cat = garments.category_name(products[qid].get("category"))
            true_type = garments.garment_type(true_cat)
            t = time.perf_counter()
            rec = recommend.recommend(recommend.StyleQuery(image_vectors=[q_vecs[i]]), k=args.k,
                                      diversity=d, base_filter_kwargs=base)
            times.append((time.perf_counter() - t) * 1000)
            items = rec["your_style"]
            if d == 0.0:
                # The plain baseline: nearest items, no variety constraints.
                plain = store.search(q_vecs[i], k=args.k, query_filter=store.build_filter(**base), with_vectors=True)
                items = plain
            if not items:
                continue
            stored = store.get_vectors([it["product_id"] for it in items])
            vecs = [stored[it["product_id"]] for it in items if it["product_id"] in stored]
            q = recommend.normalize(q_vecs[i])
            m["style_match"] += float(np.mean([recommend.normalize(v) @ q for v in vecs]))
            m["ild"] += intra_list_diversity(vecs)
            cats = [garments.category_name(it.get("category")) for it in items]
            m["distinct_categories"] += len(set(cats))
            m["distinct_types"] += len({garments.garment_type(c) for c in cats})
            m["same_category_precision"] += sum(c == true_cat for c in cats) / len(cats)
            m["queries"] += 1
            if d == args.diversities[0] and rec.get("detected"):
                detect_total += 1
                detect_hits += rec["detected"]["garment_type"] == true_type
            if n % 100 == 0:
                print(f"  diversity {d}: {n}/{len(chosen)}")
        nq = max(m["queries"], 1)
        rows.append({
            "setting": "plain nearest neighbours" if d == 0.0 else f"your_style, diversity {d}",
            "diversity": d,
            "style_match": round(m["style_match"] / nq, 4),
            "intra_list_diversity": round(m["ild"] / nq, 4),
            "distinct_categories_in_top_k": round(m["distinct_categories"] / nq, 2),
            "distinct_garment_types_in_top_k": round(m["distinct_types"] / nq, 2),
            "same_category_precision": round(m["same_category_precision"] / nq, 4),
            "latency_ms_p50": round(float(np.percentile(times, 50)), 1),
            "latency_ms_p95": round(float(np.percentile(times, 95)), 1),
        })

    print(f"\nTop {args.k} results per query")
    hdr = f"  {'setting':<28} {'style':>6} {'ILD':>6} {'cats':>5} {'types':>5} {'sameCat':>8} {'p50 ms':>7}"
    print(hdr)
    for r in rows:
        print(f"  {r['setting']:<28} {r['style_match']:>6.3f} {r['intra_list_diversity']:>6.3f} "
              f"{r['distinct_categories_in_top_k']:>5.1f} {r['distinct_garment_types_in_top_k']:>5.1f} "
              f"{r['same_category_precision']:>8.3f} {r['latency_ms_p50']:>7.1f}")
    acc = detect_hits / detect_total if detect_total else 0.0
    print(f"\nGarment type detection (top / bottom / full body) accuracy: {acc:.3f} on {detect_total} queries")
    print("style = similarity to the query, ILD = variety between results, "
          "cats/types = distinct categories / garment types, sameCat = share in the query's category")

    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = config.REPORTS_DIR / f"recommendation_eval_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps({"k": args.k, "num_queries": len(chosen), "seed": args.seed, "settings": rows,
                               "garment_type_detection_accuracy": round(acc, 4)}, indent=2), encoding="utf-8")
    print(f"\nSaved {out}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        store.get_client().close()
