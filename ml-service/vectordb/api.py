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

from . import catalogue, colors, config, heads, recommend, store, vibes

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
PUBLIC_FIELDS = ("product_id", "category", "category_name", "garment_type", "subcategory", "color",
                 "pattern", "dataset_split", "tags", "color_names", "palette")
NOT_PRODUCT_LISTS = ("vibes", "attributes", "query_colors", "photo_colors")
MAX_MOODBOARD_IMAGES = 8
CLOTHING_MATCH_SCORE = 0.8  # cosine similarity to the nearest catalogue item


class Filters(BaseModel):
    """Attribute and colour options shared by the JSON routes."""
    tags: list[str] = Field(default_factory=list, max_length=5,
                            description='attributes every result must have, e.g. ["floral", "sleeveless"]')
    avoid_tags: list[str] = Field(default_factory=list, max_length=10, description='e.g. ["denim"]')
    colors: list[str] = Field(default_factory=list, max_length=5,
                              description='colours to match: names ("navy") or hex ("#1F2A44")')
    color_weight: float = Field(default=0.5, ge=0.0, le=1.0, description="how strongly to match colours")
    only_colors: list[str] = Field(default_factory=list, max_length=5,
                                   description='every result must contain one of these colour names')


class ForYouRequest(Filters):
    liked_ids: list[str] = Field(min_length=1, max_length=200)
    disliked_ids: list[str] = Field(default_factory=list, max_length=200)
    steer: str | None = Field(default=None, max_length=200)
    k: int = Field(default=12, ge=1, le=50)
    diversity: float = Field(default=0.3, ge=0.0, le=0.9)


class VibeRequest(Filters):
    vibe: str = Field(min_length=1, max_length=200, description='e.g. "old money", "rainy day in Paris"')
    liked_ids: list[str] = Field(default_factory=list, max_length=200)
    k: int = Field(default=12, ge=1, le=50)
    diversity: float = Field(default=0.35, ge=0.0, le=0.9)


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
        for extra in ("reason", "why", "match", "color_match"):
            if extra in r:
                item[extra] = r[extra]
        out.append(item)
    return out


def _public_sections(rec: dict) -> dict:
    return {key: (_public(val) if isinstance(val, list) and key not in NOT_PRODUCT_LISTS else val)
            for key, val in rec.items()}


def _color_names(raw: list[str]) -> list[str]:
    out = [c.strip().lower() for c in raw if c.strip()]
    unknown = [c for c in out if c not in colors.COLOR_NAMES]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown colour name(s) {unknown}. "
                                                    f"Use one of: {', '.join(colors.COLOR_NAMES)}")
    return out


