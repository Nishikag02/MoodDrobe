# MoodDrobe build journal — night of 18–19 Nov 2026

Goal for the night: a working end-to-end demo on the team PC (RTX 3050 Laptop 4 GB, i5-11400H, 16 GB RAM) before the 8:00 AM IST evaluation. Upload an inspiration photo (outfit, café, beach, mountains…) or type a vibe, and get clothing recommendations from the DeepFashion catalogue that match its aesthetic.

Times are IST. All numbers come from the saved reports in `ml-service/data/processed/reports/` (not committed, research-only data).

## What was done, in order

1. **Code (23:45).** Branch `mooddrobe-local` from `origin/feature/ml-service`, plus the ML retrieval/recommendation commits (vector store, Qdrant ingestion, evaluation scripts, category/attribute heads, style recommendations, setup script, products.csv builder). Then the patches: colour matching + attribute filters + "why" explanations (`bb61741`), Polyvore outfit compatibility (`fb52fd4`), mood photos read as scenes (`cf1a22a`), similarity-method comparison (`0a0f1d8`).
2. **Python env (00:30).** `ml-service/.venv` on Python 3.13 (the only Python on the PC; every package installed fine): torch 2.14.1+cu126 (CUDA works), transformers 5.23, qdrant-client 1.20, pandas, FastAPI.
3. **Dataset (00:00–00:50).** DeepFashion Category & Attribute Prediction. The six annotation files were checked (header count = data lines: 289,222 images, 1,000 attributes, 50 categories). `img.zip` (2,681,199,362 bytes) came through the browser and unzipped in 230 s → 289,219 jpgs. Two DeepFashion folders differ only in letter case (`Striped_A-Line_Dress` / `Striped_A-line_Dress`) and merge on Windows; `products.csv` still has 289,222 rows and 0 missing images.
4. **Qdrant (00:44).** Docker Desktop + `qdrant/qdrant:v1.20.0` from `backend/docker-compose.yml`.
5. **FashionCLIP model (01:35).** The 605 MB weights stalled on the slow line, so they came through the browser into `ml-service/models/fashion-clip/`.
6. **GPU embedding (01:37–02:05).** Speed trial 239 images/s (batch 256). All 289,222 images → 58 chunks of 512-d vectors, 0 failures, ~25 min. In parallel on CPU: 5-colour palettes for every product (324/s, 0 missing).
7. **Training and index (02:20).** verify_embeddings: 58/58 chunks valid, 0 duplicates. Category/attribute heads trained in 98 s. Qdrant collection `mooddrobe_catalogue_v2`: 289,222 points with tags and palettes, HNSW + int8, status green.
8. **Evaluation (02:30).** Retrieval, recommendation variety, and the method comparison (numbers below).
9. **API and web demo (02:40).** FastAPI on :8000 (`ml-service/start_api.ps1`), React/Vite web app on :5173 (`frontend/`, Studio + Saved pages, mood reading, outfits, filters, drawer). Checked in the browser end to end.
10. **Backend and auth (02:18).** Postgres container started; Express + better-auth on :3000 (email/password and Google). Sign-up, login and session checked with curl and in the browser; `/api/recommendations/*` proxy works.
11. **Polyvore compatibility (02:25–02:30).** The parquet images came through the browser; 249,109 of 251,008 items embedded at ~320 images/s (1,899 ids not in the parquet files); compatibility model trained in ~4 min; the API was restarted so complete-the-look ranks pairs with it.
12. **Saved items and history (02:32).** New Postgres tables `saved_items` and `user_history` + authenticated routes `/api/saved` and `/api/history` (commit `ba7a1f9`).
13. **Disjoint check (02:35).** Polyvore *disjoint* split trained separately (`compat_disjoint.npz`) to get an honest number on outfits whose items were never seen in training.

## Key decisions and why

