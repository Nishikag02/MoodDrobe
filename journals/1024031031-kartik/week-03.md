# Weekly Engineering Journal — Week 3

- **Name:** Kartik
- **Roll Number:** 1024031031
- **Date Range:** 03 Sep 2026 – 09 Sep 2026
- **Module / Component:** Relational Modeling & Better-Auth Server Engine

---

## 1. Goal & Objectives
- Design relational database schemas for users, sessions, accounts, and verifications using Drizzle ORM.
- Integrate Better-Auth server using the Drizzle PostgreSQL adapter.
- Configure connection pooling via `pg.Pool`.

---

## 2. Technical Activities & Implementation

### A. Database Schema Modeling
- Authored `backend/src/db/schema.ts` defining PostgreSQL tables:
  - `user`: Primary user registry with unique email constraints.
  - `session`: User sessions tied with foreign key cascading deletes (`onDelete: "cascade"`).
  - `account`: OAuth/credential records with composite unique indexing (`issuer`, `accountId`).
  - `verification`: Identifier/token mappings with indexed lookups.

### B. Better-Auth Configuration
- Configured `backend/src/lib/auth.ts`:
  - Connected `drizzleAdapter` passing PostgreSQL schema definitions.
  - Enabled email/password strategies and configured Google OAuth credentials.
  - Set CORS-trusted origins to match `http://localhost:5173`.
- Set up connection pooling in `backend/src/db/index.ts` via `node-postgres` (`pg.Pool`).

---

## 3. Snippets & Patterns (MWE / Ready Reckoner)

### Better-Auth Initialization with Drizzle Adapter
```typescript
import { betterAuth } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";
import * as schema from "../db/schema.js";

const db = drizzle(new Pool({ connectionString: process.env.DATABASE_URL }), {
  schema,
});

export const auth = betterAuth({
  database: drizzleAdapter(db, { provider: "pg", schema }),
  baseURL: "http://localhost:3000",
  trustedOrigins: ["http://localhost:5173"],
  emailAndPassword: { enabled: true },
  socialProviders: {
    google: {
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    },
  },
});

```

---

## 4. Challenges & Mitigations
- **Challenge:** Avoiding orphaned session rows upon account termination.
  - **Mitigation:** Applied foreign key constraints with explicit cascading deletion rules directly in Drizzle table schema definitions.

---

## 5. Next Week Objectives
- Build Express HTTP server and attach Better-Auth node handlers.
- Configure `drizzle-kit` migration scripts in `package.json`.