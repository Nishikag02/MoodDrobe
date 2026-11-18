"""Turn every Polyvore item image into a FashionCLIP vector (same model and
preprocessing as the catalogue), so the compatibility model can be trained
on vectors only.

Reads the images straight from the downloaded parquet files (no unzipping).
If you have the original polyvore_outfits/images/ folder instead (from the
authors' Google Drive tarball), pass --images-dir.

Safe to stop (Ctrl+C) and re-run: finished parts are skipped.
Uses the NVIDIA GPU automatically if PyTorch can see one.

From ml-service/:
    python -m scripts.embed_polyvore
    python -m scripts.embed_polyvore --limit 2000      # quick speed trial
    python -m scripts.embed_polyvore --images-dir data\\raw\\polyvore_outfits\\images

Output: data/processed/polyvore/item_embeddings.npz (item_ids, embeddings).
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

import numpy as np

ML_ROOT = Path(__file__).resolve().parent.parent
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from vectordb import compat  # noqa: E402

PART_ROWS = 5000
ID_NAMES = ("item_id", "id", "image_id", "item", "itemid")


def needed_items(version_dir: Path) -> set[str]:
    ids = set()
    for split in ("train", "valid", "test"):
        for o in json.loads((version_dir / f"{split}.json").read_text(encoding="utf-8")):
            ids.update(str(it["item_id"]) for it in o["items"])
    return ids


def to_image(value):
    from PIL import Image
    try:
        if isinstance(value, dict):
            data = value.get("bytes")
            if data is None and value.get("path"):
                return Image.open(value["path"]).convert("RGB")
        else:
            data = value
        with Image.open(io.BytesIO(data)) as im:
            return im.convert("RGB")
    except Exception:
        return None


def find_columns(pf, wanted: set[str]) -> tuple[str, str]:
    """Pick the image column (bytes) and the item-id column of a parquet file."""
    import pyarrow as pa
    schema = pf.schema_arrow
    img_col = None
    for f in schema:
        t = f.type
        if pa.types.is_struct(t) and any(t.field(i).name == "bytes" for i in range(t.num_fields)):
            img_col = f.name
            break
        if pa.types.is_binary(t) or pa.types.is_large_binary(t):
            img_col = img_col or f.name
    if img_col is None:
        raise SystemExit(f"No image column found. Columns: {schema.names}")
    others = [n for n in schema.names if n != img_col]
    for n in others:
        if n.lower() in ID_NAMES:
            return img_col, n
    sample = next(pf.iter_batches(batch_size=50, columns=others)).to_pydict()
    for n in others:
        vals = [str(v) for v in sample[n]]
        if vals and sum(v in wanted for v in vals) >= 0.8 * len(vals):
            return img_col, n
    raise SystemExit(f"No item-id column found. Columns: {schema.names}. "
                     f"Send this message to Claude.")


def row_source(args, wanted: set[str]):
    """Yield (part name, [(item_id, loader)]) groups of up to PART_ROWS items."""
    if args.images_dir:
        files = sorted(p for p in Path(args.images_dir).glob("*.jpg") if p.stem in wanted)
        if args.limit:
            files = files[: args.limit]
        for k in range(0, len(files), PART_ROWS):
            from PIL import Image

            def load(p=None):
                try:
                    with Image.open(p) as im:
                        return im.convert("RGB")
                except Exception:
                    return None
            yield f"images_{k // PART_ROWS:04d}", [(p.stem, (lambda p=p: load(p))) for p in files[k:k + PART_ROWS]]
        return

    import pyarrow.parquet as pq
    files = sorted((args.polyvore / "data" / args.version).glob("*.parquet"))
    if not files:
        raise SystemExit(f"No parquet files in {args.polyvore / 'data' / args.version}. "
                         f"Run python -m scripts.download_polyvore first.")
    seen = 0
    for path in files:
        pf = pq.ParquetFile(path)
        img_col, id_col = find_columns(pf, wanted)
        print(f"{path.name}: {pf.metadata.num_rows:,} rows (image column '{img_col}', id column '{id_col}')")
        for k, batch in enumerate(pf.iter_batches(batch_size=PART_ROWS, columns=[id_col, img_col])):
            d = batch.to_pydict()
            rows = [(str(i), (lambda v=v: to_image(v))) for i, v in zip(d[id_col], d[img_col]) if str(i) in wanted]
            if args.limit:
                rows = rows[: max(0, args.limit - seen)]
            seen += len(rows)
            if rows:
                yield f"{path.stem}_{k:04d}", rows
            if args.limit and seen >= args.limit:
                return


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", default="nondisjoint", choices=["nondisjoint", "disjoint"])
    ap.add_argument("--polyvore", type=Path, default=compat.POLYVORE_DIR)
    ap.add_argument("--images-dir", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=compat.POLYVORE_EMB)
    ap.add_argument("--batch-size", type=int, default=0, help="default: 128 on GPU, 32 on CPU")
    ap.add_argument("--limit", type=int, default=0, help="only the first N items (speed trial)")
    args = ap.parse_args()

    wanted = needed_items(args.polyvore / args.version)
    print(f"{len(wanted):,} items are used by the {args.version} outfits")

    import torch
    from concurrent.futures import ThreadPoolExecutor
    from vectordb import embedder
    _, model, processor = embedder._load()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    if device == "cuda":
        model = model.half()
    bs = args.batch_size or (128 if device == "cuda" else 32)
    print(f"Device: {device}" + (f" ({torch.cuda.get_device_name(0)})" if device == "cuda" else "") + f", batch {bs}")

    parts_dir = args.out.parent / f"parts_{args.version}"
    parts_dir.mkdir(parents=True, exist_ok=True)
    pool = ThreadPoolExecutor(max_workers=8)
    t_all, n_all = time.time(), 0
    for name, rows in row_source(args, wanted):
        part = parts_dir / f"{name}.npz"
        if part.exists():
            print(f"  {name}: already done, skipping")
            continue
        t0 = time.time()
        ids, vecs, failed = [], [], 0
        for b in range(0, len(rows), bs):
            batch = rows[b:b + bs]
            images = list(pool.map(lambda r: r[1](), batch))
            ok = [(r[0], im) for r, im in zip(batch, images) if im is not None]
            failed += len(batch) - len(ok)
            if not ok:
                continue
            with torch.no_grad():
                pixels = processor(images=[im for _, im in ok], return_tensors="pt")["pixel_values"].to(device)
                if device == "cuda":
                    pixels = pixels.half()
                out = embedder._as_tensor(model.get_image_features(pixel_values=pixels), "image")
            v = out.float().cpu().numpy()
            v /= np.linalg.norm(v, axis=1, keepdims=True) + 1e-12
            ids += [i for i, _ in ok]
            vecs.append(v.astype(np.float32))
        if vecs:
            tmp = part.with_name(part.stem + ".partial.npz")
            np.savez(tmp, item_ids=np.array(ids), embeddings=np.concatenate(vecs))
            tmp.replace(part)
        secs = time.time() - t0
        n_all += len(ids)
        print(f"  {name}: {len(ids)} ok, {failed} unreadable, {secs:.0f}s ({len(ids) / max(secs, 1e-6):.0f} images/s)",
              flush=True)

    # Merge all parts into one file (duplicates across splits are kept once).
    merged: dict[str, np.ndarray] = {}
    for p in sorted(parts_dir.glob("*.npz")):
        if p.name.endswith(".partial.npz"):
            continue
        with np.load(p) as f:
            for i, v in zip(f["item_ids"], f["embeddings"]):
                merged.setdefault(str(i), v)
    if not merged:
        print("Nothing embedded.")
        return 1
    ids = sorted(merged)
    np.savez(args.out, item_ids=np.array(ids), embeddings=np.stack([merged[i] for i in ids]).astype(np.float32))
    missing = len(wanted - set(ids))
    print(f"\nSaved {len(ids):,} item vectors to {args.out} ({missing:,} of the needed items missing)")
    print(f"This run: {n_all:,} images in {time.time() - t_all:.0f}s")
    print("Next: python -m scripts.train_compat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
