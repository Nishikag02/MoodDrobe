# MoodDrobe demo — how to run

Three PowerShell windows. Postgres and Express are **not** needed for the demo.

## 1. Qdrant (vector database)
Only if the ML setup uses Docker Qdrant (skip if it runs in local/embedded mode):

```powershell
docker start qdrant
```

## 2. ML service (FastAPI, port 8000)

```powershell
cd C:\Users\Singh\Desktop\MoodDrobe\ml-service
.\.venv\Scripts\Activate.ps1
uvicorn recommend_server:app --host 127.0.0.1 --port 8000
```

Wait for `Application startup complete`. Check http://127.0.0.1:8000/recommend/options opens in the browser.

## 3. Web app (Vite, port 5173)

```powershell
cd C:\Users\Singh\Desktop\MoodDrobe\frontend
pnpm install      # first time only
pnpm dev
```

Open **http://localhost:5173**. The dot in the top-right says "Model online" when the app can reach the ML service.
The app calls `/ml/...`, which Vite forwards to `http://127.0.0.1:8000` (set `ML_SERVICE_URL` to change it).

## Demo flow
1. Drop a café / beach / mountain photo into the box → **Find my style**.
2. Show "How MoodDrobe read your vibe": mood vs clothing photo, palette, aesthetic bars.
3. Scroll: **Outfits for this vibe** → **Your style** (tabs: Tops / Bottoms / One-pieces) → **Closest matches**.
4. **Refine**: click a colour chip (only that colour), click a detail tag (require → exclude → clear), slide Closest ↔ More variety.
5. Click any item → drawer with **Complete the look** and **More like this**.
6. Type a vibe ("old money") or click a preset chip.
7. Upload an outfit photo → shows **Complete the look** for the detected garment.
8. Drop several images at once → moodboard.

## Pages
- `/` — MoodDrobe studio (new)
- `/login`, `/signup`, `/dashboard` — existing Better Auth pages (need Express + Postgres)
- `/welcome` — the old placeholder home page
