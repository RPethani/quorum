/**
 * Types for the live system-flow diagram. Mirrors the master flow
 * captured in `docs-specs/system-flow-stages.md` — six stages
 * (S1–S6), the per-deliberation move sequence inside each, and the
 * orthogonal pause-block conditions.
 *
 * If you add or rename a stage / step / pause condition here, you
 * also update `docs-specs/system-flow-stages.md` in the same commit.
 * That contract lives in `.claude/rules/visual-flow.md`.
 */

export type StageId = "S1" | "S2" | "S3" | "S4" | "S5" | "S6";

export const STAGE_LABEL: Record<StageId, string> = {
  S1: "Initialise",
  S2: "Set up",
  S3: "Draft the plan",
  S4: "Work the artifacts",
  S5: "Wrap up",
  S6: "Archived",
};

export type MoveStep = "propose" | "critique" | "synthesise" | "decide";

export const MOVE_STEP_LABEL: Record<MoveStep, string> = {
  propose: "Propose",
  critique: "Critique",
  synthesise: "Synthesise",
  decide: "Decide",
};

export type StepState = "pending" | "active" | "done" | "skipped" | "failed";

/** Orthogonal pause / block conditions that can fire on any stage from S3 onward. */
export type PauseCondition =
  | "AWAITING_HUMAN"
  | "AGENTS_UNREACHABLE"
  | "AWAITING_PERMISSION"
  | "BLOCKED_ON_ROUTING"
  | "COST_CEILING"
  | "NEEDS_MANIFEST_RATIFICATION";

/** S2 setup checklist item state. */
export type SetupCheck = {
  id: "problem_statement" | "participants" | "context" | "manifest_template";
  label: string;
  state: "pass" | "fail" | "warn" | "info";
  detail?: string;
};

/** A per-deliberation move sequence (used in S3, S4 active doc, S5). */
export type MoveSequence = {
  steps: Record<MoveStep, StepState>;
  /** The handle currently dispatched on the active step, if any. */
  activeHandle: string | null;
  /** "swapped" badge — set when the loop substituted a failing handle. */
  substituted: boolean;
  /** Plain-language status note for the operator. */
  statusNote: string;
};

/** One artifact in the gallery (used in S4). */
export type ArtifactBox = {
  filename: string;
  title: string;
  deliberationId: string | null;
  state: "done" | "active" | "pending" | "abandoned";
};

export type S2Detail = {
  kind: "S2";
  checks: SetupCheck[];
  /** Whether the "Start collaboration" action is enabled. */
  startReady: boolean;
};

export type S3Detail = {
  kind: "S3";
  sequence: MoveSequence;
  pauseConditions: PauseCondition[];
};

export type S4Detail = {
  kind: "S4";
  artifacts: ArtifactBox[];
  /** Sub-flow for the (one or more) currently-active artifacts. */
  activeSequences: Array<{ artifact: ArtifactBox; sequence: MoveSequence }>;
  pauseConditions: PauseCondition[];
  /** Whether the "Wrap up project" action should appear. */
  wrapUpReady: boolean;
};

export type S5Detail = {
  kind: "S5";
  sequence: MoveSequence;
  pauseConditions: PauseCondition[];
};

export type S1Detail = { kind: "S1" };
export type S6Detail = { kind: "S6"; archivedAt: string | null };

export type StageDetail = S1Detail | S2Detail | S3Detail | S4Detail | S5Detail | S6Detail;

/** Aggregate view consumed by `<SystemFlowDiagram>`. */
export type SystemFlowState = {
  /** Which stage the system is currently in. */
  currentStage: StageId;
  /** Per-stage badge: pending / active / done / skipped. */
  stageStates: Record<StageId, StepState>;
  /**
   * Sub-flow detail per stage. The active stage's detail reflects
   * live work; past stages' detail reflects what's been recorded
   * (sequences will show all steps as `done`); future stages'
   * detail is the empty-shell shape so the renderer doesn't have
   * to special-case missing data.
   */
  details: Record<StageId, StageDetail>;
};
