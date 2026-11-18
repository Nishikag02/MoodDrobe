# MoodDrobe handover (read this first)

Last updated: 2026-11-19 01:05 IST. **Deadline: project evaluation at 8:00 AM IST, 19 Nov.** Priority is a working end-to-end demo.

## Goal
Upload any inspiration photo (a café, beach, mountains, bookstore, city street, moodboard, or an outfit) and get clothing recommendations that match its aesthetic. Dataset: DeepFashion Category & Attribute Prediction (289,222 images, 46 categories, 1,000 attributes). Research-only licence: never commit or share the data.

## Deadline situation
- Evaluation at **8:00 AM IST, Thu 19 Nov 2026** (02:30 UTC). Work started around 01:00 IST.
- **Must be ready:** the full catalogue embedded and loaded in Qdrant, the API on :8000, the web demo working for clothing photos and mood photos (café, beach, mountains, bookstore, city), evaluation numbers (retrieval, recommendations, method comparison) on the slides, and the demo script rehearsed.
- **Can slip** (show as "in progress / future work"): the Polyvore compatibility model (complete-the-look still works without it, using garment-type rules), the plain-CLIP comparison row, Express/Postgres integration, user accounts and likes storage.
- Fallback if embedding is too slow: embed val+test first (80k images) and demo on that; say so honestly on the slides.

## Full planned scope
1. Upload any inspiration (outfit, single garment, scenery, interior, moodboard, artwork, text vibe).
2. Understand it: clothing vs mood, scene, vibe words, colours, garment type and attributes.
3. Translate it into fashion terms (scene → what to wear; vibe → style prompt).
4. Retrieve from the catalogue with FashionCLIP + Qdrant.
5. Recommend: your style (varied), complete the look (pairs), closest matches, with colour matching, attribute filters, and a "why" for each item.
6. Personalise: likes and dislikes (Rocchio), "more like this", text steer ("more formal").
7. Learn outfit compatibility from Polyvore Outfits to rank complete-the-look.
8. Evaluate: retrieval metrics, recommendation variety, method comparison (cosine variants, re-rankers, Qdrant ANN, text, plain CLIP vs FashionCLIP), category/attribute accuracy, compatibility AUC/FITB.
9. Product: React web app → Express → FastAPI ML service → Qdrant; later Postgres/Supabase for users, likes and catalogue.

## Built vs in progress
- **Built and tested** (on synthetic data in the cloud, and the code compiles on this PC): vector store and ingestion, evaluation scripts, category and attribute models, style recommendations (MMR), complete the look, moodboards, vibes, scene reading for mood photos, colour palettes and matching, attribute filters, "why" explanations, method comparison, Polyvore compatibility code, Express proxy, web demo (frontend folder), one-shot setup script.
- **In progress on this PC (as of 01:05 IST):** unzip done (289,219 jpg files on disk, see note below), products.csv built (289,222 rows, 0 missing). Now downloading the FashionCLIP model weights (the first try stalled on a slow connection and was restarted over plain HTTP), then the speed trial, full GPU embedding, colours, training, Qdrant, evals and the API. The Polyvore download (`scripts.download_polyvore`) is running at the same time and shares the network.
- **Not started:** user accounts and storing likes in Postgres; deployment.

