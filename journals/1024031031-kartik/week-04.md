# Weekly Engineering Journal — Week 4

- **Name:** Kartik
- **Roll Number:** 1024031031
- **Date Range:** 10 Sep 2026 – 16 Sep 2026
- **Module / Component:** Express 5 Integration & Drizzle Migration Pipeline

---

## 1. Goal & Objectives
- Mount Better-Auth handlers onto Express 5 routing middleware.
- Configure CORS with credential forwarding for cross-origin cookies.
- Set up database migration scripts in `drizzle.config.ts` and `package.json`.

---

## 2. Technical Activities & Implementation

### A. Express 5 Server Mounting
- Built `backend/src/app/index.ts`:
  - Mounted wildcard Better-Auth routes using `app.all('/api/auth/{*any}', toNodeHandler(auth))`.
  - Configured CORS middleware allowing `http://localhost:5173` with `credentials: true`.
- Created server entrypoint in `backend/src/index.ts` utilizing Node's native `createServer`.

### B. Drizzle Kit Migration Pipeline
- Configured `backend/drizzle.config.ts` with PostgreSQL dialect and credentials ingestion.
- Configured package scripts:
  - `db:generate`: Extracts schema differences into SQL migrations.
  - `db:push`: Direct schema synchronization for rapid prototyping.
  - `db:studio`: Launches local visual database browser.

---

## 3. Snippets & Patterns (MWE / Ready Reckoner)

### Express Application Dispatcher Pattern
```typescript
import express from 'express';
import cors from 'cors';
import { toNodeHandler } from "better-auth/node";
import { auth } from "../lib/auth.js";

export function expressApp() {
  const app = express();

  app.use(
    cors({
      origin: "http://localhost:5173",
      methods: ["GET", "POST", "PUT", "DELETE"],
      credentials: true,
    })
  );

  app.all('/api/auth/{*any}', toNodeHandler(auth));
  app.use(express.json());

  app.get('/', (req, res) => {
    res.json({ message: 'MoodDrobe API Live' });
  });

  return app;
}
```

---

## 4. Challenges & Mitigations
- **Challenge:** Handling cookie authentication across separate local development ports (`5173` vs `3000`).
  - **Mitigation:** Explicitly enabled `credentials: true` on both the Express server CORS layer and the Better-Auth trusted origins array.

---

## 5. Next Week Objectives
- Implement clothing metadata ingestion endpoints.
- Establish inter-process communication with `ml-service` for vector generation.