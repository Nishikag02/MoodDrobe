"""Compare similarity / ranking methods on the same DeepFashion test queries.

Same protocol as evaluate_retrieval.py: queries are test-split images, the
index is train + val, and a result is relevant when it has the query's
category. Every method below is scored on the SAME queries, so the table can
be compared row by row. Search is exact (NumPy) unless the row says Qdrant.

Methods
  random                         random ranking (lower bound)
  fashionclip_cosine             cosine on FashionCLIP vectors (what the app uses)
  (dot product and Euclidean distance give the same ranking as cosine,
   because the saved vectors are unit length; reported as a note, not a row)
  fashionclip_zscore_cosine      cosine after standardising each dimension
  category_head_space            cosine between predicted category distributions
  cosine+category_rerank         top-200 by cosine, re-ranked with the category model
  cosine+attribute_rerank        top-200 by cosine, re-ranked with predicted attributes
  cosine+colour_rerank           top-200 by cosine, re-ranked with dominant colours
  qdrant_hnsw_int8               the real Qdrant index (approximate + quantised)
  text "a photo of a <category>" FashionCLIP text -> image search (--text)
  plain CLIP vs FashionCLIP      on a random subset, re-embedded with
                                 openai/clip-vit-base-patch32 (--clip-subset N)

Run from ml-service/ after embedding (train_heads, extract_colors and Qdrant are
optional; their rows are skipped when missing):
    python -m scripts.compare_methods
    python -m scripts.compare_methods --num-queries 1000 --text --clip-subset 20000
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np

ML_ROOT = Path(__file__).resolve().parent.parent
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from scripts.train_heads import load_split  # noqa: E402
from vectordb import catalogue, colors, config, garments, heads  # noqa: E402

CANDIDATES = int(__import__("os").getenv("MOODDROBE_CANDIDATES", "200"))  # re-ranking methods re-order this many cosine neighbours


# ---------- metrics ----------

def score_rankings(ranked_labels: list[np.ndarray], query_labels: list[str], index_counts: Counter,
                   ks: list[int]) -> dict:
    """ranked_labels[i] = labels of query i's results, best first."""
    out = {f"P@{k}": [] for k in ks}
    out.update({f"Recall@{k}": [] for k in ks})
    out.update({f"Hit@{k}": [] for k in ks})
    out["MRR"] = []
    for labels, ql in zip(ranked_labels, query_labels):
        rel = labels == ql
        total = max(index_counts.get(ql, 0), 1)
        for k in ks:
            hits = rel[:k].sum()
            out[f"P@{k}"].append(hits / k)
            out[f"Recall@{k}"].append(hits / total)
            out[f"Hit@{k}"].append(float(hits > 0))
        first = np.flatnonzero(rel)
        out["MRR"].append(1.0 / (first[0] + 1) if len(first) else 0.0)
    return {m: round(float(np.mean(v)), 4) for m, v in out.items()}


def topk_exact(q: np.ndarray, index: np.ndarray, k: int, batch: int = 64) -> tuple[np.ndarray, float]:
    """Exact top-k by dot product. Returns (indices, mean ms per query)."""
    out = np.zeros((len(q), k), dtype=np.int64)
    t = time.perf_counter()
    for s in range(0, len(q), batch):
        sims = q[s:s + batch] @ index.T
        part = np.argpartition(-sims, k, axis=1)[:, :k]
        order = np.argsort(-np.take_along_axis(sims, part, axis=1), axis=1)
        out[s:s + batch] = np.take_along_axis(part, order, axis=1)
    return out, (time.perf_counter() - t) * 1000 / len(q)


def rerank(base_scores: np.ndarray, extra: np.ndarray, weight: float) -> np.ndarray:
    """Order of candidates by base + weight * extra (extra scaled to base's spread)."""
    spread = base_scores.max() - base_scores.min() or 0.1
    e = (extra - extra.min()) / ((extra.max() - extra.min()) or 1.0)
    return np.argsort(-(base_scores + weight * spread * e))


# ---------- optional: plain CLIP ----------

