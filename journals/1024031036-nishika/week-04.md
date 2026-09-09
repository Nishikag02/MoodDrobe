# Weekly Engineering Journal — Week 4

- **Name:** Nishika
- **Roll Number:** 1024031036
- **Date Range:** 10 Sep 2026 – 16 Sep 2026
- **Module / Component:** Router Security Guards & App Sidebar System

---

## 1. Goal & Objectives
- Implement authentication route guards via `ProtectedRoute.tsx`.
- Configure client router definitions in `frontend/src/routes/router.tsx`.
- Build the collapsible multi-section application sidebar (`app-sidebar.tsx`).

---

## 2. Technical Activities & Implementation

### A. Route Guard Subsystem
- Constructed `frontend/src/components/ProtectedRoute.tsx` using `authClient.useSession()`.
- Implemented loading indicators during session hydration and redirected unauthenticated sessions to `/login`.
- Configured nested routes protecting `/dashboard` inside `router.tsx`.

### B. Navigation Sidebar Construction
- Implemented `frontend/src/components/app-sidebar.tsx` with favorites, workspaces, and team switchers.
- Bound sidebar persistence to cookie state (`sidebar_state`) with a 7-day max-age.
- Added keyboard accessibility enabling sidebar toggling using `Ctrl+B` / `Cmd+B`.

---

## 3. Snippets & Patterns (MWE / Ready Reckoner)

### Session Guard Pattern with React Router
```typescript
import { Navigate, Outlet } from "react-router-dom";
import { authClient } from "@/lib/auth-client";

export default function ProtectedRoute() {
  const { data: session, isPending } = authClient.useSession();

  if (isPending) {
    return <div className="flex h-screen items-center justify-center">Loading...</div>;
  }

  if (!session) {
    return <Navigate replace to="/login"/>;
  }

  return <Outlet/>;
}
```
---

## 4. Challenges & Mitigations
- **Challenge:** Handling sidebar collapsible behavior across desktop rail modes and mobile drawers seamlessly.
  - **Mitigation:** Abstracted layout handling via `SidebarProvider` and `useIsMobile`, dynamically switching between fixed desktop elements and mobile `Sheet` overlays.

---

## 5. Next Week Objectives
- Build out wardrobe image gallery and grid display in `/dashboard`.
- Hook up file upload drag-and-drop zones with backend ingestion routes.