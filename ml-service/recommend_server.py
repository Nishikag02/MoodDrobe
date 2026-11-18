"""One-command server: your existing ML API plus search and recommendations.

    uvicorn recommend_server:app --port 8000

It loads main.py (so /analyze-image, /embed/image and /embed/text keep
working) and adds /search, /recommend and /catalogue routes. Those routes use
the built-in FashionCLIP loader in vectordb/embedder.py. To reuse main.py's
own embedding functions instead (one model in memory, not two), see
RUN_GUIDE.md, step 6.
"""

from fastapi import FastAPI

from vectordb.api import create_search_router

try:
    from main import app  # the existing MoodDrobe ML service
except ImportError:
    app = FastAPI(title="MoodDrobe ML Service")

app.include_router(create_search_router())

# Let a local web app (Vite dev server, any localhost port) call this API directly.
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

if not any(getattr(m, "cls", None) is CORSMiddleware for m in app.user_middleware):
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_methods=["*"],
        allow_headers=["*"],
    )