- **Qdrant in Docker, locally.** Same setup as the compose file the team already had; 289k vectors fit easily; p50 search 12 ms. Local mode (`QDRANT_PATH`) stays as the fallback.
- **Browser downloads.** The PC's connection reached only ~48 KB/s from scripts (Google Drive quota pages, Hugging Face Xet stalls), while the browser was much faster. So the big files (img.zip, FashionCLIP weights, Polyvore parquets) were fetched in the browser and checked by exact byte size.
- **Local model folder + `start_api.ps1`.** The API must find the weights in `ml-service/models/fashion-clip` through `FASHIONCLIP_MODEL`. Starting uvicorn without it gave HTTP 500, so a one-click launcher sets it.
- **Full catalogue, not a subset.** The speed trial put the whole run at ~25 min, so all 289,222 images were embedded.
- **Nondisjoint vs disjoint Polyvore.** The live model uses the larger *nondisjoint* split (more training outfits). The *disjoint* split (test outfits share no items with training) was trained separately as the stricter, more honest generalisation check; it does not replace the live model.
- **SQL file instead of `drizzle-kit push`** for the new tables. The project has no migration history, and push could have tried to alter the existing auth tables; `CREATE TABLE IF NOT EXISTS` cannot.
- **Saved items in the browser for now.** The web app stores likes in localStorage; the backend routes are ready for the frontend to switch to them.

## Results

**Category / attribute models (test split):** category top-1 71.3%, top-3 89.5%, top-5 94.6%; top/bottom/full-body 90.6%; attributes recall@3 0.321, recall@5 0.415.

**Retrieval** (1,000 test queries vs the 249,222 train+val index, relevant = same category): P@1 0.656, P@5 0.614, P@10 0.598, P@20 0.578; Hit@10 0.908, Hit@20 0.947; MRR@20 0.746; random P 0.111. Qdrant latency p50 12.3 ms, p95 37.0 ms. Most common confusions: Tee↔Tank, Tee→Blouse, Cardigan→Sweater, Jacket→Blazer, Dress↔Romper.

**Recommendations** (500 queries, top 12): plain nearest neighbours — style 0.790, variety (ILD) 0.247, 3.3 categories, 58% same category; your_style (diversity 0.3) — style 0.769, ILD 0.304, 6.2 categories, 24% same category. Garment-type detection 91.4%.

**Method comparison** (P@10 / MRR): random 0.098 / 0.220; FashionCLIP cosine 0.577 / 0.735; z-score cosine 0.591 / 0.749; category-head space 0.599 / 0.708; **cosine + category re-rank 0.630 / 0.753 (best)**; + attribute re-rank 0.585 / 0.741; + colour re-rank 0.576 / 0.741 (colour match of top 10 0.533 → 0.582); Qdrant HNSW int8 0.577 / 0.741 (finds 92.3% of the exact top 10). Text queries: P@10 0.509, MRR 0.608.

**Outfit compatibility, Polyvore nondisjoint (test):** fill-in-the-blank 70.6% (clothing blanks 69.5%), AUC 0.939, vs plain FashionCLIP similarity 51.1% / 0.739. Random FITB = 25%.

**Outfit compatibility, Polyvore disjoint (test; no test item is seen in training — the stricter check):** FITB 67.7% (clothing blanks 66.7%), AUC 0.908, vs plain FashionCLIP similarity 52.4% / 0.752. 14,248 FITB questions, 29,122 outfits; 2,065 test questions were skipped because one of their items has no image vector. Trained on 16,993 outfits into a separate `compat_disjoint.npz`; the live API keeps the nondisjoint model.

**Speed:** catalogue embedding 239–380 images/s on the GPU; Polyvore 314–323 images/s; API ~70 ms embed + ~210 ms recommend per photo once warm (first request after a restart ~30 s).

## Known gaps

- No plain-CLIP row in the comparison (needs another 600 MB download).
- The web app still keeps saved items in localStorage; the backend `/api/saved` and `/api/history` routes are not wired into it yet. The /dashboard page after login is a template placeholder.
- Google login is configured but was not tested.
- Relevance for retrieval is "same category" (DeepFashion has no ground truth for "fits the vibe"); mood-photo quality is judged by eye.
- 3 catalogue paths collapse into duplicates on Windows (case-only folder names); 1,899 Polyvore items have no image.
- Everything runs on one PC; nothing is deployed.

## Next steps

- Wire the frontend to `/api/saved` and `/api/history` for logged-in users.
- Public showcase link via a tunnel from this PC (see HANDOVER.md).
- A small user study for "fits the vibe"; garment detection/cropping for street photos; fine-tuning on consumer-to-shop pairs; a licensed shoppable catalogue.