## How it works end to end
1. **Web app** (`frontend` folder): the user uploads 1 to 8 photos or types a vibe; the app calls `/ml/recommend` (Vite proxies it to FastAPI :8000).
2. **Embedding:** each photo is turned into a 512-number FashionCLIP vector (image and text share one space).
3. **Clothing or mood?** Zero-shot: the vector is compared with "a photo of clothing..." vs "a photo of a landscape / room / cafe..." prompts. A close match to a catalogue item (cosine ≥ 0.8) also counts as clothing. `mode` can force either.
4. **Mood photos:** matched to 16 scenes (cozy cafe, beach, mountains, bookstore, city street...). Each scene has a "what to wear there" text, and the photo also gets its top vibe words (25 vibes, e.g. "earthy", "coastal"). Query = 50% scene outfit text + 30% vibe words + 20% photo. The scene's dominant colours become the colours to match.
5. **Clothing photos:** used directly; the category model detects the garment type (top / bottom / full) for complete-the-look.
6. **Style vector:** photos are averaged (moodboard); likes pull it closer and dislikes push it away; an optional text steer nudges it.
7. **Qdrant search:** about 450 nearest neighbours from 289k vectors (HNSW, int8 in RAM), with filters (attributes, colours, excluded items).
8. **Re-ranking:** MMR for variety (at most 3 per category) + colour match boost → `your_style`. Complementary garment types (+ Polyvore compatibility when trained) → `complete_the_look`. Plain nearest → `closest_matches`.
9. **Explain:** each item gets `why` lines (style similarity, matching colours, attributes, vibe), plus the detected garment, vibes and attributes for the query.
10. **Display:** the web app shows the photo reading (scene, vibes, colour swatches) and product cards from `/catalogue/image/{id}`.

