<!--
Manifest template — research-direction

Starter manifest for a workspace whose goal is to take a research area
from "I'm interested in X" to "here's a coherent research direction with
specific questions, prior-art coverage, methodology, and testable
hypotheses."

This is a STARTING POINT, not a constraint. The first deliberation
refines it.
-->
---
status: DRAFTING
protocol_version: 0.1
created: 2026-04-28
locked_at: null
template_used: research-direction
---

# Outcome Manifest — Research Direction

## Required artifacts

### research-questions.md
**Purpose:** The actual questions this research direction is asking.
**Production pattern:** specifier-authored
**Required sections:**
- Top-level research question (one sentence)
- Sub-questions (≥ 3, each tractable on its own)
- Out-of-scope questions (explicitly excluded; with reasoning)
- Why these questions matter (theoretical and/or practical relevance)

### literature-survey.md
**Purpose:** The prior-art map. What's been done; what's contested; what's missing.
**Production pattern:** synthesis-aggregated
**Contributing deliberation tags:** `prior-art`, `literature`
**Depends on:** research-questions.md
**Required sections:**
- Key works (≥ 5, each with: citation, summary, relevance to our questions)
- Contested claims (where the literature disagrees)
- Identified gaps (what no one has addressed adequately)
- Methodological landscape (what approaches the field uses)

### methodology.md
**Purpose:** How we propose to investigate the research questions.
**Production pattern:** specifier-authored
**Depends on:** research-questions.md, literature-survey.md
**Required sections:**
- Approach (qualitative, quantitative, mixed; theoretical, empirical, computational)
- Data sources (or "to be identified")
- Analysis plan
- Validity threats and mitigations
- Alternatives considered (with rationale for rejection)

### hypotheses.md
**Purpose:** The testable predictions, where applicable.
**Production pattern:** specifier-authored
**Depends on:** research-questions.md, methodology.md
**Required sections:**
- Hypotheses (each: statement, type — directional/null, what would falsify it)
- Operationalizations (what counts as evidence for/against)
- Pre-registration commitments (what we're committing to before data)
- Non-hypothesizable questions (explicitly tagged as exploratory rather than confirmatory)

## Quality gates

- No unresolved DEPUTY_DECISIONs
- No deliberations in any BLOCKED state
- All ADRs have status: confirmed
- Open Questions register has zero unresolved items tagged `blocking`
- All artifacts pass their completion checks
- All declared context sources have current digests and have been reviewed by the user

## Closing ceremony

When all required artifacts pass and quality gates clear, the conductor opens a final meta-deliberation. The decider issues a DECISION transitioning the workspace to `COMPLETED`. The closing summary notes which sub-questions are well-scoped and which remain open for further work.
