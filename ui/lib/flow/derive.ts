/**
 * Pure derivation: API responses → SystemFlowState.
 *
 * No fetching here, no React. Inputs are the existing responses we
 * already use in the UI; this just composes them into the shape the
 * diagram renders. Easy to unit-test (when we add tests).
 *
 * Keep this file aligned with `docs-specs/system-flow-stages.md`.
 * The stage-resolution rules below mirror the locked master flow.
 */

import type {
  Ask,
  DeliberationListItem,
  EventRecord,
  ManifestResponse,
  ParticipantRow,
  PlanResponse,
  WorkspaceStateResponse,
} from "@/lib/api/conductor";
import type {
  ArtifactBox,
  MoveSequence,
  MoveStep,
  PauseCondition,
  StageDetail,
  StageId,
  StepState,
  SystemFlowState,
} from "./types";

export type DeriveInput = {
  state: WorkspaceStateResponse | null;
  manifest: ManifestResponse | null;
  deliberations: DeliberationListItem[];
  participants: ParticipantRow[];
  asks: Ask[];
  plan: PlanResponse | null;
  events: EventRecord[];
};

const TERMINAL_STATUSES = new Set(["DECIDED", "ABANDONED", "ARCHIVED"]);

export function deriveSystemFlowState(input: DeriveInput): SystemFlowState {
  const stage = resolveStage(input);
  const stageStates = computeStageStates(stage, input);
  const stageOrder: StageId[] = ["S1", "S2", "S3", "S4", "S5", "S6"];
  const details = stageOrder.reduce(
    (acc, s) => {
      acc[s] = buildDetail(s, input);
      return acc;
    },
    {} as Record<StageId, StageDetail>,
  );
  return { currentStage: stage, stageStates, details };
}

// ---------------------------------------------------------------------- //
// Stage resolution
// ---------------------------------------------------------------------- //

function resolveStage(input: DeriveInput): StageId {
  const ws = input.state;
  if (!ws) return "S1";

  if (ws.state === "ARCHIVED") return "S6";
  if (ws.state === "COMPLETED" || ws.state === "COMPLETED_AUTONOMOUS") {
    // Closing happened. Until the user archives, surface S5 (closing
    // ceremony) so the result is visible. Once archived, S6.
    return "S5";
  }

  const seedDelib = input.deliberations.find((d) => d.id === "0001");
  const manifestStatus = (input.manifest?.progress?.status ?? "DRAFTING").toUpperCase();

  // S1 / S2: pre-collaboration, workspace not yet active.
  if (ws.state === "INITIALIZED") {
    return "S2"; // S1 is too transient to render meaningfully.
  }

  // ACTIVE / PAUSED / READY
  if (!seedDelib || !TERMINAL_STATUSES.has(seedDelib.status.toUpperCase())) {
    return "S3";
  }
  // Seed terminal but manifest somehow not LOCKED → still S3 (recovery state).
  if (manifestStatus !== "LOCKED") return "S3";

  // Manifest locked → working artifacts unless all artifact deliberations are terminal.
  const artifactDelibs = input.deliberations.filter((d) => d.id !== "0001");
  const nonTerminal = artifactDelibs.filter((d) => !TERMINAL_STATUSES.has(d.status.toUpperCase()));

  // The lie we used to tell here: when every artifact is DECIDED, return S4
  // anyway — the badge then animates a spinner suggesting work in progress
  // while the system is in fact parked, waiting for the human to start the
  // wrap-up deliberation. The truth: S4 is done; the cursor is at S5
  // awaiting the closing ceremony. computeStageStates flips S4 to "done"
  // (green check) and S5 to "active" automatically once we report S5 here.
  if (nonTerminal.length === 0 && artifactDelibs.length > 0) {
    return "S5";
  }

  return "S4";
}

// ---------------------------------------------------------------------- //
// Per-stage badge states
// ---------------------------------------------------------------------- //

