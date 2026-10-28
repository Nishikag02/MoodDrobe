"""FastAPI routes for catalogue search. Add them to main.py with:

    from vectordb.api import create_search_router
    app.include_router(create_search_router(embed_image=..., embed_text=...))

embed_image takes a PIL image and embed_text takes a string; both return a
512-number vector. Pass the functions main.py already uses for /embed/image
and /embed/text. If you pass nothing, a built-in FashionCLIP loader is used.
"""

from __future__ import annotations

import time
from io import BytesIO
from pathlib import Path
from typing import Callable

import numpy as np
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from . import catalogue, config, store

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
PUBLIC_FIELDS = ("product_id", "category", "subcategory", "color", "pattern", "dataset_split")


class TextSearch(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    k: int = Field(default=12, ge=1, le=100)
    category: str | None = None


def _public(results: list[dict]) -> list[dict]:
    return [
        {"product_id": r["product_id"], "score": round(r["score"], 4),
         **{k: r.get(k) for k in PUBLIC_FIELDS if k != "product_id"},
         "image_url": f"/catalogue/image/{r['product_id']}"}
        for r in results
    ]


def create_search_router(
    embed_image: Callable[[Image.Image], np.ndarray] | None = None,
    embed_text: Callable[[str], np.ndarray] | None = None,
) -> APIRouter:
    if embed_image is None or embed_text is None:
        from . import embedder
        embed_image = embed_image or embedder.embed_image
        embed_text = embed_text or embedder.embed_text

    router = APIRouter(tags=["search"])

    def _search(vector, k: int, category: str | None) -> tuple[list[dict], float]:
        t = time.perf_counter()
        try:
            res = store.search(vector, k=k, query_filter=store.build_filter(category=category))
        except Exception as e:  # Qdrant down or collection missing
            raise HTTPException(status_code=503, detail=f"Vector search unavailable: {e}") from e
        return res, (time.perf_counter() - t) * 1000

    @router.post("/search/image")
    async def search_by_image(
        file: UploadFile = File(...),
        k: int = Query(12, ge=1, le=100),
        category: str | None = Query(None, description="only return this DeepFashion category"),
    ):
        data = await file.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Image is larger than 10 MB.")
        try:
            image = Image.open(BytesIO(data))
            image.load()
        except (UnidentifiedImageError, OSError):
            raise HTTPException(status_code=400, detail="The uploaded file is not a valid image.")
        t = time.perf_counter()
        vector = await run_in_threadpool(embed_image, image.convert("RGB"))
        embed_ms = (time.perf_counter() - t) * 1000
        results, search_ms = await run_in_threadpool(_search, vector, k, category)
        return {"results": _public(results),
                "timings_ms": {"embed": round(embed_ms, 1), "search": round(search_ms, 1)}}

    @router.post("/search/text")
    async def search_by_text(body: TextSearch):
        t = time.perf_counter()
        vector = await run_in_threadpool(embed_text, body.query)
        embed_ms = (time.perf_counter() - t) * 1000
        results, search_ms = await run_in_threadpool(_search, vector, body.k, body.category)
        return {"results": _public(results),
                "timings_ms": {"embed": round(embed_ms, 1), "search": round(search_ms, 1)}}

    @router.get("/catalogue/image/{product_id}")
    def catalogue_image(product_id: str):
        payload = store.get_product(product_id)
        if not payload or not payload.get("image_path"):
            raise HTTPException(status_code=404, detail="Unknown product.")
        path = catalogue.resolve_image_path(payload["image_path"])
        root = config.RAW_DATA_DIR.resolve()
        if path is None or root not in Path(path).resolve().parents:
            raise HTTPException(status_code=404, detail="Image file not found.")
        return FileResponse(path)

    return router
