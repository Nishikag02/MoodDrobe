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
