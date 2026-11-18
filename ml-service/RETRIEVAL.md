# Catalogue search and style recommendations

Step-by-step commands for everything: see `RUN_GUIDE.md`.

These steps reuse the FashionCLIP vectors already saved in
`data/processed/catalogue_embeddings/full_catalogue_v2`. None of them re-runs
the model over the catalogue, and none of them edits or deletes chunk files.

All commands are PowerShell, run from the `ml-service` folder with the venv active:

```powershell
cd C:\Users\nishi\OneDrive\Desktop\MoodDrobe\MoodDrobe\ml-service
.\.venv\Scripts\Activate.ps1
pip install -r requirements-vectordb.txt
```

## 1. Check the saved chunks

Safe to run while `embed_catalogue.py` is still working (it only reads).

```powershell
python -m scripts.verify_embeddings --inspect   # shows the arrays inside one chunk
python -m scripts.verify_embeddings             # checks every chunk
```

It prints one line per chunk and a summary per split: valid chunks out of
expected (42 train, 8 val, 8 test), vector counts, products with no vector,
and missing chunk numbers. A report is saved to `data/processed/reports/`.

The scripts look for the vectors under the names `embeddings` / `vectors` and
the IDs under `product_ids` / `ids`. If `--inspect` shows other names, tell
Claude (or add them to `VECTOR_KEYS` / `ID_KEYS` in `vectordb/catalogue.py`).

## 2. Start Qdrant and load the vectors

Qdrant runs in Docker next to Postgres:

```powershell
cd ..\backend
docker compose up -d qdrant
cd ..\ml-service
python -m scripts.ingest_qdrant
```

- Uploads every valid chunk to the collection `mooddrobe_catalogue_v2`.
- Re-running skips chunks already loaded, so you can run it now with the
  chunks you have, and again when embedding finishes.
- Invalid or half-written chunks are skipped and listed, never deleted.
- Vectors are stored on disk with a small int8 copy in RAM (about 150 MB),
  which suits an 8 GB laptop.
- Dashboard to look at the data: http://localhost:6333/dashboard

No Docker? Use Qdrant's built-in local mode instead (slower, fine for tests):

```powershell
$env:QDRANT_PATH = "data/processed/qdrant_local"
python -m scripts.ingest_qdrant
```

Set the same `$env:QDRANT_PATH` before every later command in that window.

## 3. Evaluate

Needs the test split embedded (it is used for the queries).

```powershell
python -m scripts.evaluate_retrieval
```

Queries are 2,000 random test images (seed 42). The index searched is
train + val only. A result is relevant when its `category` matches the query.
It prints Precision@K, HitRate@K, Recall@K, MRR, a random-guess baseline,
Qdrant search latency, the weakest categories and the most common mix-ups,
and saves JSON + CSV reports to `data/processed/reports/`.

Useful options: `--num-queries 500`, `--ks 1 5 10`, `--label-field subcategory`.

## 4. Add search to the FastAPI app

Add these lines to `main.py`, after `app = FastAPI(...)`, passing the
functions `main.py` already uses to embed images and text:

```python
from vectordb.api import create_search_router

app.include_router(create_search_router(
    embed_image=embed_image_fn,  # takes a PIL image, returns the 512 numbers
    embed_text=embed_text_fn,    # takes a string, returns the 512 numbers
))
```

If your functions take different inputs (for example raw bytes), wrap them,
e.g. `embed_image=lambda img: my_embed(img)`. If you call
`create_search_router()` with no arguments it loads FashionCLIP itself.

Run the API (`uvicorn main:app --reload`) and try it at http://localhost:8000/docs:

| Route | What it does |
| --- | --- |
| `POST /search/image` | Upload an image, get the top `k` products (default 12). Optional `category` filter. |
| `POST /search/text` | `{"query": "beige linen trousers", "k": 12}` |
| `GET /catalogue/image/{product_id}` | Returns the product photo |

Each search response includes `timings_ms` (embedding and search time).

### Style recommendations (more than "same category")

