# Weekly Engineering Journal — Week 3

- **Name:** Nishika
- **Roll Number:** 1024031036
- **Date Range:** 03 Sep 2026 – 09 Sep 2026
- **Module / Component:** Authentication Client & Form Systems

---

## 1. Goal & Objectives
- Initialize the Better-Auth React client in `frontend/src/lib/auth-client.ts`.
- Build the `LoginForm` and `SignupForm` components.
- Implement social authentication handlers for Google OAuth.

---

## 2. Technical Activities & Implementation

### A. Client Authentication Bindings
- Created `frontend/src/lib/auth-client.ts` using `createAuthClient` from `better-auth/react`.
- Bound backend URL consumption to `import.meta.env.VITE_BACKEND_APP_URL`.
- Declared the OAuth trigger function `handleGoogleSignIn` directing successful sign-ins to `/dashboard`.

### B. View Implementation
- Implemented `LoginForm` (`frontend/src/components/login-form.tsx`) handling email/password authentication via `authClient.signIn.email`.
- Built `SignupForm` (`frontend/src/components/signup-form.tsx`) with client-side password verification before invoking `authClient.signUp.email`.

---

## 3. Snippets & Patterns (MWE / Ready Reckoner)

### Client Social Authentication Trigger
```typescript
import { createAuthClient } from "better-auth/react";

export const authClient = createAuthClient({
  baseURL: import.meta.env.VITE_BACKEND_APP_URL,
});

export const handleGoogleSignIn = async () => {
  await authClient.signIn.social({
    provider: "google",
    callbackURL: `${import.meta.env.VITE_FRONTEND_APP_URL}/dashboard`,
    errorCallbackURL: `${import.meta.env.VITE_FRONTEND_APP_URL}/signup`,
  });
};

```

---

## 4. Challenges & Mitigations
- **Challenge:** Form submissions triggering full page reloads and clearing transient error messages.
  - **Mitigation:** Intercepted form submission events with `e.preventDefault()` and bound asynchronous error states to React state.

---

## 5. Next Week Objectives
- Wrap private views in a `ProtectedRoute` component.
- Build the persistent navigation layout (`AppSidebar`) for `Dashboard.tsx`.