function computeStageStates(current: StageId, input: DeriveInput): Record<StageId, StepState> {
  const order: StageId[] = ["S1", "S2", "S3", "S4", "S5", "S6"];
  const idx = order.indexOf(current);
  const out: Record<StageId, StepState> = {
    S1: "pending",
    S2: "pending",
    S3: "pending",
    S4: "pending",
    S5: "pending",
    S6: "pending",
  };
  for (let i = 0; i < order.length; i++) {
    if (i < idx) out[order[i]] = "done";
    else if (i === idx) out[order[i]] = "active";
    else out[order[i]] = "pending";
  }
  // S5 is optional; if we're past S4 with all artifacts terminal but no
  // closing has started, leave S5 as "pending" not "skipped" — the user
  // hasn't decided to skip yet.
  // S6 always pending unless we're in it.

  // Pause status: if state is PAUSED on S3/S4/S5, mark current stage as failed-tinted.
  if (input.state?.state === "PAUSED" && ["S3", "S4", "S5"].includes(current)) {
    out[current] = "failed";
  }
  return out;
}

// ---------------------------------------------------------------------- //
// Stage detail builders
// ---------------------------------------------------------------------- //

function buildDetail(stage: StageId, input: DeriveInput): StageDetail {
  switch (stage) {
    case "S1":
      return { kind: "S1" };
    case "S2":
      return buildS2Detail(input);
    case "S3":
      return buildS3Detail(input);
    case "S4":
      return buildS4Detail(input);
    case "S5":
      return buildS5Detail(input);
    case "S6":
      return buildS6Detail(input);
  }
}

function buildS2Detail(input: DeliveInputS2): StageDetail {
  const cliCount = input.participants.filter((p) => p.transport === "cli").length;
  const cliReachable = input.participants.filter(
    (p) => p.transport === "cli" && p.live_health?.on_path === true,
  ).length;
  const psState: SetupCheckState =
    input.state?.counts?.deliberations !== undefined && hasProblemStatement(input)
      ? "pass"
      : "fail";
  const partsState: SetupCheckState =
    cliCount === 0 ? "fail" : cliReachable === cliCount ? "pass" : "warn";

  const checks: import("./types").SetupCheck[] = [
    {
      id: "problem_statement",
      label: "Problem statement",
      state: psState,
      detail: psState === "pass" ? "Filled in" : "Empty — write one in Setup",
    },
    {
      id: "participants",
      label: "Participants",
      state: partsState,
      detail: cliCount === 0 ? "No AI participants yet" : `${cliReachable}/${cliCount} reachable`,
    },
    {
      id: "context",
      label: "Context",
      state: "info",
      detail: "Optional",
    },
  ];

  const startReady = psState === "pass" && cliCount >= 1;

  return { kind: "S2", checks, startReady };
}

type DeliveInputS2 = DeriveInput;
type SetupCheckState = "pass" | "fail" | "warn" | "info";

function hasProblemStatement(input: DeriveInput): boolean {
  // We don't have a /api/problem-statement endpoint; the heuristic is "the
  // workspace state is past INITIALIZED" or "any deliberation exists." Both
  // signals strongly imply the problem statement was filled in via the
  // wizard. For S2 in INITIALIZED state we err on "fail" until we know.
  if (input.state && input.state.state !== "INITIALIZED") return true;
  if ((input.state?.counts?.deliberations ?? 0) > 0) return true;
  return false;
}

function buildS3Detail(input: DeriveInput): StageDetail {
  const seed = input.deliberations.find((d) => d.id === "0001");
  const sequence = buildSequenceForDeliberation(seed?.id ?? null, input);
  return {
    kind: "S3",
    sequence,
    pauseConditions: detectPauseConditions(input, seed?.id ?? null),
  };
}

