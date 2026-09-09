# Weekly Engineering Journal — Week 1

- **Name:** Kartik
- **Roll Number:** 1024031031
- **Date Range:** 20 Aug 2026 – 26 Aug 2026
- **Module / Component:** Repository Topology, Workspace Planning, Environment Initialization

---

## 1. Goal & Objectives
- Initialize the monorepo structure for `MoodDrobe` (`backend/`, `frontend/`, `ml-service/`, `journals/`).
- Configure package management using `pnpm` workspace tooling.
- Establish strict TypeScript compiler settings for backend runtime safety.

---

## 2. Technical Activities & Implementation

### A. Monorepo Scaffolding
- Initialized root repository and declared sub-packages:
  - `backend/`: Node.js, Express, Drizzle ORM, Better-Auth.
  - `frontend/`: React 19, Vite, Tailwind CSS.
  - `ml-service/`: Reserved for Python-based CLIP embedding inference.
- Created `backend/pnpm-workspace.yaml` configuring `esbuild` build permissions.

### B. Compiler & Module Resolution Settings
- Configured `backend/tsconfig.json`:
  - Enforced `nodenext` module resolution and `esnext` targets.
  - Enabled strict flags: `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, and `verbatimModuleSyntax`.

---

## 3. Snippets & Patterns (MWE / Ready Reckoner)

### Strict Backend TypeScript Configuration (`backend/tsconfig.json`)
```json
{
  "compilerOptions": {
    "rootDir": "./src",
    "outDir": "./dist",
    "module": "nodenext",
    "target": "esnext",
    "lib": ["esnext"],
    "types": ["node"],
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "verbatimModuleSyntax": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*.ts"]
}
```
---

## 4. Challenges & Mitigations
- **Challenge:** Node.js native ESM incompatibility with legacy CommonJS packages.
  - **Mitigation:** Enforced `"type": "module"` in `backend/package.json` and standardized `.js` extension suffixes in source imports.

---

## 5. Next Week Objectives
- Author the formal Software Engineering Project Report.
- Containerize PostgreSQL using Docker Compose.