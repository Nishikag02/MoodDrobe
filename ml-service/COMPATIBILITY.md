# Outfit compatibility (complete the look)

## The idea in one paragraph

Before, "complete the look" picked bottoms for a top (and so on) and ranked
them by **style similarity**: how much the bottom *looks like* the top. But
pieces that go together often don't look alike (a white tee and blue jeans).
So we train a small model on **Polyvore Outfits**, 68,306 outfits that real
people put together, to answer a different question: *would these pieces
be worn together?* complete-the-look now ranks candidates by that
compatibility score (70%) blended with style similarity (30%).

FashionCLIP is **not** retrained. Polyvore item photos are turned into the
same 512-number FashionCLIP vectors as the catalogue, and a small network
(about 0.5 million numbers) learns on top of those vectors. That's why training
takes minutes.

## How the model works

1. Each item vector (512 numbers) goes through a small network and becomes a
   256-number "outfit vector".
2. Each **pair of categories** (top + bottom, top + shoes, dress + jacket...)
   has its own learned weighting of those 256 numbers, because what makes a
   top match a bottom is different from what makes it match a bag. This is
   the "type-aware" idea from Vasileva et al., *Learning Type-Aware
   Embeddings for Fashion Compatibility* (ECCV 2018), the paper that made
   Polyvore Outfits.
3. Score = cosine similarity of the two weighted vectors. Higher = goes
   together better. It is also turned into a 0–1 number
   ("compatibility": 0.82) that appears in each result's `why` list.

**Training:** take a real outfit, hide one piece, and show the model the rest
plus 17 candidates: the hidden piece and 16 random pieces of the same
category. The model is rewarded for ranking the real piece first.

## How it's tested

Both are the standard Polyvore benchmarks, on outfits never seen in training:

| Test | What it means | Random guess |
| --- | --- | --- |
| **Fill in the blank (FITB)** | Outfit with one piece missing, 4 options; how often the right one wins | 25% |
| **Compatibility AUC** | Tell real outfits from outfits made of random pieces | 0.50 |

The script also reports **FITB clothing**: only questions where the missing
piece is a top, bottom, outer layer or dress, because that's all the
DeepFashion catalogue has. And it reports both tests for plain FashionCLIP
similarity, the old method, so you can see what the model adds. For
reference, the 2018 paper reports about 55% FITB and 0.86 AUC on the
nondisjoint split.

Results are saved to `data\processed\reports\compat_eval.json`.

## Running it (Windows PowerShell)

### One-time: get access to the data

1. Make a free account at https://huggingface.co and open
   https://huggingface.co/datasets/mvasil/polyvore-outfits (the official
   copy, uploaded by the paper's first author). Read the terms and request
   access.
2. Create a token: https://huggingface.co/settings/tokens → **Create new
   token** → type **Read** → copy it.
3. In PowerShell:

```powershell
cd C:\Users\Singh\Desktop\MoodDrobe\ml-service
.\.venv\Scripts\Activate.ps1
hf auth login        # paste the token when asked (it stays hidden as you paste)
# if "hf" is not found: huggingface-cli login
```

### Run everything

```powershell
powershell -ExecutionPolicy Bypass -File .\run_compat.ps1
```

That runs the three steps below. Each can be stopped with Ctrl+C and re-run.

```powershell
python -m scripts.download_polyvore     # ~2.7 GB into data\raw\polyvore_outfits
python -m scripts.embed_polyvore        # FashionCLIP vectors, ~250k items (GPU: ~30-60 min)
python -m scripts.train_compat          # train + test, a few minutes on GPU
```

Then restart the API. If `data\processed\models\compat.npz` exists,
complete-the-look uses it automatically. Delete or rename that file to go
back to similarity-only ranking.

Useful options:

- `python -m scripts.embed_polyvore --limit 2000`: quick speed check.
- `python -m scripts.train_compat --epochs 5`: short training run.
- `python -m scripts.train_compat --eval-only`: re-test the saved model.
- `$env:MOODDROBE_COMPAT_WEIGHT = "0.5"` before starting the API: change the
  compatibility vs. similarity balance (1 = compatibility only, 0 = old behaviour).

## Files

| File | What it does |
| --- | --- |
| `vectordb/compat.py` | Model (NumPy only at run time), Polyvore readers, DeepFashion → Polyvore category mapping, re-ranking |
| `scripts/download_polyvore.py` | Downloads the dataset from Hugging Face |
| `scripts/embed_polyvore.py` | FashionCLIP vectors for Polyvore items (reads images straight from the parquet files) |
| `scripts/train_compat.py` | Training (PyTorch) and evaluation |
| `run_compat.ps1` | All of the above in one go |
| `vectordb/recommend.py` | complete-the-look calls `compat.rerank_scores` when the model exists |

## Limits worth knowing

- **Licence:** access to Polyvore Outfits is granted for academic and
  non-profit research. The authors don't own the image copyrights. Like
  DeepFashion, it's fine for this project but not for a commercial product
  without checking.
- **Different photos:** Polyvore items are product shots on white
  backgrounds; DeepFashion has many photos of people wearing the clothes.
  FashionCLIP handles both, but scores on the catalogue may be a bit less
  sharp than the Polyvore test numbers suggest.
- **Categories:** DeepFashion tops map to Polyvore "tops", bottoms to
  "bottoms", dresses/jumpsuits to "all-body", and jackets, coats and other
  outer layers to "outerwear". Shoes, bags and jewellery are learned too, but
  the catalogue has none to suggest.