| Route | What it does |
| --- | --- |
| `POST /recommend` | Form fields: `files` (1 image, or up to 8 for a moodboard), optional `steer` text ("more formal", "in black"), `liked_ids` / `disliked_ids` (comma-separated), `k`, `diversity` (0 to 0.9, default 0.3). |
| `POST /recommend/for-you` | `{"liked_ids": [...], "disliked_ids": [...], "k": 12}`: suggestions from a user's likes. |
| `GET /recommend/similar/{product_id}` | "More like this" and "complete the look" for a product the user clicked. |

A `/recommend` response has these sections:

- `your_style`: items that share the look across different garment types.
  Picked with MMR (match the look, but not near-copies of each other) and at
  most 3 per category. `diversity` controls the balance.
- `complete_the_look`: only for a single garment photo. Top -> bottoms,
  bottom -> tops, dress or full outfit -> outer layers, in the same style.
- `closest_matches`: the 6 nearest items ("find this exact piece").
- `detected`: what the photo seems to show (`garment_type`, `category`,
  `confidence`), guessed from its nearest catalogue items.
- `style_tags`: top 3 style words (e.g. "minimalist", "streetwear"), scored
  zero-shot by FashionCLIP. Approximate, meant for display.

For a moodboard, the images are averaged into one style vector, and each
image's own neighbours are added to the candidates so every look on the board
shows up. Liked items pull the style towards them; disliked items push away.

Garment types come from DeepFashion's `list_category_cloth.txt` (read from
`data/raw/deepfashion` if present, otherwise a built-in copy). They are stored
in Qdrant at ingestion, so **if you ingested before this change, re-run
`python -m scripts.ingest_qdrant --force` once.**

To measure what recommendations add over plain search:

```powershell
python -m scripts.evaluate_recommendations
```

It compares plain nearest neighbours with `your_style` at several diversity
settings: similarity to the query, variety (distinct categories, garment
types, intra-list diversity), same-category share, latency, and how often the
garment type is detected correctly. There is no "goes well together" ground
truth in DeepFashion, so outfit compatibility needs a small user study.

### Colour matching, attribute filters and explanations

`scripts/extract_colors.py` saves each product's dominant colours (the
`main.py` method, cropped to the garment box). `ingest_qdrant.py` stores them
as `palette`, `palette_weights` and `color_names`. When colours are given
(`match_colors=true` for the uploaded photos, or `colors=navy,#F5F5F5`), each
candidate's colour match (CIE Lab delta E, weighted by how much of the garment
each colour covers) is added to its relevance before MMR, scaled by
`color_weight` (0 to 1). `only_colors`, `tags` and `avoid_tags` are hard
filters in Qdrant. Every result has a `why` list (style similarity, matching
colours, requested and shared attributes, vibe). `GET /recommend/options`
lists the attributes, colour names and vibes for the app's filter controls.

## 5. Express

`backend` forwards these as `/api/recommendations/image`,
`/api/recommendations/text`, `/api/recommendations/catalogue-image/:id`,
`/api/recommendations/style` (multipart, forwarded to `/recommend`),
`/api/recommendations/for-you` and `/api/recommendations/similar/:id`.
Set `ML_SERVICE_URL` in `backend/.env` if FastAPI is not on
`http://localhost:8000`.

## Settings

| Variable | Default |
| --- | --- |
| `QDRANT_URL` | `http://localhost:6333` |
| `QDRANT_PATH` | not set (set it to use local mode) |
| `QDRANT_COLLECTION` | `mooddrobe_catalogue_v2` |
| `MOODDROBE_EMBEDDINGS_DIR` | `data/processed/catalogue_embeddings/full_catalogue_v2` |
| `MOODDROBE_PRODUCTS_CSV` | `data/catalogue/metadata/products.csv` |
| `MOODDROBE_RAW_DIR` | `data/raw/deepfashion` |
| `MOODDROBE_CHUNK_SIZE` | `5000` |
| `MOODDROBE_COLORS_DIR` | `data/processed/colors` |
