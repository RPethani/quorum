---
description: UI design-system rules — primitives, tokens, settled patterns. Loads only when editing UI files.
paths:
  - "ui/**/*.tsx"
  - "ui/**/*.ts"
  - "ui/**/*.css"
---

# Design system — UI rules

Read this before touching any `.tsx` file. The codebase has a
deliberate visual language; new components that don't match it will
be rejected.

---

## Use existing primitives — don't roll your own

| Need | Use |
|---|---|
| A button | `components/ui/button.tsx` (`<Button>`) — variants `default \| primary \| outline \| ghost \| destructive`, sizes `sm \| md \| lg \| icon` |
| A header icon button | `IconBtn` in `app/workspace/page.tsx` (`h-8 w-8 rounded-md border border-border-default`) |
| A segmented control | Match `components/design-system/theme-toggle.tsx` exactly |
| A pill | The `Stat` component in `components/workspace/secondary-header.tsx` |
| A card | `components/ui/card.tsx` (`<Card variant="default \| elevated \| recessed">`) |
| A badge | `components/ui/badge.tsx` (`<Badge variant="neutral \| primary \| success \| warning \| danger">`) |
| A dialog | `components/ui/dialog.tsx` |
| Input | `components/ui/input.tsx` |
| File picker | `components/ui/file-picker.tsx` |
| Theme toggle | `components/design-system/theme-toggle.tsx` (already wired) |

If the primitive you need doesn't exist, **first** check whether one
of the existing ones can be made to fit (with className overrides).
Add a new primitive only when the user explicitly asks or three
unrelated callers need it.

---

## Token classes — use these, not raw colours

The CSS tokens are defined in `app/globals.css` and exposed to
Tailwind. **Never** use `text-blue-600`, `bg-zinc-100`, `border-gray-300`,
or any raw Tailwind palette colour. Always use a token.

### Surfaces
- `bg-canvas` — the page background
- `bg-elevated` — cards, dialogs, primary header
- `bg-recessed` — subtle pills, secondary header bg, hover fills

### Text
- `text-fg-primary` — headings, body text
- `text-fg-secondary` — labels, default UI text
- `text-fg-tertiary` — helper text, timestamps, meta

### Borders
- `border-border-default` — default border for cards / pills / inputs

### Accents
- `accent-primary`, `accent-primary-weak`
- `accent-success`, `accent-success-weak`
- `accent-warning`, `accent-warning-weak`
- `accent-danger`, `accent-danger-weak`

The `-weak` variants are the muted backgrounds for pill fills. Use
`bg-accent-X-weak text-accent-X border-accent-X/40` together.

---

## Patterns we've already settled

### Segmented control (Theme toggle, Simple/Advanced toggle)

```tsx
<div className="inline-flex items-center gap-0 rounded-md border border-border-default bg-elevated p-0.5">
  {OPTIONS.map(({ value, Icon, label }) => {
    const active = current === value;
    return (
      <button
        type="button"
        aria-pressed={active}
        aria-label={label}
        title={label}
        onClick={() => onChange(value)}
        className={cn(
          "inline-flex h-7 w-7 items-center justify-center rounded-sm transition-colors duration-100",
          active
            ? "bg-accent-primary-weak text-accent-primary"
            : "text-fg-secondary hover:text-fg-primary",
        )}
      >
        <Icon size={14} strokeWidth={1.5} />
      </button>
    );
  })}
</div>
```

The `p-0.5` outer + `rounded-sm` inner is what produces the inset
look. Don't reinvent it.

### Header icon button (`IconBtn`)
```tsx
<button
  className="inline-flex h-8 w-8 items-center justify-center
             rounded-md border border-border-default text-fg-secondary
             hover:bg-recessed hover:text-fg-primary transition-colors"
  title="Open settings"
  aria-label="Open settings"
>
  <Icon size={14} />
</button>
```

### Tooltip rule for icon-only elements

**Every icon-only button, link, or interactive element MUST be wrapped
in `<Tooltip label="…">` AND carry an `aria-label` on the trigger.**

Don't use the native HTML `title` attribute alone — browsers delay
showing it for ~700–1500ms, which is too slow for icon-only chrome.

```tsx
import { Tooltip } from "@/components/ui/tooltip";

<Tooltip label="Open settings" side="bottom" align="center">
  <button
    type="button"
    aria-label="Open settings"
    onClick={...}
    className="..."
  >
    <Icon size={14} />
  </button>
</Tooltip>
```

The `<Tooltip>` primitive (`components/ui/tooltip.tsx`) is a CSS-only
fade-in (~120ms) with no JavaScript-side delay. It uses
`group-hover` / `group-focus-within`, so it shows on hover *and* on
keyboard focus.

`<Tooltip>` accepts:
- `side="top" | "bottom"` — defaults to `"bottom"`
- `align="start" | "center" | "end"` — defaults to `"center"`

