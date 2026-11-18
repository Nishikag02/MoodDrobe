import express, { Router } from "express";
import type { Request, Response } from "express";

// FastAPI ML service (ml-service/). Express stays the only thing the browser talks to.
const ML_SERVICE_URL = process.env.ML_SERVICE_URL ?? "http://localhost:8000";
const MAX_IMAGE_BYTES = 10 * 1024 * 1024;

export const recommendationsRouter: Router = Router();

// Attribute and colour options shared by the JSON routes (see ml-service RUN_GUIDE.md).
function filterOptions(body: Record<string, unknown> | undefined) {
  const list = (v: unknown, max: number) => (Array.isArray(v) ? v.map(String).slice(0, max) : []);
  const weight = Number(body?.color_weight ?? 0.5);
  return {
    tags: list(body?.tags, 5),
    avoid_tags: list(body?.avoid_tags, 10),
    colors: list(body?.colors, 5),
    only_colors: list(body?.only_colors, 5),
    color_weight: Number.isFinite(weight) ? Math.min(Math.max(weight, 0), 1) : 0.5,
  };
}

function clampK(value: unknown): number {
  const k = Number(value ?? 12);
  return Number.isInteger(k) && k >= 1 && k <= 50 ? k : 12;
}

type SearchResult = { product_id: string; image_url?: string; [key: string]: unknown };

async function forwardJson(res: Response, upstream: globalThis.Response) {
  const body = (await upstream.json().catch(() => ({ detail: "Invalid response from ML service" }))) as Record<string, unknown>;
  // Point image links at this server, so the browser never calls the ML service directly.
  // Covers plain search ("results") and every recommendation section.
  for (const value of Object.values(body as Record<string, unknown>)) {
    if (!Array.isArray(value)) continue;
    for (const r of value as SearchResult[]) {
      if (r && typeof r === "object" && typeof r.product_id === "string") {
        r.image_url = `/api/recommendations/catalogue-image/${encodeURIComponent(r.product_id)}`;
      }
    }
  }
  res.status(upstream.status).json(body);
}

// POST /api/recommendations/image?k=12&category=Dress
// Body: the raw image bytes, with Content-Type image/jpeg, image/png or image/webp.
recommendationsRouter.post(
  "/image",
  express.raw({ type: "image/*", limit: MAX_IMAGE_BYTES }),
  async (req: Request, res: Response) => {
    if (!Buffer.isBuffer(req.body) || req.body.length === 0) {
      res.status(400).json({ detail: "Send the image as the request body with an image/* Content-Type." });
      return;
    }
    const params = new URLSearchParams({ k: String(clampK(req.query.k)) });
    if (typeof req.query.category === "string" && req.query.category) params.set("category", req.query.category);

    const form = new FormData();
    const type = req.get("content-type") ?? "image/jpeg";
    form.append("file", new Blob([new Uint8Array(req.body)], { type }), "query-image");

    try {
      const upstream = await fetch(`${ML_SERVICE_URL}/search/image?${params}`, { method: "POST", body: form });
      await forwardJson(res, upstream);
    } catch {
      res.status(502).json({ detail: "ML service is not reachable." });
    }
  },
);

// POST /api/recommendations/text  { "query": "beige linen trousers", "k": 12 }
recommendationsRouter.post("/text", express.json(), async (req: Request, res: Response) => {
  const query = typeof req.body?.query === "string" ? req.body.query.trim() : "";
  if (!query) {
    res.status(400).json({ detail: "query is required" });
    return;
  }
  try {
    const upstream = await fetch(`${ML_SERVICE_URL}/search/text`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, k: clampK(req.body?.k), category: req.body?.category ?? null }),
    });
    await forwardJson(res, upstream);
  } catch {
    res.status(502).json({ detail: "ML service is not reachable." });
  }
});

// POST /api/recommendations/style
// Style suggestions, complete-the-look and moodboards. Send multipart/form-data
// exactly as FastAPI's /recommend expects: one to eight "files", optional
// "steer" text, "liked_ids", "disliked_ids", "k", "diversity", "tags",
// "avoid_tags", "match_colors", "colors", "color_weight", "only_colors". Forwarded as-is.
recommendationsRouter.post(
  "/style",
  express.raw({ type: "multipart/form-data", limit: 8 * MAX_IMAGE_BYTES }),
  async (req: Request, res: Response) => {
    const type = req.get("content-type") ?? "";
    if (!type.startsWith("multipart/form-data") || !Buffer.isBuffer(req.body)) {
      res.status(400).json({ detail: "Send multipart/form-data with one or more 'files'." });
      return;
    }
    try {
      const upstream = await fetch(`${ML_SERVICE_URL}/recommend`, {
        method: "POST",
        headers: { "Content-Type": type },
        body: new Uint8Array(req.body),
      });
      await forwardJson(res, upstream);
    } catch {
      res.status(502).json({ detail: "ML service is not reachable." });
    }
  },
);

