"""Build data/catalogue/metadata/products.csv from the official DeepFashion files.

Only needed on a computer that does not have products.csv yet (the original
laptop made it with prepare_catalogue.py). Same columns and row count
(289,222). It never overwrites an existing products.csv unless --force.

Needs in data/raw/deepfashion (or its Anno / Eval folders):
list_category_cloth.txt, list_category_img.txt, list_eval_partition.txt

Run from ml-service/:
    python -m scripts.build_products_csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ML_ROOT = Path(__file__).resolve().parent.parent
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from vectordb import config  # noqa: E402

COLUMNS = ["product_id", "image_path", "category", "subcategory", "color", "pattern", "source", "dataset_split"]


def find(name: str) -> Path:
    for p in (config.RAW_DATA_DIR / name, config.RAW_DATA_DIR / "Anno" / name,
              config.RAW_DATA_DIR / "Anno_coarse" / name, config.RAW_DATA_DIR / "Eval" / name):
        if p.is_file():
            return p
    raise SystemExit(f"Missing {name} in {config.RAW_DATA_DIR}")


def rows_of(path: Path) -> list[list[str]]:
    return [line.split() for line in path.read_text(encoding="utf-8").splitlines()[2:] if line.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=config.PRODUCTS_CSV)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if args.out.exists() and not args.force:
        raise SystemExit(f"{args.out} already exists (use --force to rebuild).")

    categories = [r[0] for r in rows_of(find("list_category_cloth.txt"))]
    split = {r[0]: r[1] for r in rows_of(find("list_eval_partition.txt"))}
    img_root = config.RAW_DATA_DIR / "Img"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    counts, missing = {}, 0
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for img, label in rows_of(find("list_category_img.txt")):
            name = img[len("img/"):].rsplit(".", 1)[0].replace("/", "__")
            s = split.get(img, "")
            if not (img_root / img).is_file():
                missing += 1
            w.writerow([f"df_{label}_{name}", f"Img/{img}", categories[int(label) - 1], "", "", "",
                        "DeepFashion", s])
            counts[s] = counts.get(s, 0) + 1
    print(f"Wrote {sum(counts.values()):,} rows to {args.out}")
    print("Split sizes:", {k or "(none)": v for k, v in counts.items()})
    print(f"Images not found on disk: {missing:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
