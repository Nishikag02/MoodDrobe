"""Load the saved FashionCLIP chunk vectors into Qdrant. No model is run.

Safe to re-run: chunks already loaded (same file size and time) are skipped,
and product IDs map to fixed Qdrant IDs, so nothing is duplicated.
Incomplete splits are fine: run it again later to add new chunks.

Run from ml-service/ with Qdrant running (see README):
    python -m scripts.ingest_qdrant
    python -m scripts.ingest_qdrant --splits train val     # only some splits
    python -m scripts.ingest_qdrant --force                # re-upload everything
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ML_ROOT = Path(__file__).resolve().parent.parent
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from vectordb import catalogue, config, garments, heads, store  # noqa: E402

PAYLOAD_FIELDS = ("product_id", "image_path", "category", "subcategory", "color", "pattern", "source", "dataset_split")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--embeddings-dir", type=Path, default=config.EMBEDDINGS_DIR)
    ap.add_argument("--products-csv", type=Path, default=config.PRODUCTS_CSV)
    ap.add_argument("--collection", default=config.QDRANT_COLLECTION)
    ap.add_argument("--splits", nargs="+", default=list(config.SPLITS), choices=config.SPLITS)
    ap.add_argument("--force", action="store_true", help="re-upload chunks even if already loaded")
    args = ap.parse_args()

    state_path = config.REPORTS_DIR / f"qdrant_ingest_state_{args.collection}.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"chunks": {}}

    print(f"Loading {args.products_csv} ...")
    products = catalogue.load_products(args.products_csv)

    model = heads.load()
    if model and model.has_attrs:
        print("Attribute model found: adding predicted attribute tags to each product")
    client = store.get_client()
    if store.ensure_collection(client, args.collection):
        print(f"Created Qdrant collection '{args.collection}'")
        state = {"chunks": {}}  # fresh collection: forget old state

    loaded, skipped, failed, points = 0, 0, [], 0
    t0 = time.time()
    for split in args.splits:
        for f in catalogue.list_chunk_files(args.embeddings_dir, split):
            key = f"{split}/{f.name}"
            stat = f.stat()
            fingerprint = {"size": stat.st_size, "mtime": int(stat.st_mtime)}
            prev = state["chunks"].get(key)
            if not args.force and prev and {k: prev.get(k) for k in fingerprint} == fingerprint:
                skipped += 1
                continue
            try:
                ch = catalogue.validate_chunk(catalogue.load_chunk(f), products)
            except Exception as e:
                failed.append(f"{key}: {e!r}")
                print(f"  SKIP  {key}: could not read ({e!r})")
                continue
            if ch.errors:
                failed.append(f"{key}: {'; '.join(ch.errors)}")
                print(f"  SKIP  {key}: {'; '.join(ch.errors)}")
                continue
            payloads = []
            tags = model.tags(ch.vectors) if model and model.has_attrs else [None] * len(ch.ids)
            for pid, item_tags in zip(ch.ids, tags):
                p = {k: products[pid].get(k) for k in PAYLOAD_FIELDS}
                name = garments.category_name(p.get("category"))
                p["category_name"] = name
                p["garment_type"] = garments.garment_type(name)  # upper / lower / full
                p["is_outer_layer"] = name in garments.OUTER_LAYERS
                if item_tags is not None:
                    p["tags"] = item_tags  # predicted, e.g. ["floral", "chiffon", "sleeveless"]
                p["embedding_chunk"] = key
                payloads.append(p)
            c0 = time.time()
            store.upsert(client, ch.ids, ch.vectors, payloads, args.collection)
            state["chunks"][key] = {**fingerprint, "count": len(ch.ids)}
            config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")  # save after every chunk
            loaded += 1
            points += len(ch.ids)
            print(f"  ok    {key}: {len(ch.ids)} points in {time.time() - c0:.1f}s")

    total = client.count(args.collection, exact=True).count
    expected = sum(c["count"] for c in state["chunks"].values())
    print(f"\nLoaded {loaded} chunks ({points:,} points), skipped {skipped} already loaded, "
          f"{len(failed)} failed, in {time.time() - t0:.0f}s")
    print(f"Collection '{args.collection}' now holds {total:,} points (state file expects {expected:,})")
    if failed:
        print("Failed chunks (not loaded):")
        for line in failed:
            print("  " + line)
    if total != expected:
        print("WARNING: point count differs from the state file. Re-run with --force to rebuild.")
    return 0 if not failed and total == expected else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        store.get_client().close()
