# MoodDrobe: how to run everything (Windows PowerShell)

This goes from your saved embeddings to working recommendations. Nothing
here re-runs FashionCLIP over the catalogue or deletes embedding files.
More detail on each part: `RETRIEVAL.md`.

## How it works in one paragraph

FashionCLIP turns every image, and every piece of text, into 512 numbers
(a vector). Similar-looking things get similar vectors, and a phrase like
"old money" lands near clothes that look like that. All 289k catalogue
images were turned into vectors once (your `full_catalogue_v2` run). Qdrant
stores those vectors and finds the nearest ones fast. A recommendation is:
turn the user's input (photo, moodboard, vibe words, likes) into one "style
vector", find nearby catalogue items, then re-rank them so the results are
varied and include pieces that pair with what was uploaded. Two small models
trained on your saved vectors add the garment category and attributes
(floral, denim, sleeveless and so on).

## Fastest way: one script

From `ml-service`, this runs steps 0 to 6 below in order and stops at the first problem:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_and_run.ps1
```

Options: `-LocalQdrant` (no Docker), `-SkipEval`, `-NoServer`. When the
API is up, open a second window and run `python -m scripts.smoke_test_api`.
It sends a real test photo and two vibes, then prints what comes back.

The steps below are the same thing done by hand.

## New computer without embeddings or products.csv?

Download DeepFashion (Category and Attribute Prediction) into
`data\raw\deepfashion` so that images sit in `Img\img\...` and the `list_*.txt`
files are next to `Img`. Then:

```powershell
python -m scripts.build_products_csv       # makes products.csv (289,222 rows)
python -m scripts.embed_full_catalogue     # resumable; uses an NVIDIA GPU if present
```

Embedding speed measured on a 4-core cloud CPU: about 30 images per second,
so roughly 3 hours for all 289k. A GPU is much faster.

## 0. Open the project

```powershell
cd C:\Users\nishi\OneDrive\Desktop\MoodDrobe\MoodDrobe\ml-service
.\.venv\Scripts\Activate.ps1
pip install -r requirements-vectordb.txt
```

If `embed_catalogue.py` is still running, do steps 1 to 5 in a second
PowerShell window. They only read the chunk files. Re-run steps 4 and 5
once embedding has finished, to include the last chunks.

## 1. Check the embeddings

```powershell
python -m scripts.verify_embeddings --inspect
python -m scripts.verify_embeddings
```

The first command shows the array names inside a chunk file. The scripts
expect `embeddings` (or `vectors`) and `product_ids` (or `ids`). If yours are
different, add them to `VECTOR_KEYS` / `ID_KEYS` at the top of
`vectordb/catalogue.py`.

## 2. Start Qdrant

Start Docker Desktop first, then:

```powershell
cd ..\backend
docker compose up -d qdrant
cd ..\ml-service
```

Check it at http://localhost:6333/dashboard.

## 3. Train the category and attribute models (minutes, CPU)

For attributes, put DeepFashion's `list_attr_cloth.txt` and
`list_attr_img.txt` in `data\raw\deepfashion` (next to
`list_category_cloth.txt`). Without them, only the category model is trained.

```powershell
python -m scripts.train_heads
```

It prints accuracy on the val and test splits: category top-1, top-3 and
top-5; top/bottom/full-body accuracy; and attribute recall@3 and recall@5.
These are the standard DeepFashion metrics, ready for your report. The model
is saved to `data\processed\models\heads.npz`.

## 4. Load everything into Qdrant

```powershell
python -m scripts.ingest_qdrant --force
```

`--force` re-uploads everything so each product also gets its garment type
and predicted attribute tags. Without `--force`, it only adds new chunks.

## 5. Measure quality

```powershell
python -m scripts.evaluate_retrieval
python -m scripts.evaluate_recommendations
```

Reports are saved in `data\processed\reports`.

## 6. Start the API

```powershell
uvicorn recommend_server:app --port 8000
```

This runs your existing `main.py` routes plus the new ones. Open
http://localhost:8000/docs, choose a route, and press "Try it out".

`recommend_server.py` loads its own copy of FashionCLIP for the new routes.
To use one copy, add this to the end of `main.py`, using the names of your
own embedding functions:

```python
from vectordb.api import create_search_router
app.include_router(create_search_router(embed_image=your_image_fn, embed_text=your_text_fn))
```

Then run `uvicorn main:app --port 8000` instead.

### Try it from PowerShell

Use `curl.exe`, not `curl`. In PowerShell, `curl` is a different command.

```powershell
# One outfit photo: your style, complete the look, closest matches, vibes, attributes
curl.exe -F "files=@C:\Users\nishi\Pictures\outfit.jpg" http://localhost:8000/recommend

# Moodboard: several photos (clothes, places, rooms, art), plus a text steer
curl.exe -F "files=@pin1.jpg" -F "files=@pin2.jpg" -F "files=@beach.jpg" -F "steer=more casual" http://localhost:8000/recommend

# Vibe in words
Invoke-RestMethod -Method Post -Uri http://localhost:8000/recommend/vibe -ContentType "application/json" -Body '{"vibe": "old money", "k": 12}'

# Only results with an attribute (needs step 3 with attribute files)
Invoke-RestMethod -Method Post -Uri http://localhost:8000/recommend/vibe -ContentType "application/json" -Body '{"vibe": "summer picnic", "tags": ["floral"]}'

# "More like this" for a catalogue product
Invoke-RestMethod http://localhost:8000/recommend/similar/<product_id>
```

What comes back:

| Field | Meaning |
| --- | --- |
| `inputs` | Each photo read as `clothing` or `mood`, and for mood photos, the vibes it was read as |
| `your_style` | Varied items with the same look, across garment types |
| `complete_the_look` | Pieces that pair with a single clothing photo |
| `closest_matches` | Nearest items ("find this exact piece") |
| `detected` | Garment type and category of the photo |
| `vibes` | Top vibe words for the overall look |
| `attributes` | Predicted attributes (fabric, texture, shape, part, style) |

Mood photos (a beach, a cafe, a painting) don't look like clothes, so they
are first described with vibe words ("coastal", "earthy") and then matched to
clothes. If a photo is read the wrong way, send `mode=clothing` or
`mode=mood`. You can edit the vibe list in `vectordb/vibes.py`; no retraining
is needed.

## 7. Through Express (what the React app will call)

```powershell
cd ..\backend
docker compose up -d
pnpm install
pnpm dev
```

Express runs on port 3000 and forwards to the ML service on port 8000. To
use another address, set `ML_SERVICE_URL` in `backend\.env`.

| Express route | Goes to |
| --- | --- |
| `POST /api/recommendations/style` (multipart, same fields as `/recommend`) | `/recommend` |
| `POST /api/recommendations/vibe` | `/recommend/vibe` |
| `POST /api/recommendations/for-you` | `/recommend/for-you` |
| `GET /api/recommendations/similar/:id` | `/recommend/similar/{id}` |
| `POST /api/recommendations/image`, `/text` | plain search |
| `GET /api/recommendations/catalogue-image/:id` | product photo |

## Quick fixes

- `Vector search unavailable`: Qdrant isn't running. Re-do step 2.
- `Collection ... not found`: run step 4.
- Out of memory during training: `python -m scripts.train_heads --max-train 80000`.
- Everything is slow the first time: FashionCLIP loads on the first request
  (about 10 to 30 seconds). Later requests are fast.
