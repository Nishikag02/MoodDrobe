import express, { Router } from "express";
import type { Request, Response } from "express";

// FastAPI ML service (ml-service/). Express stays the only thing the browser talks to.
const ML_SERVICE_URL = process.env.ML_SERVICE_URL ?? "http://localhost:8000";
const MAX_IMAGE_BYTES = 10 * 1024 * 1024;

export const recommendationsRouter: Router = Router();

function clampK(value: unknown): number {
  const k = Number(value ?? 12);
  return Number.isInteger(k) && k >= 1 && k <= 50 ? k : 12;
}

type SearchResult = { product_id: string; image_url?: string; [key: string]: unknown };

async function forwardJson(res: Response, upstream: globalThis.Response) {
  const body = (await upstream.json().catch(() => ({ detail: "Invalid response from ML service" }))) as { results?: unknown };
  // Point image links at this server, so the browser never calls the ML service directly.
  if (Array.isArray(body.results)) {
    for (const r of body.results as SearchResult[]) {
      r.image_url = `/api/recommendations/catalogue-image/${encodeURIComponent(r.product_id)}`;
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