def embed_with(model_name: str, paths: list[Path], texts: list[str], batch: int = 64):
    import torch
    from PIL import Image
    from transformers import CLIPModel, CLIPProcessor

    from vectordb.embedder import _as_tensor

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = CLIPModel.from_pretrained(model_name).to(dev).eval()
    if dev == "cuda":
        model = model.half()
    proc = CLIPProcessor.from_pretrained(model_name)
    img_vecs = []
    with torch.no_grad():
        for s in range(0, len(paths), batch):
            ims = []
            for p in paths[s:s + batch]:
                with Image.open(p) as im:
                    ims.append(im.convert("RGB"))
            px = proc(images=ims, return_tensors="pt")["pixel_values"].to(dev)
            if dev == "cuda":
                px = px.half()
            img_vecs.append(_as_tensor(model.get_image_features(pixel_values=px), "image").float().cpu().numpy())
            if (s // batch) % 50 == 0:
                print(f"    {model_name}: {s + len(ims):,}/{len(paths):,} images")
        tin = proc(text=texts, return_tensors="pt", padding=True, truncation=True).to(dev)
        txt = _as_tensor(model.get_text_features(**tin), "text").float().cpu().numpy()
    v = np.concatenate(img_vecs)
    return v / np.linalg.norm(v, axis=1, keepdims=True), txt / np.linalg.norm(txt, axis=1, keepdims=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--embeddings-dir", type=Path, default=config.EMBEDDINGS_DIR)
    ap.add_argument("--products-csv", type=Path, default=config.PRODUCTS_CSV)
    ap.add_argument("--num-queries", type=int, default=1000)
    ap.add_argument("--ks", type=int, nargs="+", default=[1, 5, 10, 20])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--text", action="store_true", help="also score text queries 'a photo of a <category>'")
    ap.add_argument("--clip-subset", type=int, default=0,
                    help="also compare plain CLIP with FashionCLIP on this many index images (needs the photos)")
    ap.add_argument("--no-qdrant", action="store_true")
    args = ap.parse_args()
    ks = sorted(args.ks)
    rng = np.random.default_rng(args.seed)

    products = catalogue.load_products(args.products_csv)
    print("Loading vectors ...")
    index_ids, index_vecs = [], []
    for split in ("train", "val"):
        i, v = load_split(args.embeddings_dir, split, products)
        index_ids += i
        index_vecs.append(v)
    index = np.concatenate(index_vecs).astype(np.float32)
    test_ids, test_vecs = load_split(args.embeddings_dir, "test", products)
    if len(index) == 0 or len(test_ids) == 0:
        raise SystemExit("Need embedded train/val (index) and test (queries) chunks.")
    pick = rng.choice(len(test_ids), size=min(args.num_queries, len(test_ids)), replace=False)
    q_ids = [test_ids[i] for i in pick]
    q = test_vecs[pick].astype(np.float32)
    label = lambda pid: garments.category_name(products[pid].get("category"))  # noqa: E731
    index_labels = np.array([label(p) for p in index_ids])
    q_labels = [label(p) for p in q_ids]
    counts = Counter(index_labels.tolist())
    print(f"Index: {len(index):,} train+val vectors. Queries: {len(q):,} test images. "
          f"Categories: {len(counts)}")

    rows: dict[str, dict] = {}
    kmax = max(ks)

    def add(name, idx_lists, ms, note=""):
        rows[name] = {**score_rankings([index_labels[ix] for ix in idx_lists], q_labels, counts, ks),
                      "ms_per_query": round(ms, 2), "note": note}
        print(f"  {name:32s} P@10={rows[name].get('P@10', '-')}  MRR={rows[name]['MRR']}  {ms:.1f} ms")

    # random
    add("random", [rng.choice(len(index), kmax, replace=False) for _ in q], 0.0, "lower bound")

    # cosine (exact) + candidate pool for re-ranking
    cand, ms = topk_exact(q, index, CANDIDATES)
    add("fashionclip_cosine", cand[:, :kmax], ms, "exact search; the app's ranking")
    cand_scores = np.stack([index[c] @ qv for c, qv in zip(cand, q)])

    # z-scored cosine
    mean, std = index.mean(0), index.std(0) + 1e-6
    zi = (index - mean) / std
    zi /= np.linalg.norm(zi, axis=1, keepdims=True)
    zq = (q - mean) / std
    zq /= np.linalg.norm(zq, axis=1, keepdims=True)
    top, ms = topk_exact(zq, zi, kmax)
    add("fashionclip_zscore_cosine", top, ms, "each dimension standardised first")
    del zi

    model = heads.load()
    if model is not None:
        # learned category space
        pi = np.concatenate([model.category_probs(index[s:s + 20000]) for s in range(0, len(index), 20000)])
        pi_n = pi / np.linalg.norm(pi, axis=1, keepdims=True)
        pq = model.category_probs(q)
        pq_n = pq / np.linalg.norm(pq, axis=1, keepdims=True)
        top, ms = topk_exact(pq_n.astype(np.float32), pi_n.astype(np.float32), kmax)
        add("category_head_space", top, ms, "cosine between predicted category distributions")
        t = time.perf_counter()
        order = [c[rerank(s, pi_n[c] @ pqv, 1.0)] for c, s, pqv in zip(cand, cand_scores, pq_n)]
        add("cosine+category_rerank", [o[:kmax] for o in order], rows["fashionclip_cosine"]["ms_per_query"]
            + (time.perf_counter() - t) * 1000 / len(q), f"top-{CANDIDATES} cosine, re-ranked with category model")
        if model.has_attrs:
            t = time.perf_counter()
            aq = model.attribute_scores(q)
            aq = aq / np.linalg.norm(aq, axis=1, keepdims=True)
            order = []
            for c, s, av in zip(cand, cand_scores, aq):
                ai = model.attribute_scores(index[c])
                ai = ai / np.linalg.norm(ai, axis=1, keepdims=True)
                order.append(c[rerank(s, ai @ av, 0.5)])
            add("cosine+attribute_rerank", [o[:kmax] for o in order], rows["fashionclip_cosine"]["ms_per_query"]
                + (time.perf_counter() - t) * 1000 / len(q), f"top-{CANDIDATES} cosine, re-ranked with attributes")
    else:
        print("  (no category/attribute model: run train_heads to add those rows)")

    pal = colors.load_catalogue()
    if pal:
        t = time.perf_counter()
        order, col_top_cos, col_top_col = [], [], []
        for qid, c, s in zip(q_ids, cand, cand_scores):
            qp = pal.get(qid)
            if not qp or not qp[0]:
                order.append(c)
                continue
            cs = colors.similarity_matrix(list(zip(*qp)), [pal.get(index_ids[i], ([], []))[0] for i in c],
                                          [pal.get(index_ids[i], ([], []))[1] for i in c])
            o = rerank(s, cs, 0.5)
            order.append(c[o])
            col_top_cos.append(float(cs[:10].mean()))
            col_top_col.append(float(cs[o[:10]].mean()))
        add("cosine+colour_rerank", [o[:kmax] for o in order], rows["fashionclip_cosine"]["ms_per_query"]
            + (time.perf_counter() - t) * 1000 / len(q),
            f"colour match of top 10: {np.mean(col_top_cos):.3f} -> {np.mean(col_top_col):.3f}")
    else:
        print("  (no colour palettes: run extract_colors to add that row)")

    if not args.no_qdrant:
        try:
            from qdrant_client import models as qm

            from vectordb import store
            flt = qm.Filter(must=[qm.FieldCondition(key="dataset_split", match=qm.MatchAny(any=["train", "val"]))])
            pos = {p: i for i, p in enumerate(index_ids)}
            for v in q[:10]:
                store.search(v, k=kmax, query_filter=flt)  # warm up
            t = time.perf_counter()
            res = [store.search(v, k=kmax, query_filter=flt) for v in q]
            ms = (time.perf_counter() - t) * 1000 / len(q)
            top = [np.array([pos.get(r["product_id"], 0) for r in rr] + [0] * (kmax - len(rr))) for rr in res]
            overlap = np.mean([len(set(a[:10]) & set(b[:10])) / 10 for a, b in zip(top, cand)])
            add("qdrant_hnsw_int8", top, ms, f"approximate; {overlap:.3f} of exact top-10 found")
        except Exception as e:
            print(f"  (Qdrant row skipped: {e!r})")

    text_rows = {}
    if args.text:
        from vectordb import embedder
        names = sorted(counts)
        tv = np.stack([embedder.embed_text(f"a photo of a {n}") for n in names]).astype(np.float32)
        top, ms = topk_exact(tv, index, kmax)
        text_rows["fashionclip_text"] = score_rankings([index_labels[t] for t in top], names, counts, ks)
        print(f"  text queries (FashionCLIP): P@10={text_rows['fashionclip_text']['P@10']}")

    clip_rows = {}
    if args.clip_subset:
        sub = rng.choice(len(index), size=min(args.clip_subset, len(index)), replace=False)
        qsub = np.arange(min(len(q), 500))
        paths = [catalogue.resolve_image_path(products[index_ids[i]]["image_path"]) for i in sub] + \
                [catalogue.resolve_image_path(products[q_ids[i]]["image_path"]) for i in qsub]
        if any(p is None for p in paths):
            print("  (plain CLIP skipped: some photos not found)")
        else:
            names = sorted(counts)
            sub_labels = index_labels[sub]
            sub_counts = Counter(sub_labels.tolist())
            ql = [q_labels[i] for i in qsub]
            fc_top, _ = topk_exact(q[qsub], index[sub], kmax)
            clip_rows["fashionclip (subset)"] = score_rankings([sub_labels[t] for t in fc_top], ql, sub_counts, ks)
            cv, ctext = embed_with("openai/clip-vit-base-patch32", paths, [f"a photo of a {n}" for n in names])
            ci, cq = cv[: len(sub)], cv[len(sub):]
            c_top, _ = topk_exact(cq, ci, kmax)
            clip_rows["plain CLIP (subset)"] = score_rankings([sub_labels[t] for t in c_top], ql, sub_counts, ks)
            t_top, _ = topk_exact(ctext.astype(np.float32), ci, kmax)
            clip_rows["plain CLIP text (subset)"] = score_rankings([sub_labels[t] for t in t_top], names, sub_counts, ks)
            from vectordb import embedder
            ftv = np.stack([embedder.embed_text(f"a photo of a {n}") for n in names]).astype(np.float32)
            f_top, _ = topk_exact(ftv, index[sub], kmax)
            clip_rows["fashionclip text (subset)"] = score_rankings([sub_labels[t] for t in f_top], names, sub_counts, ks)
            for n, r in clip_rows.items():
                print(f"  {n:32s} P@10={r['P@10']}  MRR={r['MRR']}")

    report = {"created": datetime.now().isoformat(timespec="seconds"), "index_size": len(index),
              "num_queries": len(q), "num_categories": len(counts), "relevance": "same category",
              "note": "cosine, dot product and Euclidean distance rank identically on unit-length vectors",
              "image_query_methods": rows, "text_query_methods": text_rows, "clip_comparison": clip_rows,
              "clip_subset_size": args.clip_subset}
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    jpath = config.REPORTS_DIR / f"method_comparison_{stamp}.json"
    jpath.write_text(json.dumps(report, indent=2), encoding="utf-8")

    cols = [f"P@{k}" for k in ks] + [f"Recall@{max(ks)}", f"Hit@{min(10, max(ks))}" if 10 in ks else f"Hit@{max(ks)}",
                                     "MRR"]
    lines = ["| Method | " + " | ".join(cols) + " | ms/query | Note |", "|" + "---|" * (len(cols) + 3)]
    for name, r in rows.items():
        lines.append(f"| {name} | " + " | ".join(str(r.get(c, "")) for c in cols) + f" | {r['ms_per_query']} | {r['note']} |")
    for title, table in (("Text queries", text_rows), ("Plain CLIP vs FashionCLIP (subset)", clip_rows)):
        if table:
            lines += ["", f"**{title}**", "", "| Method | " + " | ".join(cols) + " |", "|" + "---|" * (len(cols) + 1)]
            lines += [f"| {n} | " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for n, r in table.items()]
    mpath = jpath.with_suffix(".md")
    mpath.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n" + "\n".join(lines))
    print(f"\nSaved {jpath} and {mpath.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
