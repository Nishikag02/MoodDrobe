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
(floral, denim, sleeveless and so on). Each product's dominant colours are
saved too, so results can be re-ranked to "match these colours", and every
result comes with a short "why this was suggested" list.

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

## 3b. Extract the catalogue colours (CPU, about 20 to 40 minutes)

Needs the DeepFashion photos in `data\raw\deepfashion\Img\img` and, for
better crops, `list_bbox.txt` next to the other `list_*.txt` files.

```powershell
python -m scripts.extract_colors
```

It saves a 5-colour palette per product in `data\processed\colors`. You can
stop it with Ctrl+C and run it again; finished parts are skipped. Quick test
first: `python -m scripts.extract_colors --limit 2000` (then delete the
`data\processed\colors` folder before the full run, so the test part is redone).
This is the same dominant-colour method as `main.py`, with the background
cropped away and the share of each colour kept.

## 4. Load everything into Qdrant

```powershell
python -m scripts.ingest_qdrant --force
```

`--force` re-uploads everything so each product also gets its garment type,
predicted attribute tags and colours. Without `--force`, it only adds new
chunks. Run it with `--force` again whenever you re-train the models or
re-extract colours.

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

# Match the colours of the uploaded photo
curl.exe -F "files=@outfit.jpg" -F "match_colors=true" http://localhost:8000/recommend

# Match colours you choose (names or hex codes), and leave out denim
curl.exe -F "files=@outfit.jpg" -F "colors=navy, #F5F5F5" -F "avoid_tags=denim" http://localhost:8000/recommend

# Only floral, sleeveless pieces that contain beige
Invoke-RestMethod -Method Post -Uri http://localhost:8000/recommend/vibe -ContentType "application/json" -Body '{"vibe": "summer picnic", "tags": ["floral", "sleeveless"], "only_colors": ["beige"]}'

# "More like this" in the same colours
Invoke-RestMethod "http://localhost:8000/recommend/similar/<product_id>?match_colors=true"

# Everything the app can offer as filters (attributes, colour names, vibes)
Invoke-RestMethod http://localhost:8000/recommend/options
```

Colour and attribute options (work on `/recommend`, `/recommend/vibe` and
`/recommend/for-you`):

| Option | What it does |
| --- | --- |
| `match_colors=true` | Re-rank towards the colours of the uploaded photos (`/recommend` and `/recommend/similar`) |
| `colors` | Colours to match instead: names (`navy`, `beige`) or hex (`#1F2A44`) |
| `color_weight` | 0 to 1, default 0.5. How strongly colour counts against style |
| `only_colors` | Hard filter: each result must contain one of these colour names |
| `tags` | Hard filter: each result must have all these attributes (`floral`, `denim`) |
| `avoid_tags` | Hard filter: leave out results with any of these attributes |

Colour matching only re-orders; style still counts. A higher `color_weight`
lets colour win more often.

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
| `query_colors` | The colours being matched (only when colour matching is on) |

Each `inputs` entry also lists the photo's own `colors`, so the app can show
swatches with a "match these colours" button. Each product in a section has:

| Field | Meaning |
| --- | --- |
| `why` | Plain reasons, e.g. "Style similarity 0.82", "Matches your colours: navy, white", "Has what you asked for: floral", "Same details as your inspiration: chiffon", "Fits the old money vibe" |
| `match` | Style similarity to your input (0 to 1) |
| `color_match` | Colour match to the chosen colours (0 to 1), when colour matching is on |
| `tags`, `color_names`, `palette` | The product's predicted attributes and colours |

Mood photos (a beach, a cafe, a painting) don't look like clothes, so they
are first recognised as a setting (16 settings, for example "cozy cafe" or
"beach") and each setting has a "what to wear there" description ("cozy knit
sweater and cardigan in warm earthy brown, beige and cream"). The search mixes
that description (50%), the photo's top vibe words (30%) and the photo itself
(20%), and by default also matches the scene's colours. Each mood photo in
`inputs` shows `scene`, `scenes`, `fashion_reading` and `read_as`. Edit the
settings in `SCENES` in `vectordb/vibes.py`; no retraining is needed. If a photo is read the wrong way, send `mode=clothing` or
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
| `GET /api/recommendations/options` | `/recommend/options` |
| `POST /api/recommendations/image`, `/text` | plain search |
| `GET /api/recommendations/catalogue-image/:id` | product photo |

## Quick fixes

- `Vector search unavailable`: Qdrant isn't running. Re-do step 2.
- `Collection ... not found`: run step 4.
- Out of memory during training: `python -m scripts.train_heads --max-train 80000`.
- `color_match` is always 0, or `only_colors` returns nothing: colours are not
  in Qdrant yet. Run step 3b, then step 4 with `--force`.
- `tags` filters return nothing: run step 3 with the attribute files, then step 4 with `--force`.
- Everything is slow the first time: FashionCLIP loads on the first request
  (about 10 to 30 seconds). Later requests are fast.

## Outfit compatibility for complete-the-look (optional)

A model trained on Polyvore Outfits can rank complete-the-look suggestions by
"goes with your piece" instead of "looks like it". Setup and results:
`COMPATIBILITY.md`. Short version: request dataset access once, run
`hf auth login`, then `powershell -ExecutionPolicy Bypass -File .\run_compat.ps1`.
