import { Router } from "express";
import type { NextFunction, Request, Response } from "express";
import { fromNodeHeaders } from "better-auth/node";
import { and, desc, eq } from "drizzle-orm";
import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";
import { auth } from "../../lib/auth.js";
import { savedItems, userHistory } from "../../db/schema.js";

// Saved items and search history for logged-in users. Every route needs a better-auth session cookie.
const db = drizzle(new Pool({ connectionString: process.env.DATABASE_URL }));

type AuthedRequest = Request & { userId?: string };

async function requireSession(req: AuthedRequest, res: Response, next: NextFunction) {
  try {
    const session = await auth.api.getSession({ headers: fromNodeHeaders(req.headers) });
    if (!session?.user) {
      res.status(401).json({ error: "Not logged in" });
      return;
    }
    req.userId = session.user.id;
    next();
  } catch (err) {
    next(err);
  }
}

const str = (v: unknown, max = 1000): string | null =>
  typeof v === "string" && v.trim() ? v.trim().slice(0, max) : null;

function savedJson(r: typeof savedItems.$inferSelect) {
  return {
    product_id: r.productId,
    image_url: r.imageUrl,
    category_name: r.categoryName,
    source: r.source,
    created_at: r.createdAt.toISOString(),
  };
}

function historyJson(r: typeof userHistory.$inferSelect) {
  return { id: r.id, kind: r.kind, text: r.text, scene: r.scene, created_at: r.createdAt.toISOString() };
}

export const userDataRouter: Router = Router();
userDataRouter.use(["/saved", "/history"], requireSession);

// GET /api/saved -> { items: [...] } newest first
userDataRouter.get("/saved", async (req: AuthedRequest, res, next) => {
  try {
    const rows = await db
      .select()
      .from(savedItems)
      .where(eq(savedItems.userId, req.userId!))
      .orderBy(desc(savedItems.createdAt));
    res.json({ items: rows.map(savedJson) });
  } catch (err) {
    next(err);
  }
});

// POST /api/saved { product_id, image_url?, category_name?, source? } -> { item } (upsert)
userDataRouter.post("/saved", async (req: AuthedRequest, res, next) => {
  try {
    const productId = str(req.body?.product_id, 300);
    if (!productId) {
      res.status(400).json({ error: "product_id is required" });
      return;
    }
    const values = {
      imageUrl: str(req.body?.image_url),
      categoryName: str(req.body?.category_name, 200),
      source: str(req.body?.source, 100),
    };
    // On re-save, only overwrite the fields that were sent (keep earlier image/category/source).
    const changed = Object.fromEntries(Object.entries(values).filter(([, v]) => v !== null));
    const [row] = await db
      .insert(savedItems)
      .values({ userId: req.userId!, productId, ...values })
      .onConflictDoUpdate({
        target: [savedItems.userId, savedItems.productId],
        set: Object.keys(changed).length ? changed : { productId },
      })
      .returning();
    res.status(201).json({ item: savedJson(row!) });
  } catch (err) {
    next(err);
  }
});

// DELETE /api/saved/:product_id -> { deleted: true|false }
userDataRouter.delete("/saved/:product_id", async (req: AuthedRequest, res, next) => {
  try {
    const productId = String(req.params.product_id ?? "");
    const rows = await db
      .delete(savedItems)
      .where(and(eq(savedItems.userId, req.userId!), eq(savedItems.productId, productId)))
      .returning({ id: savedItems.id });
    res.json({ deleted: rows.length > 0 });
  } catch (err) {
    next(err);
  }
});

// GET /api/history?limit=20 -> { items: [...] } newest first (limit 1..100)
userDataRouter.get("/history", async (req: AuthedRequest, res, next) => {
  try {
    const n = Number(req.query.limit ?? 20);
    const limit = Number.isInteger(n) && n >= 1 && n <= 100 ? n : 20;
    const rows = await db
      .select()
      .from(userHistory)
      .where(eq(userHistory.userId, req.userId!))
      .orderBy(desc(userHistory.createdAt))
      .limit(limit);
    res.json({ items: rows.map(historyJson) });
  } catch (err) {
    next(err);
  }
});

// POST /api/history { kind: 'vibe'|'photo', text, scene? } -> { item }
userDataRouter.post("/history", async (req: AuthedRequest, res, next) => {
  try {
    const kind = req.body?.kind;
    const text = str(req.body?.text);
    if ((kind !== "vibe" && kind !== "photo") || !text) {
      res.status(400).json({ error: "kind must be 'vibe' or 'photo', and text is required" });
      return;
    }
    const [row] = await db
      .insert(userHistory)
      .values({ userId: req.userId!, kind, text, scene: str(req.body?.scene, 200) })
      .returning();
    res.status(201).json({ item: historyJson(row!) });
  } catch (err) {
    next(err);
  }
});
