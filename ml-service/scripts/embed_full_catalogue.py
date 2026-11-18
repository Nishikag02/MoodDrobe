"""Embed every catalogue image with FashionCLIP into full_catalogue_v2 chunks.

Writes the same layout the other scripts read:
    data/processed/catalogue_embeddings/full_catalogue_v2/{train,val,test}/chunk_XXXXX.npz + .json
Each .npz holds `embeddings` (n x 512, unit length) and `product_ids`.

Safe to stop (Ctrl+C) and re-run: finished chunks are skipped, existing
files are never overwritten. Uses an NVIDIA GPU automatically if PyTorch
can see one (much faster); otherwise CPU (many hours for all 289k).

Run from ml-service/:
    python -m scripts.embed_full_catalogue
    python -m scripts.embed_full_catalogue --splits test --limit 2000   # quick trial
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ML_ROOT = Path(__file__).resolve().parent.parent
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from vectordb import catalogue, config  # noqa: E402


def load_image(path: Path):
    from PIL import Image
    try:
        with Image.open(path) as im:
            return im.convert("RGB")
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--splits", nargs="+", default=list(config.SPLITS), choices=config.SPLITS)
    ap.add_argument("--batch-size", type=int, default=0, help="default: 256 on GPU, 32 on CPU")
    ap.add_argument("--limit", type=int, default=0, help="only the first N rows per split (trial run)")
    ap.add_argument("--out", type=Path, default=config.EMBEDDINGS_DIR)
    args = ap.parse_args()

    import torch
    from vectordb import embedder
    _, model, processor = embedder._load()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    if device == "cuda":
        model = model.half()
    batch_size = args.batch_size or (256 if device == "cuda" else 32)
    print(f"Device: {device}" + (f" ({torch.cuda.get_device_name(0)})" if device == "cuda" else "")
          + f", batch size {batch_size}")

    with open(config.PRODUCTS_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    pool = ThreadPoolExecutor(max_workers=8)
    chunk_size = config.CHUNK_SIZE

    for split in args.splits:
        rs = [r for r in rows if r["dataset_split"] == split]  # CSV order, stable chunks
        if args.limit:
            rs = rs[: args.limit]
        out_dir = args.out / split
        out_dir.mkdir(parents=True, exist_ok=True)
        n_chunks = (len(rs) + chunk_size - 1) // chunk_size
        print(f"\n{split}: {len(rs):,} images in {n_chunks} chunks")
        for ci in range(n_chunks):
            npz = out_dir / f"chunk_{ci:05d}.npz"
            if npz.exists() and npz.with_suffix(".json").exists():
                try:
                    if not catalogue.load_chunk(npz).errors:
                        print(f"  chunk {ci:05d}: already done, skipping")
                        continue
                except Exception:
                    pass
                print(f"  chunk {ci:05d}: exists but unreadable; leaving it alone. Move it away to redo it.")
                continue
            part = rs[ci * chunk_size:(ci + 1) * chunk_size]
            t0 = time.time()
            ids, vecs, failed = [], [], []
            for b in range(0, len(part), batch_size):
                batch = part[b:b + batch_size]
                images = list(pool.map(lambda r: load_image(config.RAW_DATA_DIR / r["image_path"]), batch))
                ok = [(r, im) for r, im in zip(batch, images) if im is not None]
                failed += [r["product_id"] for r, im in zip(batch, images) if im is None]
                if not ok:
                    continue
                with torch.no_grad():
                    inputs = processor(images=[im for _, im in ok], return_tensors="pt")
                    pixels = inputs["pixel_values"].to(device)
                    if device == "cuda":
                        pixels = pixels.half()
                    out = embedder._as_tensor(model.get_image_features(pixel_values=pixels), "image")
                v = out.float().cpu().numpy()
                v /= np.linalg.norm(v, axis=1, keepdims=True) + 1e-12
                ids += [r["product_id"] for r, _ in ok]
                vecs.append(v.astype(np.float32))
            if not vecs:
                print(f"  chunk {ci:05d}: no readable images, skipped")
                continue
            tmp = npz.with_name(npz.stem + ".partial.npz")
            np.savez(tmp, embeddings=np.concatenate(vecs), product_ids=np.array(ids))
            tmp.replace(npz)  # only a complete file ever gets the final name
            secs = time.time() - t0
            npz.with_suffix(".json").write_text(json.dumps({
                "split": split, "chunk": ci, "num_success": len(ids), "num_failed": len(failed),
                "failed_product_ids": failed, "seconds": round(secs, 1), "device": device,
                "model": embedder.MODEL_NAME}, indent=2), encoding="utf-8")
            print(f"  chunk {ci:05d}: {len(ids)} ok, {len(failed)} failed, {secs:.0f}s "
                  f"({len(ids) / max(secs, 1e-6):.0f} images/s)", flush=True)
    print("\nDone. Next: python -m scripts.verify_embeddings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