// POST /api/recommendations/for-you  { "liked_ids": [...], "disliked_ids": [...], "k": 12 }
// Later this should read the signed-in user's likes from Postgres instead of the body.
recommendationsRouter.post("/for-you", express.json(), async (req: Request, res: Response) => {
  const liked = Array.isArray(req.body?.liked_ids) ? req.body.liked_ids.map(String) : [];
  if (liked.length === 0) {
    res.status(400).json({ detail: "liked_ids is required" });
    return;
  }
  const disliked = Array.isArray(req.body?.disliked_ids) ? req.body.disliked_ids.map(String) : [];
  try {
    const upstream = await fetch(`${ML_SERVICE_URL}/recommend/for-you`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ liked_ids: liked, disliked_ids: disliked, k: clampK(req.body?.k), ...filterOptions(req.body) }),
    });
    await forwardJson(res, upstream);
  } catch {
    res.status(502).json({ detail: "ML service is not reachable." });
  }
});

// POST /api/recommendations/vibe
// { "vibe": "old money", "k": 12, "tags": ["knit"], "avoid_tags": ["denim"],
//   "colors": ["navy", "#F5F5F5"], "color_weight": 0.5, "only_colors": ["beige"] }
recommendationsRouter.post("/vibe", express.json(), async (req: Request, res: Response) => {
  const vibe = typeof req.body?.vibe === "string" ? req.body.vibe.trim() : "";
  if (!vibe) {
    res.status(400).json({ detail: "vibe is required, e.g. \"old money\"" });
    return;
  }
  const likedIds = Array.isArray(req.body?.liked_ids) ? req.body.liked_ids.map(String) : [];
  try {
    const upstream = await fetch(`${ML_SERVICE_URL}/recommend/vibe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vibe, liked_ids: likedIds, k: clampK(req.body?.k), ...filterOptions(req.body) }),
    });
    await forwardJson(res, upstream);
  } catch {
    res.status(502).json({ detail: "ML service is not reachable." });
  }
});

// GET /api/recommendations/options -> attributes, colour names and vibes the app can offer as filters
recommendationsRouter.get("/options", async (_req: Request, res: Response) => {
  try {
    const upstream = await fetch(`${ML_SERVICE_URL}/recommend/options`);
    await forwardJson(res, upstream);
  } catch {
    res.status(502).json({ detail: "ML service is not reachable." });
  }
});

// GET /api/recommendations/similar/:productId?match_colors=true&tags=floral
// -> "more like this" + "complete the look"
recommendationsRouter.get("/similar/:productId", async (req: Request, res: Response) => {
  const productId = String(req.params.productId);
  if (!/^[\w.-]+$/.test(productId)) {
    res.status(400).json({ detail: "Bad product id" });
    return;
  }
  try {
    const params = new URLSearchParams({ k: String(clampK(req.query.k)) });
    for (const key of ["match_colors", "color_weight", "tags", "avoid_tags"]) {
      if (typeof req.query[key] === "string") params.set(key, req.query[key] as string);
    }
    const upstream = await fetch(
      `${ML_SERVICE_URL}/recommend/similar/${encodeURIComponent(productId)}?${params}`,
    );
    await forwardJson(res, upstream);
  } catch {
    res.status(502).json({ detail: "ML service is not reachable." });
  }
});

// GET /api/recommendations/catalogue-image/:productId  -> the product photo
recommendationsRouter.get("/catalogue-image/:productId", async (req: Request, res: Response) => {
  const productId = String(req.params.productId);
  if (!/^[\w.-]+$/.test(productId)) {
    res.status(400).json({ detail: "Bad product id" });
    return;
  }
  try {
    const upstream = await fetch(`${ML_SERVICE_URL}/catalogue/image/${encodeURIComponent(productId)}`);
    if (!upstream.ok) {
      res.status(upstream.status).end();
      return;
    }
    res.set("Content-Type", upstream.headers.get("content-type") ?? "image/jpeg");
    res.set("Cache-Control", "public, max-age=86400");
    res.send(Buffer.from(await upstream.arrayBuffer()));
  } catch {
    res.status(502).json({ detail: "ML service is not reachable." });
  }
});