## Where things are
- Project folder: `C:\Users\Singh\Desktop\MoodDrobe`, git branch **`mooddrobe-local`**. Nothing is pushed. **Ask the user before any push or PR.**
- Commits on top of the original code (`126c060` = products.csv builder, the last bundle commit): `bb61741` (colour matching, attribute filters, "why" explanations), `fb52fd4` (Polyvore outfit compatibility), `cf1a22a` (mood photos read as scenes), `0a0f1d8` (similarity-method comparison, `scripts\compare_methods.py`).
- ML service: `ml-service\` (FastAPI + FashionCLIP `patrickjohncyh/fashion-clip`, 512-d vectors). Key code: `vectordb\` (store.py Qdrant, recommend.py, vibes.py scenes and vibes, colors.py, heads.py category/attribute models, compat.py, api.py routes), `scripts\`.
- Data: `ml-service\data\raw\deepfashion\` (Img\img\..., list_*.txt), `data\catalogue\metadata\products.csv`, embeddings in `data\processed\catalogue_embeddings\full_catalogue_v2\{train,val,test}\chunk_XXXXX.npz` (5,000 per chunk, 58 chunks). **Never delete embedding chunks.** Reports go in `data\processed\reports\`, models in `data\processed\models\`. `ml-service/data/catalogue/`, `data/raw/` and `data/processed/` are listed in `.git\info\exclude` so git ignores them.
- Image count note: 289,219 jpgs on disk (+ one stray `.7z` stub from the zip) against 289,222 listed. DeepFashion has two folders that differ only in letter case (`Striped_A-Line_Dress` / `Striped_A-line_Dress`), which merge on Windows, so a few of those listed paths resolve to the same file. build_products_csv reports 0 missing; the effect is a handful of duplicate images, which is harmless.
- `img.zip` (2.68 GB) is still in `C:\Users\Singh\Downloads`; the user can delete it once the pipeline works.
- Express backend: `backend\` (`/api/recommendations/*` proxies to :8000). Optional for the demo.
- Web demo: `frontend\` (React + Vite); see `frontend\DEMO.md`. It calls `/ml/...`, which Vite proxies to http://127.0.0.1:8000.
- Full guide: `ml-service\RUN_GUIDE.md`. Details: `ml-service\RETRIEVAL.md`, `ml-service\COMPATIBILITY.md`.
- Deck: https://claude.ai/artifact/WmSvHp5qMgNQeZ8ycRbgzb. Demo script: https://claude.ai/artifact/SqVvjDKzrr2mrWZvb91aq7. Plan: https://claude.ai/artifact/CAi7YwD8jiFbbtJX1UDsid

## Machine
RTX 3050 Laptop GPU (4 GB), i5-11400H, 16 GB RAM, Python 3.13 venv at `ml-service\.venv` (torch 2.14.1+cu126, CUDA works). Docker Desktop running; Qdrant container `mooddrobe_qdrant` (v1.20.0) on :6333, readyz OK. Internet is slow (Hugging Face Xet downloads stalled; set `$env:HF_HUB_DISABLE_XET="1"` if a model download hangs).

## Pipeline status (run in this order, from ml-service with the venv active)
Check each output to see where it got to. Every step can be resumed or re-run safely.
1. ✅ Unzip img.zip into `data\raw\deepfashion\Img` → 289,219 jpgs (see the note above).
2. ✅ `python -m scripts.build_products_csv` → 289,222 rows (train 209,222 / val 40,000 / test 40,000), 0 images missing.
3. ✅ Speed trial 239 img/s; full run DONE (58 chunks, 0 failed). Command: `python -m scripts.embed_full_catalogue` (log `data\processed\embed_full.log`). Needs $env:FASHIONCLIP_MODEL set (see Progress log).
4. ✅ `python -m scripts.extract_colors --workers 3` DONE (289,222 palettes).
5. ✅ DONE: `python -m scripts.verify_embeddings` → `python -m scripts.train_heads` → `python -m scripts.ingest_qdrant --force`.
6. ✅ retrieval + recommendations DONE (see log); ⏳ compare_methods running (without --clip-subset). `python -m scripts.evaluate_retrieval --num-queries 1000`, `python -m scripts.evaluate_recommendations`, `python -m scripts.compare_methods --num-queries 1000 --text --clip-subset 20000`.
7. ✅ API up + smoke test OK. Start with `start_api.ps1` (sets FASHIONCLIP_MODEL). API: `uvicorn recommend_server:app --host 0.0.0.0 --port 8000` (keep the window open), then `python -m scripts.smoke_test_api`. Docs at http://localhost:8000/docs.
8. Frontend: `cd frontend; pnpm install; pnpm dev` (see DEMO.md).
9. ✅ DONE (compat model trained, API restarted). Polyvore compatibility: `python -m scripts.download_polyvore` (HF login already done; already running at 01:05 IST), then `python -m scripts.embed_polyvore --limit 2000`, `python -m scripts.embed_polyvore`, `python -m scripts.train_compat`, then restart the API. Or `.\run_compat.ps1 -SkipDownload`.
Shortcut for steps 2 to 7: `powershell -ExecutionPolicy Bypass -File .\setup_and_run.ps1`.

## API (port 8000)
`POST /recommend` (multipart `files` 1 to 8, `steer`, `tags`, `avoid_tags`, `colors`, `match_colors`, `color_weight`, `only_colors`, `mode`=auto|clothing|mood, `k`, `diversity`), `POST /recommend/vibe` {vibe, tags, colors, ...}, `POST /recommend/for-you`, `GET /recommend/similar/{id}?match_colors=true`, `GET /recommend/options`, `GET /catalogue/image/{id}`, `POST /search/image`, `POST /search/text`.
Response sections: `inputs` (per photo: kind, scene, fashion_reading, colors), `your_style`, `complete_the_look`, `closest_matches`, `detected`, `vibes`, `attributes`, `query_colors`; each item has `why`, `match`, `color_match`, `tags`, `color_names`.

## How mood photos work
Clothing vs mood is decided zero-shot. A mood photo is matched to one of 16 scenes (`SCENES` in vibes.py), each with a "what to wear there" text. The query is 50% scene outfit text, 30% top vibe words and 20% the photo, then re-ranked toward the scene's colours. Editing the lists needs no retraining.

## Evaluation protocol
Queries are test-split images, the index is train+val, and a result is relevant if it has the same category. Metrics: P@K, Recall@K, HitRate, MRR, latency; recommendation variety (ILD, distinct categories). Only put numbers on slides that come from the saved reports.

## User preferences
Beginner-friendly PowerShell commands, complete code when replacing scripts, minimal changes, protect embeddings and the user's own edits, and confirm before pushing. Never claim a check that wasn't actually run.

## Future prospects
- **Shoppable catalogue:** replace or extend DeepFashion (research-only) with a licensed retail catalogue or affiliate feeds (prices, sizes, links), loaded through the same embedding and ingestion scripts.
- **Garment segmentation / detection:** detect and crop each garment in a street photo (e.g. YOLO/SAM-based) so every piece of an outfit is searched separately ("shop the look").
- **Fine-tuning:** fine-tune FashionCLIP (or train a projection head) on DeepFashion's consumer-to-shop pairs and on Polyvore for better retrieval and compatibility.
- **Stronger scene understanding:** a general vision-language model (e.g. a captioning model) to describe mood photos in free text, instead of a fixed list of 16 scenes.
- **Personalisation:** store likes, dislikes and wardrobe items in Postgres/Supabase; learn a per-user style vector; "for you" feed; feedback-driven re-ranking.
- **Better moodboards:** detect several distinct looks on one board (clustering) and return one outfit per look; Pinterest board import.
- **Ranking quality:** learned diversity and novelty, seasonal and weather awareness, budget and size filters, sustainability tags.
- **Full outfits:** generate complete outfits (top + bottom + shoes + outer layer + accessories) scored by the compatibility model.
- **Evaluation:** a small user study for "fits the vibe" and outfit compatibility (no ground truth in DeepFashion), plus A/B tests in the app.
- **Product:** mobile app, user accounts, sharing outfits, cloud deployment (GPU inference server, managed Qdrant), caching and monitoring.

## Progress log
(Times are IST, 19 Nov 2026 unless marked.)
- 18 Nov ~23:45 — Branch `mooddrobe-local` created from origin/feature/ml-service, bundle fast-forwarded to 126c060. Machine checked (RTX 3050 4 GB, 15.7 GB RAM, Python 3.13 only, Docker installed).
- 00:30 — venv `ml-service\.venv` ready: torch 2.14.1+cu126 (CUDA OK), transformers 5.23.0, qdrant-client 1.20.0, pandas 3.1.1.
- 00:20–00:40 — Patches applied: bb61741 (colour), fb52fd4 (Polyvore compat), later cf1a22a (scenes), 0a0f1d8 (compare_methods).
- 00:44 — Docker Desktop started; Qdrant container `mooddrobe_qdrant` up, readyz 200.
- 00:45–00:50 — DeepFashion: all 6 list_*.txt verified (counts match); img.zip (2,681,199,362 B, browser download) unzipped in 230 s → 289,219 jpgs; products.csv built (289,222 rows, 0 missing).
- 00:55–01:05 — **Problem:** internet ~48 KB/s; FashionCLIP weights (605 MB) download stalled via Hugging Face Xet. Config/tokenizer files copied to `ml-service\models\fashion-clip\`; a resumable curl download of model.safetensors runs into `ml-service\data\models\fashion-clip\`. User asked to download it in the browser (it goes to Downloads). Once verified (605,157,890 bytes), put it in `ml-service\models\fashion-clip\` and set `$env:FASHIONCLIP_MODEL="C:\Users\Singh\Desktop\MoodDrobe\ml-service\models\fashion-clip"` for every later command, including uvicorn.
- 01:07 — Polyvore download (`scripts.download_polyvore`, PIDs 12528/24372, started outside this session) is still running and sharing the slow connection. Stopping it from the automated session was blocked by a permission check; the user should close its window. The user will download the Polyvore files in the browser instead; they go into `ml-service\data\raw\polyvore_outfits` (root: polyvore_item_metadata.json, categories.csv, polyvore_outfit_titles.json; `nondisjoint\`: train/valid/test.json, fill_in_blank_*.json, compatibility_*.txt; `data\nondisjoint\`: *.parquet).
- 01:10 — Polyvore check: all small files are already present in `data\raw\polyvore_outfits` (metadata, categories.csv, nondisjoint\*.json/*.txt; polyvore_outfit_titles.json not downloaded, not needed by the script). Missing only `data\nondisjoint\{validation,test,train}.parquet` (234 MB / 447 MB / 1.92 GB). User downloads them in the browser from `https://huggingface.co/datasets/mvasil/polyvore-outfits/resolve/main/data/nondisjoint/<name>.parquet`; a watcher moves each one from Downloads into `data\raw\polyvore_outfits\data\nondisjoint\` once the size matches exactly. If the watcher is no longer running, move them by hand.
- 01:10 — At the user's request, stopped the Polyvore download process and the background curl of model.safetensors (the partial file in `ml-service\data\models\fashion-clip\` can be ignored). Docker/Qdrant are left running. Everything still to download (browser, signed in to HF): `patrickjohncyh/fashion-clip/resolve/main/model.safetensors` (605,157,890 B) → `ml-service\models\fashion-clip\`; Polyvore `data/nondisjoint/{validation,test,train}.parquet` → `ml-service\data\raw\polyvore_outfits\data\nondisjoint\`.
- 01:35 — FashionCLIP weights arrived via browser (605,157,890 B) → `ml-service\models\fashion-clip\model.safetensors` (+ config/tokenizer files). **Every command that loads the model needs** `$env:FASHIONCLIP_MODEL="C:\Users\Singh\Desktop\MoodDrobe\ml-service\models\fashion-clip"` (and optionally `$env:HF_HUB_OFFLINE="1"`), including uvicorn. Partial curl copy removed.
- 01:36 — Speed trial: 1,000 test images in 4 s = **239 images/s** on GPU (batch 256). Trial chunk `test\chunk_00000.*` deleted.
- 01:37 — **Full embedding started** (all splits, `python -u -m scripts.embed_full_catalogue`), log `ml-service\data\processed\embed_full.log`. **Colour extraction started** in parallel (`scripts.extract_colors --workers 3`), log `ml-service\data\processed\extract_colors.log`. Both resumable: if interrupted, just re-run the same command (with FASHIONCLIP_MODEL set for embedding).
- 02:05 — User reported "GPU not used". Checked: embedding runs on cuda (log "Device: cuda ... batch size 256"; nvidia-smi lists PID 15856, ~1.1 GB VRAM). GPU utilisation reads ~0% because the GPU needs only ~1 s per 5,000 images; the CPU (jpg decode/resize) is the bottleneck, and Task Manager's default "3D" graph doesn't show CUDA work. Nothing changed. Speed 240 img/s with colours running, 350–380 img/s after.
- 02:05 — **Colour extraction DONE**: 289,222 palettes in `data\processed\colors\` (324/s, 0 images missing).
- 02:07 — Embedding: train 42/42, val 8/8, test 6/8 chunks done.
- 02:10 — **Embedding DONE**: 58 chunks (train 42, val 8, test 8), 289,222 images, 0 failed. Started `data\processed\run_after_embed.ps1` (verify_embeddings → train_heads → ingest_qdrant --force → evaluate_retrieval --num-queries 1000 → evaluate_recommendations; logs in `data\processed\logs\`). If it stops, re-run that script or the failed step by hand (with FASHIONCLIP_MODEL set).
- 02:20 — ✅ verify_embeddings: 58/58 chunks valid, 0 products without a vector, 0 duplicate IDs (report `data\processed\reports\verify_full_catalogue_v2.json`).
- 02:22 — ✅ train_heads (98 s) → `data\processed\models\heads.npz`. Test: category top-1 0.713 / top-3 0.895 / top-5 0.946, top/bottom/full 0.906; attributes recall@3 0.321 / @5 0.415. (Val: 0.718 / 0.898 / 0.945, 0.907; 0.324 / 0.419.)
- 02:22 — ⏳ ingest_qdrant --force running (collection `mooddrobe_catalogue_v2`, with attribute tags + colour palettes).
- 02:25 — ✅ Polyvore parquets all in `data\raw\polyvore_outfits\data\nondisjoint\` (test 447,480,804 B; validation 234,349,102 B; train 1,919,749,731 B). Polyvore dataset complete; **do not re-run download_polyvore**. Next for Polyvore (after the demo works): `embed_polyvore --limit 2000` → `embed_polyvore` → `train_compat` → restart API.
- 02:28 — ✅ ingest_qdrant: 289,222 points in `mooddrobe_catalogue_v2` (148 s), with attribute tags + colours.
- 02:29 — ✅ evaluate_retrieval (1,000 test queries vs train+val, relevant = same category): P@1 0.656, P@5 0.614 / Hit@5 0.858, P@10 0.598 / Hit@10 0.908, P@20 0.578 / Hit@20 0.947, MRR@20 0.746; random P 0.111; Qdrant p50 12.3 ms, p95 37.0 ms. Report `data\processed\reports\retrieval_eval_category_20261119_015244.json`.
- 02:32 — ✅ evaluate_recommendations (500 queries, top 12): plain NN style 0.790 / ILD 0.247 / 3.3 cats / sameCat 0.581; your_style div 0.3: 0.769 / 0.304 / 6.2 / 0.241; div 0.5: 0.750 / 0.337 / 6.3 / 0.236. Garment-type detection 0.914. Report `data\processed\reports\recommendation_eval_20261119_015526.json`.
- 02:40 — ✅ **API running on :8000** in its own window ("MoodDrobe API :8000"). Start it with `powershell -ExecutionPolicy Bypass -File C:\Users\Singh\Desktop\MoodDrobe\ml-service\start_api.ps1` (new uncommitted helper that sets FASHIONCLIP_MODEL; launching uvicorn without that variable gives HTTP 500 on /recommend because the weights aren't in the HF cache). ✅ smoke_test_api: all requests succeeded (photo → Tee detected 0.87, complete_the_look = shorts/leggings/skirts; vibes "old money", "90s grunge" OK). First photo ~7 s (model warm-up).
- 02:41 — ⏳ compare_methods --num-queries 1000 --text running (no --clip-subset: plain CLIP would be another 600 MB download). Log `data\processed\logs\compare_methods.log`.
- Next: frontend (`cd frontend; pnpm install; pnpm dev`, see DEMO.md), then Polyvore: embed_polyvore --limit 2000 → embed_polyvore → train_compat → restart API.
- 02:48 — ✅ **Web demo running** at http://localhost:5173 (window "MoodDrobe web :5173", `cd frontend; pnpm dev`). `/ml` proxy reaches the API ("Model online"). Browser test: preset "cozy coffeeshop on a rainy afternoon" → Winter Cozy 93%, outfits with real images. NOTE: frontend\DEMO.md says to start the API with plain uvicorn; on this PC use `ml-service\start_api.ps1` instead (DEMO.md not edited — user's uncommitted file). The frontend folder has the user's uncommitted changes; leave them alone.
- 02:48 — compare_methods partial (P@10 / MRR): random 0.098/0.220; fashionclip_cosine 0.577/0.735; zscore 0.591/0.749; category_head_space 0.599/0.708; +category_rerank 0.630/0.753; +attribute_rerank 0.585/0.741; +colour_rerank 0.576/0.741.
- 02:55 — ✅ compare_methods DONE → `data\processed\reports\method_comparison_20261119_015937.md` (+ .json). P@10 / MRR: random 0.098/0.220; fashionclip_cosine 0.577/0.735; zscore 0.591/0.749; category_head_space 0.599/0.708; **cosine+category_rerank 0.630/0.753 (best)**; +attribute_rerank 0.585/0.741; +colour_rerank 0.576/0.741 (colour match 0.533→0.582); qdrant_hnsw_int8 0.577/0.741 (92.3% of exact top-10, 9.7 ms). Text queries: P@10 0.509, MRR 0.608. No plain-CLIP row (not downloaded).
- 02:57 — Polyvore trial: `embed_polyvore --limit 2000` → 314 img/s on GPU (image column 'image', id column 'item_id'; 251,008 items needed). ⏳ Full `embed_polyvore` then `train_compat` running in background (logs `data\processed\logs\embed_polyvore.log`, `train_compat.log`). When done: restart the API (close the API window, run start_api.ps1 again) and read `data\processed\reports\compat_eval.json`.

## How to start every service (checked 02:20 IST)
1. **Docker Desktop** (Start menu). Then `cd C:\Users\Singh\Desktop\MoodDrobe\backend; docker compose up -d` → `mooddrobe_qdrant` (:6333) and `mooddrobe_postgres` (:5432, db `mydb`). (`superhuman-postgres` on :5436 belongs to another project; ignore it.)
2. **ML API :8000**: `powershell -ExecutionPolicy Bypass -File C:\Users\Singh\Desktop\MoodDrobe\ml-service\start_api.ps1` (window "MoodDrobe API :8000").
3. **Express backend :3000** (auth + `/api/recommendations/*` proxy): `cd C:\Users\Singh\Desktop\MoodDrobe\backend; pnpm dev` (window "MoodDrobe backend :3000"). Uses the existing `backend\.env` (DATABASE_URL → local Postgres, BETTER_AUTH_SECRET, Google OAuth keys). Auth tables (user, session, account, verification) already exist; no migration needed.
4. **Web app :5173**: `cd C:\Users\Singh\Desktop\MoodDrobe\frontend; pnpm dev` (window "MoodDrobe web :5173").

**Demo login (local test account, created 02:18 IST):** email `demo@mooddrobe.test`, password in `DEMO_LOGIN.local.txt` in the project folder (git-ignored). Log in at http://localhost:5173/login → redirects to the protected /dashboard.

- Auth = better-auth (email+password and Google) at `/api/auth/*`. Checked with curl: sign-up/email 200, sign-in/email 200, get-session with cookie 200 (returns user), without cookie `null`. Browser login on :5173 works.
- The frontend login uses the backend (`VITE_BACKEND_APP_URL=http://localhost:3000`). The Studio (/) and Saved (/saved) pages call the ML API directly via the Vite `/ml` proxy; **saved/liked items are stored in the browser's localStorage** (`frontend\src\lib\saved.ts`), not in the backend. There is no saved-items route in Express yet. The /dashboard page is still the template placeholder.
- Express proxy check: GET http://localhost:3000/api/recommendations/options → 200 (same data as :8000).
- 02:20 — All services checked/started: Qdrant up; **Postgres `mooddrobe_postgres` started** (was down); **Express backend started** on :3000; auth tested (demo user, see "How to start every service"); ML API :8000 and web :5173 up. Qdrant collection: status green, 289,222 points (all indexed), 512-d Cosine, on_disk.
- 02:20 — Polyvore embedding DONE: 249,109 of 251,008 items (1,899 ids not present in the parquet files, 0 unreadable), 832 s. ⏳ train_compat running (epoch 20: valid FITB 69.7%, AUC 0.942).
- 02:28 — ✅ **train_compat DONE** → `data\processed\models\compat.npz`, report `data\processed\reports\compat_eval.json`. Test: FITB 70.6% (clothing blank 69.5%), AUC 0.939 vs FashionCLIP-cosine baseline FITB 51.1%, AUC 0.739 (valid: 69.8% / 0.940 vs 50.5% / 0.740). 7,347 FITB questions, 16,449 outfits.
- 02:30 — ✅ API restarted (start_api.ps1) so complete-the-look uses the compatibility model; smoke test OK (Tee → shorts/skirt/leggings/jeans/sweatpants, "why" shows "Outfit compatibility ... (learned from Polyvore outfits)"). First request after a restart ~30 s (warm-up), then ~70 ms embed + ~210 ms recommend. **Before the demo: upload one photo once to warm up.**
- **STATE: full pipeline complete, all services running** (Docker/Qdrant/Postgres, API :8000, backend :3000, web :5173). Remaining optional: plain-CLIP comparison row (needs a 600 MB download), saved items in Postgres, the dashboard page.
- 02:32 — ✅ **Saved items + history API** (commit `ba7a1f9`, backend only). New tables `saved_items` (unique user_id+product_id) and `user_history`, created with `backend\sql\0001_saved_items_user_history.sql` (idempotent; apply with `Get-Content sql\0001_saved_items_user_history.sql | docker exec -i mooddrobe_postgres psql -U postgres -d mydb`). Routes in `backend\src\app\routes\user-data.ts`, all need the better-auth cookie (401 `{"error":"Not logged in"}` otherwise):
  - `GET /api/saved` → `{"items":[{product_id,image_url,category_name,source,created_at}]}` newest first
  - `POST /api/saved` `{product_id, image_url?, category_name?, source?}` → 201 `{"item":{...}}` (upsert; re-save only overwrites sent fields)
  - `DELETE /api/saved/:product_id` → `{"deleted":true|false}`
  - `GET /api/history?limit=20` (1–100) → `{"items":[{id,kind,text,scene,created_at}]}` newest first
  - `POST /api/history` `{kind:'vibe'|'photo', text, scene?}` → 201 `{"item":{...}}`
  Tested with curl (demo cookie; test rows deleted afterwards). CORS for :5173 with credentials incl. DELETE preflight OK. Backend window restarted. Frontend wiring is left to the demo-app thread (frontend not edited).
- 02:33 — Polyvore **disjoint** text files downloaded to `data\raw\polyvore_outfits\disjoint\`. ⏳ Training `train_compat --version disjoint --out data\processed\models\compat_disjoint.npz` with `MOODDROBE_REPORTS_DIR=data\processed\reports\disjoint` (so the live `compat.npz` and `compat_eval.json` are not touched); result copied to `data\processed\reports\compat_eval_disjoint.json`. Log `data\processed\logs\train_compat_disjoint.log`.

## Showcase online (public link from this PC)
Everything keeps running on this PC (GPU, Qdrant, Postgres); a **Cloudflare quick tunnel** gives one public https URL to the web app on :5173. Vite forwards `/ml` → :8000 and (once the frontend adds it) `/api` → :3000, so one URL covers the whole app.

1. **Get cloudflared once** (55 MB, official): in the browser download https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe and save it as `C:\Users\Singh\Desktop\MoodDrobe\tools\cloudflared.exe` (git-ignored).
2. Start Docker, the API (`start_api.ps1`), the backend (`pnpm dev` in backend) and the web app (`pnpm dev` in frontend) as usual.
3. Start the tunnel in its own window:
   `C:\Users\Singh\Desktop\MoodDrobe\tools\cloudflared.exe tunnel --url http://localhost:5173`
   It prints a URL like `https://random-words.trycloudflare.com`. Share that.
4. **The URL changes every time the tunnel restarts.** No account is needed; quick tunnels have no uptime guarantee.
5. **Keep the PC on, plugged in and awake** (Settings → System → Power: screen/sleep "Never" while presenting). Closing the laptop lid or sleeping kills the link.
6. **Fallback:** demo on http://localhost:5173 on this PC.

Required code settings (status 02:45 IST):
- Backend ✅ (`backend/src/lib/auth.ts`): `trustedOrigins` includes `https://*.trycloudflare.com` (+ optional `EXTRA_TRUSTED_ORIGINS` in backend/.env). Checked: sign-in with Origin `https://x.trycloudflare.com` → 200, unknown origin → 403.
- Frontend (owned by the demo-app thread, not edited here):
  - `frontend/vite.config.ts` → in `server` add `allowedHosts: ['.trycloudflare.com']` (otherwise Vite answers "Blocked request. This host is not allowed"), and a proxy `'/api': { target: 'http://127.0.0.1:3000' }` (no rewrite, keep the Origin header) next to `/ml`.
  - `frontend/src/lib/auth-client.ts` → `baseURL` must be the page's own origin (e.g. `window.location.origin`) instead of `VITE_BACKEND_APP_URL=http://localhost:3000`; for a visitor's browser "localhost:3000" is their own computer, so login over the tunnel fails otherwise.
- Cookies: the backend's cookies come back through the Vite proxy as host-only cookies for the tunnel domain; https at the edge is fine.
- Security: the public URL exposes the whole app (sign-up, uploads). Stop the tunnel window (Ctrl+C) after the showcase.