def _filter_kwargs(tags: list[str], avoid_tags: list[str], color_list: list[str], color_weight: float,
                   only_colors: list[str], fallback_colors: list[tuple[str, float]] | None = None) -> dict:
    """Turn the request's attribute/colour options into recommend() arguments."""
    try:
        color_query = colors.parse(color_list) if color_list else (fallback_colors or [])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"must_have_tags": tags or None, "avoid_tags": avoid_tags or None,
            "color_query": color_query or None, "color_weight": color_weight,
            "only_colors": _color_names(only_colors) or None}


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

    def _run_recommend(query: recommend.StyleQuery, k: int, diversity: float, options: dict | None = None):
        try:
            return recommend.recommend(query, k=k, diversity=diversity, embed_text=embed_text, **(options or {}))
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
        tags: str | None = Form(None, description='comma-separated attributes every result must have, e.g. "floral"'),
        avoid_tags: str | None = Form(None, description='comma-separated attributes to leave out, e.g. "denim"'),
        mode: str = Form("auto", pattern="^(auto|clothing|mood)$",
                         description="auto = detect per image; clothing / mood = treat every image that way"),
        match_colors: bool | None = Form(None, description="re-rank towards the colours of the uploaded photos; "
                                                           "default: on when a mood photo is uploaded"),
        colors_: str | None = Form(None, alias="colors",
                                   description='colours to match instead, e.g. "navy, white" or "#1F2A44"'),
        color_weight: float = Form(0.5, ge=0.0, le=1.0, description="how strongly to match colours"),
        only_colors: str | None = Form(None, description='every result must contain one of these, e.g. "navy, white"'),
    ):
        """Recommendations from clothing photos, mood photos (scenery, rooms, art) or a mix (moodboard)."""
        if len(files) > MAX_MOODBOARD_IMAGES:
            raise HTTPException(status_code=400, detail=f"At most {MAX_MOODBOARD_IMAGES} images.")
        images = [await _read_image(f) for f in files]
        t = time.perf_counter()
        raw_vecs = [await run_in_threadpool(embed_image, im) for im in images]
        steer_vec = await run_in_threadpool(embed_text, steer.strip()) if steer and steer.strip() else None

        # Mood photos are translated into vibe words first; clothing photos are used directly.
        image_vecs, inputs = [], []
        for f, v in zip(files, raw_vecs):
            clothing, p = await run_in_threadpool(vibes.is_clothing_photo, v, embed_text)
            if mode == "auto" and not clothing:
                # Second opinion: a photo that closely matches a catalogue item is clothing.
                nearest = await run_in_threadpool(store.search, v, 1)
                clothing = bool(nearest) and nearest[0]["score"] >= CLOTHING_MATCH_SCORE
            if mode != "auto":
                clothing = mode == "clothing"
            if clothing:
                image_vecs.append(v)
                inputs.append({"file": f.filename, "kind": "clothing", "clothing_probability": p})
            else:
                # Mood photo: recognise the setting (cafe, beach...), then search for what to wear there.
                mood_vec, reading = await run_in_threadpool(vibes.interpret, v, embed_text)
                image_vecs.append(mood_vec)
                inputs.append({"file": f.filename, "kind": "mood", "clothing_probability": p, **reading})
        # Clothing photos: colours of the garment (centre crop). Mood photos: colours of the whole scene.
        palettes = [colors.palette(im) if item["kind"] == "clothing" else colors.palette(im, box=(0, 0, *im.size))
                    for im, item in zip(images, inputs)]
        for item, pal in zip(inputs, palettes):
            item["colors"] = [{"hex": h, "weight": w, "name": colors.color_name(h)} for h, w in pal]
        embed_ms = (time.perf_counter() - t) * 1000

        liked, disliked = _split_ids(liked_ids), _split_ids(disliked_ids)
        stored = await run_in_threadpool(store.get_vectors, liked + disliked) if liked or disliked else {}
        single_garment = len(raw_vecs) == 1 and inputs[0]["kind"] == "clothing"
        query = recommend.StyleQuery(
            image_vectors=image_vecs, steer_vector=steer_vec,
            pair_vector=raw_vecs[0] if single_garment else None,
            liked_vectors=[stored[i] for i in liked if i in stored],
            disliked_vectors=[stored[i] for i in disliked if i in stored],
            exclude_ids=liked + disliked,
        )
        t = time.perf_counter()
        use_colors = match_colors if match_colors is not None else any(i["kind"] == "mood" for i in inputs)
        options = _filter_kwargs(_split_ids(tags), _split_ids(avoid_tags), _split_ids(colors_), color_weight,
                                 _split_ids(only_colors),
                                 fallback_colors=colors.merge(palettes) if use_colors else None)
        rec = await run_in_threadpool(_run_recommend, query, k, diversity, options)
        return {"inputs": inputs, **_public_sections(rec),
                "timings_ms": {"embed": round(embed_ms, 1), "recommend": round((time.perf_counter() - t) * 1000, 1)}}

    @router.post("/recommend/vibe")
    async def recommend_from_vibe(body: VibeRequest):
        """Outfits for a vibe in words: "old money", "90s grunge", "rainy day in Paris"."""
        text_vec = await run_in_threadpool(embed_text, vibes.text_query(body.vibe))
        stored = await run_in_threadpool(store.get_vectors, body.liked_ids) if body.liked_ids else {}
        query = recommend.StyleQuery(text_vectors=[text_vec],
                                     liked_vectors=[stored[i] for i in body.liked_ids if i in stored],
                                     exclude_ids=body.liked_ids)
        options = _filter_kwargs(body.tags, body.avoid_tags, body.colors, body.color_weight, body.only_colors)
        rec = await run_in_threadpool(_run_recommend, query, body.k, body.diversity, options)
        return _public_sections(rec)

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
        options = _filter_kwargs(body.tags, body.avoid_tags, body.colors, body.color_weight, body.only_colors)
        rec = await run_in_threadpool(_run_recommend, query, body.k, body.diversity, options)
        rec.pop("closest_matches", None)
        return _public_sections(rec)

    @router.get("/recommend/similar/{product_id}")
    async def recommend_similar(product_id: str, k: int = Query(12, ge=1, le=50),
                                diversity: float = Query(0.3, ge=0.0, le=0.9),
                                match_colors: bool = Query(False, description="prefer this product's colours"),
                                color_weight: float = Query(0.5, ge=0.0, le=1.0),
                                tags: str | None = Query(None), avoid_tags: str | None = Query(None)):
        """"More like this" and "complete the look" for a catalogue product the user clicked."""
        stored = await run_in_threadpool(store.get_vectors, [product_id])
        if product_id not in stored:
            raise HTTPException(status_code=404, detail="Unknown product.")
        own = None
        if match_colors:
            payload = await run_in_threadpool(store.get_product, product_id) or {}
            own = list(zip(payload.get("palette") or [], payload.get("palette_weights") or []))
        query = recommend.StyleQuery(image_vectors=[stored[product_id]], pair_vector=stored[product_id],
                                     exclude_ids=[product_id])
        options = _filter_kwargs(_split_ids(tags), _split_ids(avoid_tags), [], color_weight, [], fallback_colors=own)
        rec = await run_in_threadpool(_run_recommend, query, k, diversity, options)
        return _public_sections(rec)

    @router.get("/recommend/options")
    def recommend_options():
        """Values the app can offer as filters: attributes, colour names and vibes."""
        model = heads.load()
        attrs = []
        if model is not None and model.has_attrs:
            attrs = [{"name": n, "type": t} for n, t in zip(model.attr_names, model.attr_types)]
        return {"attributes": attrs,
                "colors": [{"name": n, "hex": h} for n, h in colors.COLOR_NAMES.items()],
                "vibes": [name for name, _ in vibes.VIBES]}

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
