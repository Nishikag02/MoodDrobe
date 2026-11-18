"""Train the outfit compatibility model on Polyvore Outfits and evaluate it.

Needs the item vectors from scripts/embed_polyvore.py (FashionCLIP itself is
not retrained, so this takes minutes, not hours).

How training works, in plain words:
  Take a real outfit, hide one piece, and show the model the rest plus
  17 candidates: the hidden piece and 16 random pieces of the same category
  (another pair of shoes, another bag...). The model is rewarded for
  scoring the real piece highest. Repeat for every outfit, many times.

How it is checked (the two standard Polyvore tests, on outfits never used
for training):
  - Fill in the blank (FITB): an outfit with one piece missing and 4 options.
    Accuracy = how often the right one wins. Guessing gets 25%.
  - Compatibility AUC: real outfits vs. outfits made of random pieces.
    1.0 = always tells them apart, 0.5 = coin flip.
Both are also reported for plain FashionCLIP similarity (what
complete-the-look used before), so you can see what the model adds.

From ml-service/:
    python -m scripts.train_compat
    python -m scripts.train_compat --epochs 5            # quick run
    python -m scripts.train_compat --eval-only           # re-test the saved model

Writes data/processed/models/compat.npz and data/processed/reports/compat_eval.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ML_ROOT = Path(__file__).resolve().parent.parent
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from vectordb import compat, config  # noqa: E402

CLOTHING = {"tops", "bottoms", "outerwear", "all-body"}  # what the DeepFashion catalogue has


# ---------- data ----------

class Data:
    def __init__(self, poly: dict, emb: dict[str, np.ndarray]):
        cat_of = poly["category"]
        ids = sorted(emb)
        self.index = {i: k for k, i in enumerate(ids)}
        self.E = np.stack([emb[i] for i in ids]).astype(np.float32)
        train_items = {i for o in poly["splits"]["train"]["outfits"] for i in o if i in self.index}
        cats = sorted({cat_of.get(i, compat.UNKNOWN) for i in train_items} - {compat.UNKNOWN})
        self.categories = cats + [compat.UNKNOWN]
        cidx = {c: k for k, c in enumerate(self.categories)}
        self.cat = np.array([cidx.get(cat_of.get(i, compat.UNKNOWN), len(cats)) for i in ids], dtype=np.int64)
        self.cat_name = cat_of

        self.train_outfits = [np.array([self.index[i] for i in o if i in self.index])
                              for o in poly["splits"]["train"]["outfits"]]
        self.train_outfits = [o for o in self.train_outfits if len(o) >= 2]
        tr = np.array(sorted(self.index[i] for i in train_items))
        self.by_cat = {c: tr[self.cat[tr] == c] for c in range(len(self.categories))}
        self.by_cat = {c: v for c, v in self.by_cat.items() if len(v)}
        self.all_train = tr

        self.tasks = {}
        for split in ("valid", "test"):
            s = poly["splits"][split]
            ok = lambda xs: all(x in self.index for x in xs)  # noqa: E731
            self.tasks[split] = {
                "compat": [(lab, [self.index[i] for i in ids_]) for lab, ids_ in s["compat"] if ok(ids_)],
                "fitb": [([self.index[i] for i in q], [self.index[i] for i in a], r)
                         for q, a, r in s["fitb"] if ok(q) and ok(a)],
                "outfits": [[self.index[i] for i in o if i in self.index] for o in s["outfits"]],
            }
            dropped = len(s["compat"]) - len(self.tasks[split]["compat"]) + len(s["fitb"]) - len(self.tasks[split]["fitb"])
            if dropped:
                print(f"  {split}: {dropped} questions skipped (an item has no vector)")


# ---------- model ----------

def build_model(n_cats: int, dim: int = 256, hidden: int = 512, dropout: float = 0.1):
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    class Compat(nn.Module):
        def __init__(self):
            super().__init__()
            self.fc1 = nn.Linear(512, hidden)
            self.ln = nn.LayerNorm(hidden)
            self.fc2 = nn.Linear(hidden, dim)
            self.skip = nn.Linear(512, dim, bias=False)
            self.drop = nn.Dropout(dropout)
            self.mask_raw = nn.Parameter(torch.full((n_cats, n_cats, dim), math.log(math.e - 1)))
            self.log_scale = nn.Parameter(torch.tensor(math.log(10.0)))

        def encode(self, x):
            h = self.drop(F.gelu(self.ln(self.fc1(x)), approximate="tanh"))
            return self.fc2(h) + self.skip(x)

        def masks(self):
            m = F.softplus(self.mask_raw)
            return 0.5 * (m + m.transpose(0, 1))

        def scale(self):
            return self.log_scale.exp().clamp(max=50.0)

        def pair(self, ha, ca, hb, cb):
            """ha/hb: (..., D) encoded items, ca/cb: (...) category ids -> (...) scores."""
            m = self.masks()[ca, cb]
            return self.scale() * F.cosine_similarity(ha * m, hb * m, dim=-1)

    return Compat()


def export(model, categories: list[str], info: dict, path: Path):
    sd = {k: v.detach().float().cpu().numpy() for k, v in model.state_dict().items()}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.stem + ".partial.npz")
    np.savez(tmp, fc1_w=sd["fc1.weight"], fc1_b=sd["fc1.bias"], ln_g=sd["ln.weight"], ln_b=sd["ln.bias"],
             fc2_w=sd["fc2.weight"], fc2_b=sd["fc2.bias"], skip_w=sd["skip.weight"],
             masks=model.masks().detach().float().cpu().numpy(),
             scale=np.float32(model.scale().item()),
             categories=np.array(categories), info=np.array(json.dumps(info)))
    tmp.replace(path)


# ---------- evaluation (works for any "pair score" function) ----------

def auc(labels, scores) -> float:
    labels = np.asarray(labels)
    scores = np.asarray(scores, dtype=np.float64)
    order = scores.argsort()
    ranks = np.empty(len(scores))
    ranks[order] = np.arange(1, len(scores) + 1)
    for s in np.unique(scores[np.r_[False, np.diff(scores[order]) == 0]] if len(scores) > 1 else []):
        tie = scores == s
        ranks[tie] = ranks[tie].mean()
    pos = labels == 1
    n_pos, n_neg = pos.sum(), (~pos).sum()
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    return float((ranks[pos].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def evaluate(pair_fn, data: Data, split: str) -> dict:
    """pair_fn(a_idx, b_idx) -> scores for row-aligned item index arrays."""
    t = data.tasks[split]
    clothing = {k for k, c in enumerate(data.categories) if c in CLOTHING}

    # FITB: candidate score = mean compatibility with the outfit's other pieces
    qa, qb, owner = [], [], []
    for qi, (q, answers, _) in enumerate(t["fitb"]):
        for ai, a in enumerate(answers):
            qa += q
            qb += [a] * len(q)
            owner += [(qi, ai)] * len(q)
    s = pair_fn(np.array(qa), np.array(qb))
    tot = {}
    for (qi, ai), v in zip(owner, s):
        tot.setdefault(qi, {}).setdefault(ai, []).append(v)
    right, right_c, n_c = 0, 0, 0
    for qi, (q, answers, r) in enumerate(t["fitb"]):
        means = [np.mean(tot[qi][ai]) for ai in range(len(answers))]
        hit = int(np.argmax(means) == r)
        right += hit
        if data.cat[answers[r]] in clothing:
            right_c += hit
            n_c += 1

    # Compatibility AUC: outfit score = mean over all pairs of pieces
    pa, pb, owner = [], [], []
    for oi, (_, items) in enumerate(t["compat"]):
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                pa.append(items[i])
                pb.append(items[j])
                owner.append(oi)
    s = pair_fn(np.array(pa), np.array(pb))
    sums = np.bincount(owner, weights=s, minlength=len(t["compat"]))
    cnts = np.bincount(owner, minlength=len(t["compat"]))
    outfit_scores = sums / np.maximum(cnts, 1)
    return {
        "fitb_accuracy": round(right / max(len(t["fitb"]), 1), 4),
        "fitb_accuracy_clothing_blank": round(right_c / max(n_c, 1), 4),
        "fitb_questions": len(t["fitb"]),
        "compat_auc": round(auc([lab for lab, _ in t["compat"]], outfit_scores), 4),
        "compat_outfits": len(t["compat"]),
    }


def calibration_pairs(data: Data, split: str, rng, n: int = 20000):
    """Real pairs (same outfit) vs. pairs where one piece is swapped for a random one of the same category."""
    a, b, y = [], [], []
    outfits = [o for o in data.tasks[split]["outfits"] if len(o) >= 2]
    for _ in range(n):
        o = outfits[rng.integers(len(outfits))]
        i, j = rng.choice(len(o), 2, replace=False)
        pool = data.by_cat.get(int(data.cat[o[j]]), data.all_train)
        a += [o[i], o[i]]
        b += [o[j], int(pool[rng.integers(len(pool))])]
        y += [1, 0]
    return np.array(a), np.array(b), np.array(y, dtype=np.float64)


def fit_platt(scores, y, steps: int = 500) -> tuple[float, float]:
    a, b = 1.0, 0.0
    s = (scores - scores.mean()) / (scores.std() + 1e-9)
    for _ in range(steps):  # plain gradient descent on logistic loss
        p = 1 / (1 + np.exp(-(a * s + b)))
        a -= 0.5 * np.mean((p - y) * s)
        b -= 0.5 * np.mean(p - y)
    # undo the standardisation so it applies to raw scores
    return float(a / (scores.std() + 1e-9)), float(b - a * scores.mean() / (scores.std() + 1e-9))


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", default="nondisjoint", choices=["nondisjoint", "disjoint"])
    ap.add_argument("--polyvore", type=Path, default=compat.POLYVORE_DIR)
    ap.add_argument("--embeddings", type=Path, default=compat.POLYVORE_EMB)
    ap.add_argument("--out", type=Path, default=compat.MODEL_PATH)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--patience", type=int, default=6, help="stop after this many epochs without improvement")
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--negatives", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--dim", type=int, default=256)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--eval-only", action="store_true")
    args = ap.parse_args()

    import torch
    import torch.nn.functional as F
    torch.manual_seed(args.seed)
    rng = np.random.default_rng(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    print(f"Loading Polyvore ({args.version}) and item vectors...")
    data = Data(compat.load_polyvore(args.version, args.polyvore), compat.load_polyvore_embeddings(args.embeddings))
    print(f"  {len(data.E):,} items, {len(data.train_outfits):,} training outfits, "
          f"categories: {', '.join(data.categories)}")
    for split in ("valid", "test"):
        print(f"  {split}: {len(data.tasks[split]['fitb']):,} FITB questions, "
              f"{len(data.tasks[split]['compat']):,} compatibility outfits")

    E = torch.from_numpy(data.E).to(device)
    C = torch.from_numpy(data.cat).to(device)

    def cosine_fn(a, b):
        return (data.E[a] * data.E[b]).sum(1)

    def model_fn(model):
        model.eval()
        with torch.no_grad():
            H = torch.cat([model.encode(E[k:k + 8192]) for k in range(0, len(E), 8192)])

            @torch.no_grad()
            def fn(a, b):
                out = []
                for k in range(0, len(a), 65536):
                    ia = torch.from_numpy(a[k:k + 65536]).to(device)
                    ib = torch.from_numpy(b[k:k + 65536]).to(device)
                    out.append(model.pair(H[ia], C[ia], H[ib], C[ib]).float().cpu().numpy())
                return np.concatenate(out) if out else np.zeros(0)
        return fn

    report = {"version": args.version, "baseline_fashionclip_cosine": {}, "compat_model": {}}
    for split in ("valid", "test"):
        report["baseline_fashionclip_cosine"][split] = evaluate(cosine_fn, data, split)
    print("\nBaseline (plain FashionCLIP similarity):")
    for split, r in report["baseline_fashionclip_cosine"].items():
        print(f"  {split}: FITB {r['fitb_accuracy']:.1%}  AUC {r['compat_auc']:.3f}")

    if args.eval_only:
        m = compat.CompatModel(dict(np.load(args.out, allow_pickle=False)))
        H = np.concatenate([m.encode(data.E[k:k + 8192]) for k in range(0, len(data.E), 8192)])
        cid = m.cat_ids([data.categories[c] for c in data.cat])

        def np_fn(a, b):
            return m.pair_scores(H[a], cid[a], H[b], cid[b])
        for split in ("valid", "test"):
            report["compat_model"][split] = evaluate(np_fn, data, split)
    else:
        model = build_model(len(data.categories), dim=args.dim).to(device)
        opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
        steps_per_epoch = max(1, len(data.train_outfits) // args.batch_size)
        sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=args.epochs * steps_per_epoch,
                                                    pct_start=0.1)
        unk = len(data.categories) - 1
        qmax = max(len(o) for o in data.train_outfits) - 1
        best, best_state, bad = -1.0, None, 0
        print(f"\nTraining on {device}: up to {args.epochs} epochs x {steps_per_epoch} steps")
        for epoch in range(1, args.epochs + 1):
            model.train()
            t0, total = time.time(), 0.0
            order = rng.permutation(len(data.train_outfits))
            for step in range(steps_per_epoch):
                outs = [data.train_outfits[i] for i in order[step * args.batch_size:(step + 1) * args.batch_size]]
                B, K = len(outs), args.negatives + 1
                q = np.zeros((B, qmax), dtype=np.int64)
                qm = np.zeros((B, qmax), dtype=np.float32)
                cand = np.zeros((B, K), dtype=np.int64)
                for r, o in enumerate(outs):
                    t = rng.integers(len(o))
                    rest = np.delete(o, t)
                    q[r, :len(rest)] = rest
                    qm[r, :len(rest)] = 1
                    pool = data.by_cat.get(int(data.cat[o[t]]), data.all_train)
                    cand[r, 0] = o[t]
                    cand[r, 1:] = pool[rng.integers(len(pool), size=K - 1)]
                q_t, c_t = torch.from_numpy(q).to(device), torch.from_numpy(cand).to(device)
                qm_t = torch.from_numpy(qm).to(device)
                cq, cc = C[q_t].clone(), C[c_t].clone()
                # sometimes hide the category so the "unknown" weighting also learns
                cq[torch.rand_like(cq, dtype=torch.float) < 0.05] = unk
                cc[torch.rand_like(cc, dtype=torch.float) < 0.05] = unk
                hq, hc = model.encode(E[q_t]), model.encode(E[c_t])  # (B,Q,D), (B,K,D)
                s = model.pair(hq[:, :, None], cq[:, :, None], hc[:, None], cc[:, None])  # (B,Q,K)
                s = (s * qm_t[:, :, None]).sum(1) / qm_t.sum(1, keepdim=True)  # mean over the outfit
                loss = F.cross_entropy(s, torch.zeros(B, dtype=torch.long, device=device))
                opt.zero_grad()
                loss.backward()
                opt.step()
                sched.step()
                total += loss.item()
            val = evaluate(model_fn(model), data, "valid")
            print(f"  epoch {epoch:2d}: loss {total / steps_per_epoch:.3f}  valid FITB {val['fitb_accuracy']:.1%}  "
                  f"AUC {val['compat_auc']:.3f}  ({time.time() - t0:.0f}s)", flush=True)
            if val["fitb_accuracy"] > best:
                best, bad = val["fitb_accuracy"], 0
                best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            else:
                bad += 1
                if bad >= args.patience:
                    print("  no improvement for a while, stopping early")
                    break
        model.load_state_dict(best_state)
        fn = model_fn(model)
        ca, cb, cy = calibration_pairs(data, "valid", rng)
        platt = fit_platt(fn(ca, cb).astype(np.float64), cy)
        for split in ("valid", "test"):
            report["compat_model"][split] = evaluate(fn, data, split)
        info = {"version": args.version, "platt": platt, "test": report["compat_model"]["test"],
                "baseline_test": report["baseline_fashionclip_cosine"]["test"],
                "trained": time.strftime("%Y-%m-%d %H:%M")}
        export(model, data.categories, info, args.out)
        print(f"\nSaved model to {args.out}")

        # Check the NumPy copy (used by the API) gives the same answers as PyTorch.
        compat.load.cache_clear()
        m = compat.CompatModel(dict(np.load(args.out, allow_pickle=False)))
        a, b = ca[:2000], cb[:2000]
        np_s = m.pair_scores(m.encode(data.E[a]), m.cat_ids([data.categories[c] for c in data.cat[a]]),
                             m.encode(data.E[b]), m.cat_ids([data.categories[c] for c in data.cat[b]]))
        diff = float(np.abs(np_s - fn(a, b)).max())
        print(f"NumPy vs PyTorch max difference: {diff:.2e}" + ("  OK" if diff < 1e-3 else "  (too large!)"))
        report["numpy_check_max_diff"] = diff

    print("\nResults (higher is better):")
    print(f"  {'':10s} {'FITB':>8s} {'FITB clothing':>14s} {'AUC':>7s}")
    for name, key in (("similarity", "baseline_fashionclip_cosine"), ("compat", "compat_model")):
        for split, r in report[key].items():
            print(f"  {name + ' ' + split:16s} {r['fitb_accuracy']:7.1%} {r['fitb_accuracy_clothing_blank']:13.1%} "
                  f"{r['compat_auc']:7.3f}")
    out = config.REPORTS_DIR / "compat_eval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
