<!--
Manifest template — saas-product

Starter manifest for a workspace whose goal is to refine a SaaS product
idea into a buildable, decided spec. The bootstrapper proposes this as
the starting point when `quorum init --manifest-template saas-product` is
used or when the problem statement reads like a SaaS product brainstorm.

This is a STARTING POINT, not a constraint. The first deliberation
refines it: artifacts may be added, removed, or modified to fit the
actual project.
-->
---
status: DRAFTING            # DRAFTING | READY | LOCKED
protocol_version: 0.1
created: 2026-04-28
locked_at: null
template_used: saas-product
---

# Outcome Manifest — SaaS Product

## Required artifacts

### requirements.md
**Purpose:** Complete functional specification of the product.
**Production pattern:** specifier-authored
**Specifier role:** spec-writer
**Production triggers:** all deliberations tagged `feature` are DECIDED
**Depends on:** none
**Required sections:**
- Product vision (1–2 paragraphs)
- User personas (≥ 2)
- Core features (each with: description, user story, acceptance criteria)
- Non-functional requirements (performance, security, accessibility)
- Out-of-scope (explicit list)
**Completion checks:**
- All required sections present and non-empty
- Core features section has ≥ 3 features
- Each feature has all required sub-elements
- Approved by decider (DECISION on a `ratifies: requirements.md` deliberation)

### ux-requirements.md
**Purpose:** Layout and interaction specification.
**Production pattern:** synthesis-aggregated
**Contributing deliberation tags:** `ux`, `flow`, `component`
**Depends on:** requirements.md
**Becomes eligible for production when:** requirements.md is complete
**Required sections:**
- Page/screen inventory (each with: purpose, key components, navigation)
- Component library
- Critical user flows
- Information architecture
**Completion checks:**
- All pages from requirements.md represented
- Each critical flow traces through specific pages
- Cross-references to requirements.md resolve

### tech-stack.md
**Purpose:** The chosen stack and the reasoning behind it.
**Production pattern:** specifier-authored
**Depends on:** requirements.md
**Required sections:**
- Stack overview (one paragraph)
- Per-layer choices (frontend, backend, data, infra) with rationale
- Trade-offs accepted
- Alternatives considered (links to ADRs)

### pricing.md
**Purpose:** Pricing tier structure and reasoning.
**Production pattern:** specifier-authored
**Depends on:** requirements.md
**Required sections:**
- Tier structure (each tier: name, price, included features, target audience)
- Pricing rationale
- Trial/free policies
- Annual vs monthly policy
- Out-of-scope (e.g., usage-based pricing in v1)

### mvp-scope.md
**Purpose:** What ships in v1 vs what's deferred.
**Production pattern:** synthesis-aggregated
**Contributing deliberation tags:** `scope`, `mvp`
**Depends on:** requirements.md, ux-requirements.md
**Required sections:**
- In-scope features (with rationale for inclusion)
- Out-of-scope features (with rationale for deferral)
- Acceptance criteria for "v1 ships"
- Risks of the chosen scope

## Quality gates

- No unresolved DEPUTY_DECISIONs
- No deliberations in any BLOCKED state
- All ADRs have status: confirmed (not provisional)
- Open Questions register has zero unresolved items tagged `blocking`
- All artifacts pass their completion checks
- All declared context sources have current digests and have been reviewed by the user (§1.8)

## Closing ceremony

When all required artifacts pass completion checks AND all quality gates are clear, the conductor opens a final meta-deliberation (`final: true`) for the closing summary. The decider issues a DECISION on this meta-deliberation to transition the workspace to `COMPLETED`.
