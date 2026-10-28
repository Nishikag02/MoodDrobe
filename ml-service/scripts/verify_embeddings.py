"""Check the saved catalogue embedding chunks. Read-only: never edits or deletes.

Run from ml-service/ (safe while embed_catalogue.py is still running):
    python -m scripts.verify_embeddings
    python -m scripts.verify_embeddings --inspect      # show what is inside one chunk
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

from vectordb import catalogue, config  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--embeddings-dir", type=Path, default=config.EMBEDDINGS_DIR)
    ap.add_argument("--products-csv", type=Path, default=config.PRODUCTS_CSV)
    ap.add_argument("--inspect", action="store_true", help="print the arrays inside the first chunk and stop")
    args = ap.parse_args()

    files = catalogue.list_chunk_files(args.embeddings_dir)
    if not files:
        print(f"No chunk_*.npz files found under {args.embeddings_dir}")
        return 1

    if args.inspect:
        print(json.dumps(catalogue.describe_chunk(files[0]), indent=2))
        return 0

    print(f"Loading {args.products_csv} ...")
    products = catalogue.load_products(args.products_csv)
    expected = catalogue.expected_chunks(products)
    split_totals = {s: sum(1 for p in products.values() if p.get("dataset_split") == s) for s in config.SPLITS}

    report = {"embeddings_dir": str(args.embeddings_dir), "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "splits": {}, "chunks": []}
    seen: dict[str, str] = {}
    cross_dupes = 0
    all_ok = True

    for split in config.SPLITS:
        split_files = catalogue.list_chunk_files(args.embeddings_dir, split)
        present = {catalogue.chunk_index(f) for f in split_files}
        missing = sorted(set(range(expected[split])) - present)
        extra = sorted(i for i in present if i >= expected[split])
        valid_chunks, vectors = 0, 0
        for f in split_files:
            try:
                ch = catalogue.validate_chunk(catalogue.load_chunk(f), products)
            except Exception as e:  # unreadable or half-written file
                report["chunks"].append({"chunk": f"{split}/{f.name}", "ok": False, "errors": [repr(e)]})
                print(f"  BAD   {split}/{f.name}: {e!r}")
                all_ok = False
                continue
            for pid in ch.ids:
                if pid in seen:
                    cross_dupes += 1
                seen[pid] = ch.rel_name
            ok = not ch.errors
            valid_chunks += ok
            vectors += len(ch.ids) if ok else 0
            all_ok &= ok
            report["chunks"].append({"chunk": ch.rel_name, "ok": ok, "vectors": len(ch.ids),
                                     "errors": ch.errors, "warnings": ch.warnings})
            status = "ok   " if ok else "BAD  "
            note = "; ".join(ch.errors + ch.warnings)
            print(f"  {status} {ch.rel_name}: {len(ch.ids)} vectors{'  (' + note + ')' if note else ''}")

        not_embedded = split_totals[split] - sum(1 for pid, where in seen.items() if where.startswith(split + "/"))
        report["splits"][split] = {
            "expected_chunks": expected[split], "chunks_found": len(split_files), "valid_chunks": valid_chunks,
            "missing_chunk_indices": missing, "unexpected_chunk_indices": extra, "vectors_in_valid_chunks": vectors,
            "products_in_csv": split_totals[split], "products_without_vector": not_embedded,
        }
        all_ok &= not missing and not extra

    report["duplicate_ids_across_chunks"] = cross_dupes
    all_ok &= cross_dupes == 0
    report["all_ok"] = all_ok

    print("\nSummary")
    for s, r in report["splits"].items():
        print(f"  {s:5}: {r['valid_chunks']}/{r['expected_chunks']} valid chunks, "
              f"{r['vectors_in_valid_chunks']:,} vectors, {r['products_without_vector']:,} products without a vector"
              + (f", missing chunks {r['missing_chunk_indices']}" if r["missing_chunk_indices"] else "")
              + (f", unexpected chunks {r['unexpected_chunk_indices']} (check CHUNK_SIZE)" if r["unexpected_chunk_indices"] else ""))
    print(f"  duplicate IDs across chunks: {cross_dupes}")

    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = config.REPORTS_DIR / f"verify_{args.embeddings_dir.name}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport saved to {out}")
    print("ALL CHUNKS VALID" if all_ok else "NOT COMPLETE OR HAS ERRORS - see above")
    return 0 if all_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
