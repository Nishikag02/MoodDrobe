"""Download Polyvore Outfits (the official copy by its authors on Hugging Face).

Before the first run (one time):
  1. Sign in at https://huggingface.co and open
     https://huggingface.co/datasets/mvasil/polyvore-outfits
     Read the terms (academic / non-profit research use) and click to request access.
  2. Make a "Read" token at https://huggingface.co/settings/tokens
  3. In PowerShell (with .venv active):  hf auth login   (paste the token)

Then, from ml-service/:
    python -m scripts.download_polyvore                 # nondisjoint version, ~2.7 GB
    python -m scripts.download_polyvore --version disjoint

Files land in data/raw/polyvore_outfits/. Re-running skips files already downloaded.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ML_ROOT = Path(__file__).resolve().parent.parent
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from vectordb import compat  # noqa: E402

REPO = "mvasil/polyvore-outfits"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", default="nondisjoint", choices=["nondisjoint", "disjoint"])
    ap.add_argument("--out", type=Path, default=compat.POLYVORE_DIR)
    ap.add_argument("--no-images", action="store_true", help="only the small text files (for a quick check)")
    args = ap.parse_args()

    try:
        from huggingface_hub import snapshot_download
        from huggingface_hub.utils import GatedRepoError, HfHubHTTPError
    except ImportError:
        print("Missing package. Run: pip install huggingface_hub")
        return 1

    patterns = ["polyvore_item_metadata.json", "categories.csv", f"{args.version}/*"]
    if not args.no_images:
        patterns.append(f"data/{args.version}/*.parquet")  # the item images
    print(f"Downloading {REPO} ({args.version}) into {args.out}")
    print("The image files are large (about 2.6 GB for nondisjoint); this can take a while.")
    try:
        snapshot_download(repo_id=REPO, repo_type="dataset", local_dir=args.out, allow_patterns=patterns)
    except GatedRepoError:
        print("\nAccess denied. Open https://huggingface.co/datasets/mvasil/polyvore-outfits, "
              "accept the terms, then run `hf auth login` and try again.")
        return 1
    except HfHubHTTPError as e:
        print(f"\nDownload failed: {e}\nIf it says 401/403, run `hf auth login` first.")
        return 1

    need = [args.out / "polyvore_item_metadata.json", args.out / args.version / "train.json",
            args.out / args.version / "fill_in_blank_test.json", args.out / args.version / "compatibility_test.txt"]
    missing = [str(p) for p in need if not p.is_file()]
    if missing:
        print("Missing after download:", *missing, sep="\n  ")
        return 1
    parquets = sorted((args.out / "data" / args.version).glob("*.parquet"))
    print(f"\nOK. Text files present; {len(parquets)} image parquet files.")
    print("Next: python -m scripts.embed_polyvore")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
