# Weekly Engineering Journal — Week 2

- **Name:** Nishika
- **Roll Number:** 1024031036
- **Date Range:** 27 Aug 2026 – 02 Sep 2026
- **Module / Component:** Design Tokens, OKLCH Color Systems & Form Primitives

---

## 1. Goal & Objectives
- Establish the design system tokens for `MoodDrobe` in `frontend/src/index.css`.
- Implement responsive compound field components in `frontend/src/components/ui/field.tsx`.
- Integrate modern typography and layout reset rules.

---

## 2. Technical Activities & Implementation

### A. Design Token Configuration
- Defined light and dark mode color profiles using perceptual OKLCH color spaces.
- Configured CSS variables for surfaces, primary/secondary accents, borders, and sidebar states:
  - `--background`: `oklch(1 0 0)` (light) / `oklch(0.145 0 0)` (dark)
  - `--primary`: `oklch(0.205 0 0)` (light) / `oklch(0.922 0 0)` (dark)
- Integrated `@fontsource-variable/geist` as the base variable font family.

### B. Compound Form Field Architecture
- Engineered `Field`, `FieldGroup`, `FieldLabel`, `FieldDescription`, and `FieldError` components.
- Applied `class-variance-authority` (cva) to toggle between vertical, horizontal, and responsive alignments.

---

## 3. Snippets & Patterns (MWE / Ready Reckoner)

### Variant-Driven Field System Pattern
```typescript
import { cva, type VariantProps } from "class-variance-authority";

export const fieldVariants = cva("group/field flex w-full gap-2", {
  variants: {
    orientation: {
      vertical: "flex-col *:w-full",
      horizontal: "flex-row items-center",
      responsive: "flex-col *:w-full @md/field-group:flex-row @md/field-group:items-center",
    },
  },
  defaultVariants: {
    orientation: "vertical",
  },
});

```
---

## 4. Challenges & Mitigations
- **Challenge:** Managing nested field error rendering without inconsistent margins across screen widths.
  - **Mitigation:** Applied container queries (`@container/field-group`) directly inside Tailwind utility classes.

---

## 5. Next Week Objectives
- Connect frontend client to backend authentication endpoints.
- Build dedicated Login and Signup form components.