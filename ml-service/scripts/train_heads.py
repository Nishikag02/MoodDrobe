"""Train the category and attribute models on the saved FashionCLIP vectors.

No FashionCLIP run: it reads full_catalogue_v2 chunks. Trains on the train
split, reports on val and test. Takes minutes on a laptop CPU and about
1.5 GB of RAM for the full dataset.

Attributes need DeepFashion's list_attr_cloth.txt and list_attr_img.txt in
data/raw/deepfashion (or its Anno folder). Without them only the category
model is trained.

Run from ml-service/:
    python -m scripts.train_heads
    python -m scripts.train_heads --no-attributes        # category model only
    python -m scripts.train_heads --max-train 50000      # quicker trial run
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

ML_ROOT = Path(__file__).resolve().parent.parent
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from vectordb import catalogue, config, garments, heads  # noqa: E402


def load_split(embeddings_dir: Path, split: str, products: dict) -> tuple[list[str], np.ndarray]:
    ids, vecs = [], []
    for f in catalogue.list_chunk_files(embeddings_dir, split):
        try:
            ch = catalogue.validate_chunk(catalogue.load_chunk(f), products)
        except Exception as e:
            print(f"  skipping {split}/{f.name}: {e!r}")
            continue
        if ch.errors:
            print(f"  skipping {ch.rel_name}: {'; '.join(ch.errors)}")
            continue
        ids.extend(ch.ids)
        vecs.append(ch.vectors)
    if not vecs:
        return [], np.zeros((0, config.EMBEDDING_DIM), dtype=np.float32)
    v = np.concatenate(vecs)
    return ids, v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-12)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--embeddings-dir", type=Path, default=config.EMBEDDINGS_DIR)
    ap.add_argument("--products-csv", type=Path, default=config.PRODUCTS_CSV)
    ap.add_argument("--out", type=Path, default=heads.MODEL_PATH)
    ap.add_argument("--no-attributes", action="store_true")
    ap.add_argument("--max-train", type=int, default=0, help="use only this many training vectors (0 = all)")
    ap.add_argument("--epochs", type=int, default=8)
    args = ap.parse_args()
    t0 = time.time()

    products = catalogue.load_products(args.products_csv)
    data = {}
    for split in config.SPLITS:
        print(f"Loading {split} vectors ...")
        data[split] = load_split(args.embeddings_dir, split, products)
        print(f"  {len(data[split][0]):,} vectors")
    tr_ids, tr_x = data["train"]
    if not tr_ids:
        raise SystemExit("No train-split vectors found.")
    if args.max_train and len(tr_ids) > args.max_train:
        pick = np.random.default_rng(0).choice(len(tr_ids), args.max_train, replace=False)
        tr_ids, tr_x = [tr_ids[i] for i in pick], tr_x[pick]

    mean, std = heads.standardize_stats(tr_x)
    norm = lambda x: (x - mean) / std  # noqa: E731
    arrays = {"mean": mean, "std": std}
    report: dict = {"trained_on": len(tr_ids), "trained_at": time.strftime("%Y-%m-%d %H:%M:%S")}

    # ---- category model ----
    print("\nTraining category model ...")
    cat_of = lambda pid: garments.category_name(products[pid].get("category"))  # noqa: E731
    arrays.update(heads.train_category_head(norm(tr_x), [cat_of(p) for p in tr_ids], epochs=args.epochs))
    classes = [str(c) for c in arrays["cat_classes"]]
    cidx = {c: i for i, c in enumerate(classes)}
    report["category"] = {"classes": len(classes)}
    for split in ("val", "test"):
        ids, x = data[split]
        keep = [i for i, p in enumerate(ids) if cat_of(p) in cidx]
        if not keep:
            continue
        z = norm(x[keep]) @ arrays["cat_w"] + arrays["cat_b"]
        true = np.array([cidx[cat_of(ids[i])] for i in keep])
        types_true = [garments.garment_type(classes[t]) for t in true]
        types_pred = [garments.garment_type(classes[t]) for t in z.argmax(axis=1)]
        r = {"top1": heads.topk_accuracy(z, true, 1), "top3": heads.topk_accuracy(z, true, 3),
             "top5": heads.topk_accuracy(z, true, 5),
             "garment_type_accuracy": float(np.mean([a == b for a, b in zip(types_true, types_pred)])),
             "images": len(keep)}
        report["category"][split] = {k: round(v, 4) if isinstance(v, float) else v for k, v in r.items()}
        print(f"  {split}: top-1 {r['top1']:.3f}, top-3 {r['top3']:.3f}, top-5 {r['top5']:.3f}, "
              f"top/bottom/full accuracy {r['garment_type_accuracy']:.3f}")

    # ---- attribute model ----
    cloth = heads.find_anno_file("list_attr_cloth.txt")
    img = heads.find_anno_file("list_attr_img.txt")
    if args.no_attributes:
        print("\nSkipping attributes (--no-attributes).")
    elif not (cloth and img):
        print("\nAttribute files not found (list_attr_cloth.txt, list_attr_img.txt); "
              "training the category model only.")
    else:
        names = heads.read_attribute_names(cloth)
        key_of = {pid: heads.image_key(products[pid]["image_path"]) for s in data for pid in data[s][0]}
        print(f"\nReading {img.name} ({len(names)} attributes; this file is large, about a minute) ...")
        labels = heads.read_attribute_labels(img, set(key_of.values()), len(names))
        print(f"  labels for {len(labels):,} images")

        def xy(ids, x):
            keep = [i for i, p in enumerate(ids) if key_of[p] in labels]
            y = np.stack([labels[key_of[ids[i]]] for i in keep]) if keep else np.zeros((0, len(names)), bool)
            return norm(x[keep]), y

        x_tr, y_tr = xy(tr_ids, tr_x)
        print("Training attribute model ...")
        arrays.update(heads.train_attribute_head(x_tr, y_tr, names, epochs=max(3, args.epochs - 2)))
        kept = arrays["attr_index"]
        report["attributes"] = {"attributes_used": len(kept)}
        for split in ("val", "test"):
            x_s, y_s = xy(*data[split])
            if not len(y_s):
                continue
            scores = x_s @ arrays["attr_w"] + arrays["attr_b"]
            y_k = y_s[:, kept]
            r = {"recall_at_3": heads.attribute_recall_at_k(scores, y_k, 3),
                 "recall_at_5": heads.attribute_recall_at_k(scores, y_k, 5)}
            report["attributes"][split] = {k: round(v, 4) for k, v in r.items()}
            print(f"  {split}: attribute recall@3 {r['recall_at_3']:.3f}, recall@5 {r['recall_at_5']:.3f}")

    heads.save(args.out, arrays, report)
    print(f"\nSaved {args.out} (+ .json report) in {time.time() - t0:.0f}s")
    print("Re-run `python -m scripts.ingest_qdrant --force` to add attribute tags to the index.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
