# Weekly Engineering Journal — Week 1

- **Name:** Nishika
- **Roll Number:** 1024031036
- **Date Range:** 20 Aug 2026 – 26 Aug 2026
- **Module / Component:** Ideation, Requirements Specification, Presentation Deck (PPT)

---

## 1. Goal & Objectives
- Finalize functional requirements for the `MoodDrobe` visual fashion recommendation system.
- Formulate and design the technical project evaluation slide deck (PPT).
- Define user experience journeys for wardrobe catalogs, mood boards, and outfit exploration.

---

## 2. Technical Activities & Implementation

### A. Evaluation Presentation Engineering (PPT)
- Designed and structured the evaluation deck:
  - Articulated the core problem: Bridging visual inspiration with personal wardrobe inventory using vector similarity search.
  - Diagrammed the high-level architecture separating `frontend`, `backend`, and `ml-service`.
  - Defined milestones for sprint evaluation, authentication flows, and machine learning inference integration.

### B. Client Application Planning
- Determined the frontend stack: React 19, Vite, Tailwind CSS v4, and headless UI primitives via `@base-ui/react`.
- Formulated the navigation hierarchy: Landing page (`/`), Authentication views (`/login`, `/signup`), and authenticated workspaces (`/dashboard`).

---

## 3. Snippets & Patterns (MWE / Ready Reckoner)

### Client Route Specification Contract
```typescript
export interface AppRouteDefinition {
  path: string;
  isProtected: boolean;
  component: string;
}

export const ROUTE_REGISTRY: AppRouteDefinition[] = [
  { path: "/", isProtected: false, component: "Home" },
  { path: "/login", isProtected: false, component: "Login" },
  { path: "/signup", isProtected: false, component: "Signup" },
  { path: "/dashboard", isProtected: true, component: "Dashboard" },
];

```
---

## 4. Challenges & Mitigations
- **Challenge:** Scope creep regarding initial UI complexity during the evaluation presentation.
  - **Mitigation:** Sequenced milestones into distinct phases: Authentication and layout in Phase 1, recommendation queries and CLIP integration in Phase 2.

---

## 5. Next Week Objectives
- Define the global CSS variable system using OKLCH color palettes.
- Implement compound form field primitives.


