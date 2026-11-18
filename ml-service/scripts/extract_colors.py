"""Dominant colours for every catalogue image (no FashionCLIP, CPU only).

Reads products.csv and the DeepFashion photos, crops each one to its garment
box (list_bbox.txt, if present), and saves a 5-colour palette per product to
data/processed/colors/part_XXXXX.npz. Resumable: finished parts are skipped,
so you can stop it with Ctrl+C and run it again.

Run from ml-service/:
    python -m scripts.extract_colors
    python -m scripts.extract_colors --workers 4 --limit 2000     # quick test

Then load the colours into Qdrant: python -m scripts.ingest_qdrant --force
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ML_ROOT = Path(__file__).resolve().parent.parent
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from vectordb import catalogue, colors, config, heads  # noqa: E402

PART_SIZE = 10000


def read_boxes() -> dict[str, tuple[int, int, int, int]]:
    """list_bbox.txt -> {'img/Sheer_Blouse/img_01.jpg': (x1, y1, x2, y2)}"""
    path = heads.find_anno_file("list_bbox.txt")
    if path is None:
        return {}
    boxes = {}
    with open(path, encoding="utf-8") as f:
        next(f)
        next(f)
        for line in f:
            parts = line.split()
            if len(parts) >= 5:
                try:
                    boxes[heads.image_key(parts[0])] = tuple(int(x) for x in parts[-4:])
                except ValueError:
                    pass
    return boxes


def _one(job):
    pid, image_path, box = job
    from PIL import Image
    path = catalogue.resolve_image_path(image_path) if image_path else None
    if path is None:
        return pid, []
    try:
        with Image.open(path) as im:
            return pid, colors.palette(im, box=box)
    except OSError:
        return pid, []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--products-csv", type=Path, default=config.PRODUCTS_CSV)
    ap.add_argument("--out", type=Path, default=config.COLORS_DIR)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--limit", type=int, default=None, help="only the first N products (for a test)")
    args = ap.parse_args()

    products = list(catalogue.load_products(args.products_csv).values())
    if args.limit:
        products = products[: args.limit]
    boxes = read_boxes()
    print(f"{len(products):,} products; garment boxes for {len(boxes):,} images"
          + ("" if boxes else " (list_bbox.txt not found: using the centre of each photo)"))
    args.out.mkdir(parents=True, exist_ok=True)

    missing, t0, done, processed = 0, time.time(), 0, 0
    n_parts = (len(products) + PART_SIZE - 1) // PART_SIZE
    with Pool(args.workers) as pool:
        for part in range(n_parts):
            out_file = args.out / f"part_{part:05d}.npz"
            rows = products[part * PART_SIZE:(part + 1) * PART_SIZE]
            if out_file.exists():
                done += len(rows)
                continue
            jobs = [(r["product_id"], r.get("image_path"),
                     boxes.get(heads.image_key(r.get("image_path") or ""))) for r in rows]
            ids, hexes, weights = [], [], []
            for pid, pal in pool.imap(_one, jobs, chunksize=64):
                if not pal:
                    missing += 1
                pal = (pal + [("", 0.0)] * colors.PALETTE_SIZE)[: colors.PALETTE_SIZE]
                ids.append(pid)
                hexes.append([h for h, _ in pal])
                weights.append([w for _, w in pal])
            tmp = out_file.with_name(out_file.stem + ".partial.npz")
            np.savez(tmp, product_ids=np.array(ids), hex=np.array(hexes, dtype="<U7"),
                     weights=np.array(weights, dtype=np.float32))
            tmp.replace(out_file)
            done += len(rows)
            processed += len(rows)
            rate = processed / max(time.time() - t0, 1e-6)
            print(f"  part {part + 1}/{n_parts}: {done:,} products ({rate:.0f}/s)")

    print(f"Done. Palettes saved in {args.out}. Images not found: {missing:,}")
    if missing:
        print("  (Products whose photo is missing get no colours; everything else still works.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