function buildS4Detail(input: DeriveInput): StageDetail {
  // Derive ordered artifact list from the manifest body. We don't have a
  // dedicated /api/artifacts endpoint; instead we read the deliberations
  // that have a corresponding artifact-named title (the auto-advance
  // deliberation creator names the deliberation by the artifact). The
  // backend keeps these aligned via auto_advance.py.
  const artifactDelibs = input.deliberations
    .filter((d) => d.id !== "0001")
    .sort((a, b) => Number.parseInt(a.id) - Number.parseInt(b.id));
  const artifacts: ArtifactBox[] = artifactDelibs.map((d) => {
    const status = d.status.toUpperCase();
    let state: ArtifactBox["state"] = "pending";
    if (status === "DECIDED" || status === "ARCHIVED") state = "done";
    else if (status === "ABANDONED") state = "abandoned";
    else state = "active";
    return {
      filename: extractArtifactFilename(d) ?? `${d.id}.md`,
      title: d.title || `Artifact ${d.id}`,
      deliberationId: d.id,
      state,
    };
  });

  const activeArtifacts = artifacts.filter((a) => a.state === "active");
  const activeSequences = activeArtifacts.map((a) => ({
    artifact: a,
    sequence: buildSequenceForDeliberation(a.deliberationId, input),
  }));

  const allTerminal =
    artifacts.length > 0 && artifacts.every((a) => a.state === "done" || a.state === "abandoned");

  return {
    kind: "S4",
    artifacts,
    activeSequences,
    pauseConditions: detectPauseConditions(input, activeArtifacts[0]?.deliberationId ?? null),
    wrapUpReady: allTerminal,
  };
}

function buildS5Detail(input: DeriveInput): StageDetail {
  // Closing deliberation: not yet implemented. For now we treat S5 as
  // "the closing slot exists; show a placeholder sequence." When the
  // S5 work lands this will read the actual closing deliberation.
  const placeholder: MoveSequence = {
    steps: { propose: "pending", critique: "pending", synthesise: "pending", decide: "pending" },
    activeHandle: null,
    substituted: false,
    statusNote: "Closing not yet started.",
  };
  return { kind: "S5", sequence: placeholder, pauseConditions: [] };
}

function buildS6Detail(input: DeriveInput): StageDetail {
  return { kind: "S6", archivedAt: input.state?.state_changed_at ?? null };
}

// ---------------------------------------------------------------------- //
// Move-sequence + pause detection
// ---------------------------------------------------------------------- //

function buildSequenceForDeliberation(
  deliberationId: string | null,
  input: DeriveInput,
): MoveSequence {
  const empty: MoveSequence = {
    steps: { propose: "pending", critique: "pending", synthesise: "pending", decide: "pending" },
    activeHandle: null,
    substituted: false,
    statusNote: "Waiting to start.",
  };
  if (!deliberationId) return empty;

  const planItem = input.plan?.items.find((i) => i.deliberation_id === deliberationId);
  const ask = input.asks.find(
    (a) => a.source_deliberation === deliberationId && a.status === "open",
  );

  // Determine which moves have already landed on this deliberation by
  // walking the recent events log (`move_appended`).
  const moveTypes = collectAppendedMoveTypes(deliberationId, input.events);

  const steps: Record<MoveStep, StepState> = {
    propose: moveTypes.has("PROPOSAL") ? "done" : "pending",
    critique: moveTypes.has("CRITIQUE") ? "done" : "pending",
    synthesise: moveTypes.has("SYNTHESIS") ? "done" : "pending",
    decide: moveTypes.has("DECISION") || moveTypes.has("OVERRIDE") ? "done" : "pending",
  };

  // The active step is whatever the planner says is next (if any), or — if
  // there's an open Ask — the decide step.
  let activeHandle: string | null = null;
  let statusNote = "Waiting on the next step.";
  let substituted = false;

  if (ask) {
    steps.decide = "active";
    statusNote = "Your turn — answer the question above.";
  } else if (planItem) {
    const stepKey = planItemMoveTypeToStep(planItem.move_type);
    if (stepKey) {
      steps[stepKey] = "active";
      activeHandle = planItem.handle;
      statusNote = `${shortName(planItem.handle)} is ${verbForStep(stepKey)}.`;
      substituted = wasSubstituted(input, deliberationId, planItem.handle, planItem.move_type);
    } else {
      statusNote = "Working.";
    }
  }

  return { steps, activeHandle, substituted, statusNote };
}

