# Quorum Design System — v0.1

This document is the design contract for every Quorum UI surface. It is the codified source of truth derived from §3 of `IMPLEMENTATION_BOOTSTRAP.md`. Where this document and the bootstrap conflict, the bootstrap wins; where this document adds detail beyond the bootstrap, that detail is implementation discretion. **Do not deviate from this spec without explicit user approval.**

The system is implemented under `ui/components/design-system/` (tokens, theme provider) and `ui/components/ui/` (primitives owned by us, customized from shadcn/ui).

---

## 1. Aesthetic principles

The user's directive: *minimalist, simple, primarily black-and-white, thoughtful accent colors only where they add meaning, lighter tones that work in both light and dark modes.* Apple's Pro design language (Jony Ive era) is the closest reference point.

- **Restraint over decoration.** Whitespace earns its keep. Borders are 1px when present at all. Drop shadows are rare and subtle (used to elevate, not to embellish).
- **Type over chrome.** Typography carries the weight. Buttons can be just text in many cases. Cards are defined by spacing more than by visible borders.
- **Neutral first, color as signal.** Color is communication, not decoration. A button is colored because it represents an action with consequence; a status badge is colored because it conveys state. Decorative color is forbidden.
- **Calm motion.** Transitions are 150–200ms with `ease-out`. No bouncing, no flourishes. The system feels considered, not playful.
- **Grid-disciplined spacing.** 8px base unit. Everything is a multiple. Even when the user can't see the grid, they feel it.

---

## 2. The neutral scale

A 9-step neutral scale (`neutral-50` … `neutral-950`). Both modes use the same scale; mode determines which end is foreground. True extremes: `neutral-50` = `#FAFAFA`, `neutral-950` = `#0A0A0A` — never pure white, never pure black. Intermediate steps are slightly cool (subtle blue undertone, ~2% saturation) for an engineered, precise feel.

**Light mode mapping**

| Token | Hex | Used as |
|---|---|---|
| `bg-canvas` | `neutral-50` | Page background |
| `bg-recessed` | `neutral-100` | Recessed surfaces (sidebars, sub-panes) |
| `bg-elevated` | `white` | Elevated cards, popovers |
| `fg-primary` | `neutral-950` | Primary text |
| `fg-secondary` | `neutral-700` | Secondary text |
| `fg-tertiary` | `neutral-500` | Tertiary text, disabled |
| `border-default` | `neutral-200` | Default 1px borders |
| `border-emphasis` | `neutral-300` | Emphasized 1px borders |

**Dark mode mapping**

| Token | Hex | Used as |
|---|---|---|
| `bg-canvas` | `neutral-950` | Page background |
| `bg-recessed` | `neutral-900` | Recessed surfaces |
| `bg-elevated` | `neutral-800` | Elevated cards, popovers |
| `fg-primary` | `neutral-50` | Primary text |
| `fg-secondary` | `neutral-300` | Secondary text |
| `fg-tertiary` | `neutral-500` | Tertiary text, disabled |
| `border-default` | `neutral-800` | Default 1px borders |
| `border-emphasis` | `neutral-700` | Emphasized 1px borders |

The relationship between layers is preserved across modes. Visual hierarchy stays consistent.

---

## 3. The accent palette — five accents, each with a job

| Token | Job | Light tone | Dark tone | Use only for |
|---|---|---|---|---|
| `accent-primary` | Primary action / linkable | `#3B82F6` | `#60A5FA` | Primary buttons, focused inputs, active links, the user's avatar |
| `accent-success` | Decided / completed | `#10B981` | `#34D399` | DECISION badges, COMPLETED status, "yes" affirmations |
| `accent-warning` | Blocked / pending | `#F59E0B` | `#FBBF24` | BLOCKED states, "your turn" indicators, pending permissions |
| `accent-danger` | Failed / refused / destructive | `#EF4444` | `#F87171` | Failed invocations, denied permissions, destructive confirmations |
| `accent-muted` | Auxiliary / informational | `#8B5CF6` | `#A78BFA` | EXPLANATION moves, INTERJECTION origin marker, audit-trail metadata |

Every accent has a **`-weak`** variant for backgrounds, badges, and tinted surfaces (e.g., `accent-primary-weak` is `blue-100` light / `blue-950` dark). Weak variants are what let us use color systemically without it ever feeling loud.

**Forbidden:** a sixth accent. Resist the temptation to add "info" or "neutral-positive" — the constraint produces the calm.

---

## 4. Typography

**Two typefaces, three roles**

- **Inter** — primary UI. Variable font; weights `400`, `500`, `600`, `700` only.
- **JetBrains Mono** — code, agent handles, IDs, timestamps, keyboard shortcuts.

**Type ramp**

