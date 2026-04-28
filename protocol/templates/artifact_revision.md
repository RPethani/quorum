<!--
ARTIFACT_REVISION — an updated version of a previously-completed manifest
artifact, triggered by subsequent decisions. The prior version is preserved
under /artifacts/versions/<name>.v<n>.md; the current version is
/artifacts/<name>.md. Audit trail is honest about evolution.
-->
### [ARTIFACT_REVISION] @<handle> · <ISO-8601-timestamp> → targets <artifact-filename>

## Targets

<!-- The artifact filename (and optionally specific section refs).
     Example:
       - requirements.md
       - requirements.md#pricing -->

## What changes

<!-- Concrete: additions, removals, modifications. Describe at the section
     level, not as a diff. Example:
       - Added "Annual discount tiers" subsection under #pricing
       - Removed Mobile-only feature F-7 (out of scope per DECISION@...#0021)
       - Modified "MVP scope" to include onboarding flow -->

## Triggering decisions

<!-- The DECISION moves that drove this revision. One reference per line. -->

## Backwards-compatible?

<!-- yes | no
     A revision is backwards-incompatible if it breaks references from
     other artifacts (e.g., requirements.md removed a feature that
     ux-requirements.md describes screens for). Incompatible revisions
     trigger ARTIFACT_REVISION cascade against the dependent artifacts. -->

## New version number

<!-- The new version, e.g., v2. The conductor renames the prior current
     file to /artifacts/versions/<name>.v<previous>.md and writes the new
     content as /artifacts/<name>.md. -->