function planItemMoveTypeToStep(moveType: string): MoveStep | null {
  switch (moveType) {
    case "PROPOSAL":
      return "propose";
    case "CRITIQUE":
      return "critique";
    case "SYNTHESIS":
      return "synthesise";
    case "DECISION":
    case "OVERRIDE":
      return "decide";
    default:
      return null;
  }
}

function verbForStep(step: MoveStep): string {
  switch (step) {
    case "propose":
      return "drafting an initial take";
    case "critique":
      return "pushing back";
    case "synthesise":
      return "reconciling the discussion";
    case "decide":
      return "deciding";
  }
}

function shortName(handle: string): string {
  if (!handle) return "Someone";
  const map: Record<string, string> = {
    "@claude-opus": "Claude (Opus)",
    "@claude": "Claude",
    "@gemini": "Gemini",
    "@codex": "Codex",
    "@rakesh": "You",
  };
  return map[handle] ?? handle.replace(/^@/, "");
}

function collectAppendedMoveTypes(deliberationId: string, events: EventRecord[]): Set<string> {
  const out = new Set<string>();
  for (const e of events) {
    if (e.type !== "move_appended") continue;
    if ((e.deliberation_id as string | undefined) !== deliberationId) continue;
    const mt = e.move_type as string | undefined;
    if (mt) out.add(mt);
  }
  return out;
}

function wasSubstituted(
  input: DeriveInput,
  deliberationId: string,
  currentHandle: string,
  moveType: string,
): boolean {
  // Substitution = the planner is dispatching `currentHandle` for this
  // (deliberation, move_type) but the events log shows another handle
  // failed on the same key recently.
  for (let i = input.events.length - 1; i >= 0; i--) {
    const e = input.events[i];
    if (!e || e.type !== "agent_failed") continue;
    if ((e.deliberation_id as string | undefined) !== deliberationId) continue;
    if ((e.move_type as string | undefined) !== moveType) continue;
    const failedHandle = e.handle as string | undefined;
    if (failedHandle && failedHandle !== currentHandle) return true;
  }
  return false;
}

function detectPauseConditions(
  input: DeriveInput,
  activeDeliberationId: string | null,
): PauseCondition[] {
  const out: PauseCondition[] = [];
  if (input.asks.some((a) => a.status === "open")) out.push("AWAITING_HUMAN");
  if (input.state?.state === "PAUSED") out.push("AGENTS_UNREACHABLE");
  // Cost ceiling reached
  const cost = input.state?.cost;
  if (cost?.enforce && cost.fraction >= 1) out.push("COST_CEILING");
  // Per-deliberation routing block — would surface as a deliberation
  // status of BLOCKED_ON_ROUTING; we can't read that from the list endpoint
  // alone, so this stays partially-detected for now.
  if (activeDeliberationId) {
    const d = input.deliberations.find((x) => x.id === activeDeliberationId);
    if (d?.status.toUpperCase().startsWith("BLOCKED_ON_ROUTING")) {
      out.push("BLOCKED_ON_ROUTING");
    }
  }
  return out;
}

function extractArtifactFilename(d: DeliberationListItem): string | null {
  // The auto-advance deliberations are titled "Produce <name>"; we can derive
  // the filename from the title. Not 100% reliable; future versions will
  // surface ratifies: directly via /api/deliberations.
  const m = d.title.match(/Produce\s+(.+)/i);
  if (!m) return null;
  return `${m[1].toLowerCase().trim().replace(/\s+/g, "-")}.md`;
}