| Token | Size / line-height / weight | Use |
|---|---|---|
| `text-xs` | 12 / 16 / 500 | Metadata, timestamps, tertiary labels |
| `text-sm` | 14 / 20 / 400 | Body, table cells, most UI |
| `text-base` | 15 / 24 / 400 | Reading content (deliberation prose) |
| `text-md` | 16 / 24 / 500 | Medium-emphasis labels, button text |
| `text-lg` | 18 / 28 / 600 | Section titles, card headings |
| `text-xl` | 22 / 32 / 600 | Page subheadings |
| `text-2xl` | 28 / 36 / 700 | Page titles, deliberation titles |
| `text-3xl` | 36 / 44 / 700 | Workspace name (rare) |

**Mono ramp** is one step smaller than the prose equivalent (mono is naturally heavier; the offset compensates).

**Letter-spacing** — body 0; headings `-0.01em`; all-caps labels `0.02em`.

**Numerals** — all numerals are tabular (`font-variant-numeric: tabular-nums`). Counts, costs, timestamps, durations align vertically.

---

## 5. Spacing & layout

**8px base.** Spacing tokens:

| Token | px | Use |
|---|---|---|
| `1` | 4 | Tight intra-component cases only |
| `2` | 8 | Default tight |
| `3` | 12 | Default |
| `4` | 16 | Component-internal grouping |
| `5` | 20 | |
| `6` | 24 | Section gaps |
| `8` | 32 | |
| `10` | 40 | |
| `12` | 48 | |
| `16` | 64 | |
| `20` | 80 | |
| `24` | 96 | |

**Container widths**

- Deliberation prose pane: max-width `60ch` (reading-comfortable line length).
- Settings panels: max-width `48rem`.
- Activity feed: no max — it's a list.

**Three-pane layout (§9.5 of the design doc)**

- Left rail (sidebar): 280px fixed; collapsible to 60px (icon-only).
- Center pane: flexible; reading-width capped per above.
- Right rail (activity / context): 360px; collapsible to 0.

**Responsive** — desktop-primary. <1024px: right rail collapses to a slide-over. <768px: left rail collapses too.

---

## 6. Border, radius, shadow

**Borders** — 1px, never thicker.

**Radius**

| Token | px | Use |
|---|---|---|
| `radius-none` | 0 | Tables, code blocks |
| `radius-sm` | 4 | Inputs, small buttons |
| `radius-md` | 8 | Cards, modals, larger buttons |
| `radius-lg` | 12 | Workspace shell, large surfaces |

**Shadow** — three steps, all very subtle.

| Token | Use |
|---|---|
| `shadow-sm` | Subtly-elevated cards on hover |
| `shadow-md` | Popovers, dropdowns |
| `shadow-lg` | Modals, sheets |

In dark mode, shadows are barely visible. Compensate with a 1px border on elevated surfaces to keep them legibly separated.

---

## 7. Component contracts

### Primitives (in `ui/components/ui/`, customized from shadcn/ui)

- **Button** — variants: `default` (filled neutral), `primary` (filled accent-primary), `outline` (1px border, transparent fill), `ghost` (no border, no fill), `destructive` (filled accent-danger). Sizes: `sm`, `md` (default), `lg`. Icon-only variant has square aspect ratio.
- **Card** — variants: `default` (1px border, no shadow), `elevated` (`shadow-sm` + 1px border), `recessed` (`bg-recessed`, no border).
- **Input, Textarea, Select, Combobox** — all share the same focused state: 1px border becomes `accent-primary` plus a 2px outer ring at `accent-primary-weak`.
- **Badge** — pill-shaped, `text-xs`, padding `1.5/3`. Variants per accent: `primary`, `success`, `warning`, `danger`, `muted`, `neutral`. Weak background, strong text.
- **Tooltip** — appears on hover, 200ms delay. Mono font for keyboard shortcuts; sans for prose tooltips.
- **Dialog, Sheet, Popover, DropdownMenu** — standard shadcn behaviors with our radius and shadow tokens.
- **Tabs** — underline style, not pill. Active tab has a 2px bottom border in `accent-primary`; inactive tabs have 1px in `neutral-200`/`neutral-800`.
- **Separator** — 1px, `border-default`. Vertical separators have `mx-3`; horizontal have `my-3`.

### Custom components (built by us)

- **MoveCard** — the central artifact. Header line per §5 reference convention; body sections rendered as Markdown subtypes. Composing state has a subtly pulsing left border in `accent-primary`. Failed state has a strikethrough header and `accent-danger-weak` background. Variants per move type with subtly different left-border colors.
- **DeliberationTimeline** — vertical thread of move cards. Compact (150px) and expanded (full) modes.
- **ManifestProgressBar** — outcome-manifest progress. `accent-success` for complete; `accent-warning` for in-progress.
- **YourTurnCallout** — `accent-warning-weak` background, small `accent-warning` icon, sticky-top-of-pane positioning.
- **PermissionRequestCard** (Phase 11) — visually distinct from move cards: `accent-warning-weak` outer ring, lock icon, inline action buttons.
- **CostChip** — running cost in the workspace header. Mono numerals; `accent-warning` text when >80% of ceiling.
- **HandleAvatar** — small circular badge with the handle's first letter and a deterministic accent color from a fixed 8-color palette of desaturated mid-tones (avatar palette is independent of the 5 accents). Same handle always gets the same color.