For triggers near the right edge (dialog close, header end), use
`align="end"` to keep the tooltip on-screen.

**Why also keep `aria-label`:** screen readers don't see the visual
tooltip. The `aria-label` on the trigger carries the accessibility
name independently.

This applies to:
- Header icon buttons (`IconBtn` wraps them automatically)
- Segmented controls (Theme toggle, Simple/Advanced toggle — every
  segment is icon-only and gets its own `<Tooltip>` wrapper)
- Dialog close buttons (the `<X>` in the corner)
- Avatar stacks (the participant chips — label is the display name
  + status from `tooltipFor(p)`)
- The `+` add button after avatar stacks
- Any other element where the user is shown a glyph alone

**`IconBtn` enforces this in TypeScript** — `title: string` is a
required prop, and the component renders `<Tooltip label={title}>`
+ `aria-label={title}` internally. Use `IconBtn` whenever it fits.

When auditing, two checks should both come back silent:

```bash
# 1. Every icon-only <button> must have aria-label.
python3 - <<'EOF'
import re, pathlib
for f in list(pathlib.Path('components').rglob('*.tsx')) + list(pathlib.Path('app').rglob('*.tsx')):
    txt = f.read_text()
    for m in re.finditer(
        r'<button\b([^>]*?)>\s*(<[A-Z][A-Za-z0-9]*\b[^>]*?/>)\s*</button>',
        txt, re.DOTALL,
    ):
        attrs = m.group(1)
        if 'aria-label=' in attrs:
            continue
        line = txt[:m.start()].count('\n') + 1
        print(f"{f}:{line} icon-only button missing aria-label")
EOF

# 2. No use of the slow native `title` attribute on a <button>.
grep -rn 'title="' components app | grep -v 'tooltip.tsx' | grep -v 'aria-' | head
```

### Status pill (labelled stat)
```tsx
<span className={cn(
  "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium",
  toneClasses,
)}>
  <span className="opacity-70">Working</span>
  <span className="tabular-nums">3</span>
</span>
```

The label always has `opacity-70` so the value reads as primary.
Numeric values always `tabular-nums`.

### Avatar stack (participants)
Overlapping circles using `flex items-center -space-x-2` on the `<ul>`,
with `<ParticipantAvatar size={24}>` at fixed size and a coloured
ring for status.

---

## Layout rules

### The two-row header

- **Row 1 (`<Header>`)** — brand on the left, surface mode toggle
  next to it, dialog icon buttons on the right. This row is
  identity + navigation. Operational signals do **not** go here.
- **Row 2 (`<SecondaryHeader>`)** — labelled status stats on the
  left (always visible, always with labels), participant avatar
  stack on the far right. This row is status + participants.

### Pills are always visible

If a stat exists in the system, it gets a pill in the secondary
header *at all times* with its current value. Don't hide pills
when their value is zero or "normal". The strip is a stable
dashboard, not a notifications row.

If something genuinely has no value (e.g. cost gauge before state
loads), render `—`, not nothing.

### Pills always have labels

Every pill says what it is: `Working 3`, `For you 2`, `State Active`,
`Live connected`, `Spend $3.78 / $50 (8%)`. Never bare numbers.

### Participants in chrome are icon-only

Icons in the avatar stack are 24px circles with brand glyph + status
ring. Names appear as tooltips on hover, not labels. The `+` button
is a 24px dashed circle with just a `+` glyph.

---

## Comments and copy

Component files start with a brief docstring explaining *what* the
component is and *why* the non-obvious choices were made. Don't
narrate the code; explain decisions:

```tsx
/**
 * The user-facing surface for one open Ask. Renders one of four
 * shapes (confirm | pick_one | pick_any | write). Header / author
 * are normalised by the conductor before validation, so this
 * component trusts the Ask record verbatim.
 */
```

Inline comments only when the why is non-obvious — never narrate
what the code does.

User-visible copy follows the tone in `.claude/terminology.md`.

---

## Hot spots — change these and break things

- `components/workspace/secondary-header.tsx` — status row layout.
  Touched almost every UX iteration; keep it stable.
- `components/workspace/participant-avatar.tsx` — brand glyphs
  inlined; don't replace with an icon library without the user.
- `components/workspace/ask-card.tsx` — the four answer shapes.
  Keep them coherent; new shapes need a server-side counterpart
  in `workspace/asks.py:validate_answer` and
  `workspace/ask_answerer.py:_render_body`.
- `app/workspace/page.tsx` — the shell. Big file, but everything
  has its spot. Don't refactor without need.

---

## When you must add something new

1. Read the closest existing neighbour and copy its shape.
2. Use existing primitives + tokens. No raw colour, no new sizes.
3. Make it match the patterns above (segmented control, status pill,
   icon button, avatar). If your thing doesn't fit any pattern,
   stop and ask.
4. Run `tsc --noEmit` and `biome check` before declaring done.
