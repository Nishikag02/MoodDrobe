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
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from . import catalogue, config, recommend, store

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
PUBLIC_FIELDS = ("product_id", "category", "category_name", "garment_type", "subcategory", "color",
                 "pattern", "dataset_split")
MAX_MOODBOARD_IMAGES = 8


class ForYouRequest(BaseModel):
    liked_ids: list[str] = Field(min_length=1, max_length=200)
    disliked_ids: list[str] = Field(default_factory=list, max_length=200)
    steer: str | None = Field(default=None, max_length=200)
    k: int = Field(default=12, ge=1, le=50)
    diversity: float = Field(default=0.3, ge=0.0, le=0.9)


class TextSearch(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    k: int = Field(default=12, ge=1, le=100)
    category: str | None = None


def _public(results: list[dict]) -> list[dict]:
    out = []
    for r in results:
        item = {"product_id": r["product_id"], "score": round(r["score"], 4),
                **{k: r.get(k) for k in PUBLIC_FIELDS if k != "product_id"},
                "image_url": f"/catalogue/image/{r['product_id']}"}
        for extra in ("reason", "match"):
            if extra in r:
                item[extra] = r[extra]
        out.append(item)
    return out


def _public_sections(rec: dict) -> dict:
    return {key: (_public(val) if isinstance(val, list) and key != "style_tags" else val)
            for key, val in rec.items()}


async def _read_image(file: UploadFile) -> Image.Image:
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"{file.filename} is larger than 10 MB.")
    try:
        image = Image.open(BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail=f"{file.filename} is not a valid image.")
    return image.convert("RGB")


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

    def _run_recommend(query: recommend.StyleQuery, k: int, diversity: float):
        try:
            return recommend.recommend(query, k=k, diversity=diversity, embed_text=embed_text)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except HTTPException:
            raise
        except Exception as e:  # Qdrant down or collection missing
            raise HTTPException(status_code=503, detail=f"Vector search unavailable: {e}") from e

    def _split_ids(raw: str | None) -> list[str]:
        return [i.strip() for i in (raw or "").split(",") if i.strip()]

    @router.post("/recommend")
    async def recommend_from_images(
        files: list[UploadFile] = File(..., description="1 image, or up to 8 for a moodboard"),
        steer: str | None = Form(None, description='optional text, e.g. "more formal" or "in black"'),
        liked_ids: str | None = Form(None, description="comma-separated product IDs the user liked"),
        disliked_ids: str | None = Form(None, description="comma-separated product IDs the user disliked"),
        k: int = Form(12, ge=1, le=50),
        diversity: float = Form(0.3, ge=0.0, le=0.9, description="0 = closest only, higher = more variety"),
    ):
        if len(files) > MAX_MOODBOARD_IMAGES:
            raise HTTPException(status_code=400, detail=f"At most {MAX_MOODBOARD_IMAGES} images.")
        images = [await _read_image(f) for f in files]
        t = time.perf_counter()
        image_vecs = [await run_in_threadpool(embed_image, im) for im in images]
        steer_vec = await run_in_threadpool(embed_text, steer.strip()) if steer and steer.strip() else None
        embed_ms = (time.perf_counter() - t) * 1000
        liked, disliked = _split_ids(liked_ids), _split_ids(disliked_ids)
        stored = await run_in_threadpool(store.get_vectors, liked + disliked) if liked or disliked else {}
        query = recommend.StyleQuery(
            image_vectors=image_vecs, steer_vector=steer_vec,
            liked_vectors=[stored[i] for i in liked if i in stored],
            disliked_vectors=[stored[i] for i in disliked if i in stored],
            exclude_ids=liked + disliked,
        )
        t = time.perf_counter()
        rec = await run_in_threadpool(_run_recommend, query, k, diversity)
        return {**_public_sections(rec),
                "timings_ms": {"embed": round(embed_ms, 1), "recommend": round((time.perf_counter() - t) * 1000, 1)}}

    @router.post("/recommend/for-you")
    async def recommend_for_user(body: ForYouRequest):
        """Suggestions from a user's liked (and disliked) items. Express keeps the likes."""
        stored = await run_in_threadpool(store.get_vectors, body.liked_ids + body.disliked_ids)
        liked = [stored[i] for i in body.liked_ids if i in stored]
        if not liked:
            raise HTTPException(status_code=404, detail="None of the liked products are in the index.")
        steer_vec = await run_in_threadpool(embed_text, body.steer) if body.steer else None
        query = recommend.StyleQuery(
            liked_vectors=liked, steer_vector=steer_vec,
            disliked_vectors=[stored[i] for i in body.disliked_ids if i in stored],
            exclude_ids=body.liked_ids + body.disliked_ids,
        )
        rec = await run_in_threadpool(_run_recommend, query, body.k, body.diversity)
        rec.pop("closest_matches", None)
        return _public_sections(rec)

    @router.get("/recommend/similar/{product_id}")
    async def recommend_similar(product_id: str, k: int = Query(12, ge=1, le=50),
                                diversity: float = Query(0.3, ge=0.0, le=0.9)):
        """"More like this" and "complete the look" for a catalogue product the user clicked."""
        stored = await run_in_threadpool(store.get_vectors, [product_id])
        if product_id not in stored:
            raise HTTPException(status_code=404, detail="Unknown product.")
        query = recommend.StyleQuery(image_vectors=[stored[product_id]], exclude_ids=[product_id])
        rec = await run_in_threadpool(_run_recommend, query, k, diversity)
        return _public_sections(rec)

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