### Phasing of components

| Phase | Components introduced |
|---|---|
| 2 (now) | Button, Card, Input, Textarea, Badge, Tabs, Separator, CostChip, HandleAvatar, MoveCard skeleton |
| 7 | Tooltip, Dialog, Sheet, Popover, DropdownMenu; full MoveCard; DeliberationTimeline; ManifestProgressBar; YourTurnCallout |
| 11 | PermissionRequestCard |

Components introduced later still adhere to this design system; their contracts are pre-declared above so later phases have a target.

---

## 8. Motion

- All transitions: `150ms cubic-bezier(0.16, 1, 0.3, 1)` ("ease-out-expo").
- Page transitions: 200ms.
- Modal/sheet enter: 250ms.
- Composing dot-pulse (move cards): 1.5s loop, ≥60% opacity at minimum.
- Hover transitions on buttons: 100ms.
- **No bounces. No springs. No spinning loaders unless absolutely necessary.**

---

## 9. Iconography

Lucide icons, stroke width `1.5`. Sizes: `16px` inline, `20px` button-icon, `24px` nav, `32px` empty-states.

Standard mappings:

- **Status:** `CircleCheck` (success), `CircleAlert` (warning), `CircleX` (error), `Circle` (idle), `CircleDot` (active/in-progress)
- **Actions:** `Play`, `Pause`, `RotateCw`, `Copy`, `Download`, `Settings2`
- **Navigation:** `ChevronRight` / `ChevronDown`, `ArrowRight`
- **Object types:** `MessageSquare` (deliberation), `FileText` (artifact), `Users` (participants), `BookOpen` (context), `KeyRound` (permissions), `Clock` (timeline)

Avoid icon-only buttons except in tightly-constrained spaces (toolbars, table actions). Always pair with a tooltip.

---

## 10. Accessibility

- **Color contrast** — all text-on-background combinations pass WCAG AA at minimum. Primary text on canvas: AAA.
- **Focus indicators** — 2px ring in `accent-primary-weak` plus a 1px shift to `accent-primary` on the bordered edge. Never rely on color alone.
- **Keyboard navigation** — every interactive element reachable via Tab; visible focus order matches visual order; skip-to-content link at top of pages.
- **Screen reader labels** — every icon-only button has `aria-label`. Move cards have a hidden `aria-describedby` summarizing the move.
- **Reduced motion** — respect `prefers-reduced-motion`. Composing pulse becomes a static dot. Page transitions become instant.

---

## 11. Light / dark mode

- System preference is the default (`next-themes` with `defaultTheme="system"`).
- User can override via a toggle in the workspace header — three states: `light`, `dark`, `system`.
- Preference persists in localStorage.
- **No flash of incorrect theme** — `next-themes` handles SSR/CSR mismatch via `suppressHydrationWarning`.
- Every component must be tested in both modes during development. The `_design-system` showcase route is the verification surface.

---

## 12. Empty & error states

Every list, panel, and pane has a designed empty state. The pattern:

- Centered vertical layout
- 32px icon at top, in `neutral-400` / `neutral-600`
- One-line title, `text-md`, `neutral-700` / `neutral-300`
- One sentence of explanation, `text-sm`, `neutral-500`
- Action button if applicable, primary variant

Error states use the same layout with `accent-danger` for the icon and a more constructive title (specific, not generic). Always include a recovery action.

---

## 13. Forbidden patterns

- No skeuomorphism (no fake-paper textures, no material-mimicking gradients).
- No emoji as UI chrome (emoji can appear in user-authored content only).
- No animated gradients, glows, or parallax.
- No more than the 5 accents.
- No nested cards. Use a recessed surface or combine into one card.
- No round-corner-on-some-sides-only (except tabs, intentionally).
- No icon-spamming. If three list items in a row have decorative icons that are not communicating different states, drop them.

---

## 14. The two design tests

Apply both before considering any UI surface complete.

1. **The grayscale test.** Convert your screen to grayscale (or imagine it). Does the hierarchy still read clearly? If color is the only thing distinguishing two elements, the design is fragile. Rebuild the hierarchy with type weight, spacing, or position; reserve color for *additional* signal.
2. **The whisper test.** If every element is shouting, nothing is heard. Look at any screen and ask: *what should the user see first? second? third?* If everything is competing equally, demote 80% of it.

These tests are how we catch over-design before the user has to.
