/**
 * Thin client for the conductor's HTTP API (see conductor/src/.../server/http_app.py).
 *
 * Phase 5 ships read endpoints + POST /api/step. Phase 8 adds WebSocket
 * pushes; until then we poll.
 */

const DEFAULT_BASE = "http://127.0.0.1:8500";

function base(): string {
  if (typeof window !== "undefined") {
    const param = new URLSearchParams(window.location.search).get("api");
    if (param) return param;
  }
  return DEFAULT_BASE;
}

export type WorkspaceStateResponse = {
  workspace_id: string;
  mode: "interactive" | "autonomous";
  state: string;
  state_changed_at: string;
  counts: {
    deliberations: number;
    artifacts: number;
    decisions: number;
    tasks: number;
    inbox_pending: number;
  };
  processes: {
    conductor_running: boolean;
    ui_running: boolean;
  };
  cost: {
    spent_usd: number;
    ceiling_usd: number;
    fraction: number;
    invocations: number;
    enforce: boolean;
  };
};

export type DeliberationListItem = {
  id: string;
  title: string;
  status: string;
  tags: string[];
  filename: string;
};

export type DeliberationDetail = DeliberationListItem & {
  markdown: string;
};

export type PlanItemResponse = {
  deliberation_id: string;
  deliberation_title: string;
  role: string;
  move_type: string;
  reason: string;
  is_manual: boolean;
  handle: string;
  layer: string;
  fitness: number | null;
  cost: number | null;
};

export type PlanResponse = {
  items: PlanItemResponse[];
  blocked: Array<{
    deliberation_id: string;
    role: string;
    move_type: string;
    reason: string;
  }>;
  skipped_terminal: string[];
};

export type StepOk = {
  status: "ok";
  handle: string;
  role: string;
  move_type: string;
  deliberation_id: string;
  duration_s: number;
  attempts: number;
  appended: true;
  inboxes_notified: string[];
  error: null;
};

export type StepFailure = {
  status: "validation_failed" | "subprocess_failed" | "timeout";
  handle: string;
  role: string;
  move_type: string;
  deliberation_id: string;
  duration_s: number;
  attempts: number;
  appended: false;
  inboxes_notified: string[];
  error: string;
};

export type StepIdle = {
  status: "idle";
  reason: string;
  plan: PlanResponse;
};

export type StepResponse = StepOk | StepFailure | StepIdle;

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${base()}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`${path} → ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

async function postJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${base()}${path}`, {
    method: "POST",
    cache: "no-store",
  });
  if (!res.ok && res.status !== 402) {
    throw new Error(`${path} → ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export async function getState(): Promise<WorkspaceStateResponse> {
  return getJSON<WorkspaceStateResponse>("/api/state");
}

export async function getDeliberations(): Promise<DeliberationListItem[]> {
  const body = await getJSON<{ deliberations: DeliberationListItem[] }>("/api/deliberations");
  return body.deliberations;
}

export async function getDeliberation(id: string): Promise<DeliberationDetail> {
  return getJSON<DeliberationDetail>(`/api/deliberations/${encodeURIComponent(id)}`);
}

export async function getPlan(): Promise<PlanResponse> {
  return getJSON<PlanResponse>("/api/plan");
}

export async function step(): Promise<StepResponse> {
  return postJSON<StepResponse>("/api/step");
}

// ----- Phase-7 endpoints -------------------------------------------------- //

export type ParticipantRow = {
  handle: string;
  display_name: string;
  model: string;
  transport: "cli" | "manual" | "mcp" | "ide" | string;
  cli_command: string;
  quota_daily: number | null;
  quota_per_deliberation: number | null;
  permission_capability: string;
  account_label: string;
  health: string;
  inherits_fitness_from: string | null;
};

export type ManifestProgress = {
  status: "DRAFTING" | "READY" | "LOCKED";
  total_artifacts: number;
  artifacts_complete: number;
  artifacts_in_production: number;
  artifacts_pending: number;
  quality_gates_clear: boolean;
  closing_ceremony_eligible: boolean;
};

export type ManifestResponse = {
  exists: boolean;
  markdown: string;
  progress: ManifestProgress | null;
};

export type InboxSummary = {
  handle: string;
  filename: string;
  body: string;
  pending_count: number;
};

export type ContextManifest = {
  schema_version: string;
  repos: Array<Record<string, unknown>>;
  docs: Array<Record<string, unknown>>;
  urls: Array<Record<string, unknown>>;
  notes: Array<Record<string, unknown>>;
};

export type EventRecord = Record<string, unknown> & {
  type: string;
  ts?: string;
};

export type EventsResponse = {
  since: number;
  next: number;
  events: EventRecord[];
};

export type WizardPayload = {
  manifest_template?: string | null;
  mode?: "interactive" | "autonomous";
  unavailability_policy?: "strict" | "substitute" | "substitute_aggressively";
  cost_ceiling_usd?: number;
  problem_statement?: string;
};

export async function getParticipants(): Promise<ParticipantRow[]> {
  const body = await getJSON<{ participants: ParticipantRow[] }>("/api/participants");
  return body.participants;
}

export async function getManifest(): Promise<ManifestResponse> {
  return getJSON<ManifestResponse>("/api/manifest");
}

export async function getInboxes(): Promise<InboxSummary[]> {
  const body = await getJSON<{ inboxes: InboxSummary[] }>("/api/inboxes");
  return body.inboxes;
}

export async function getContextManifest(): Promise<ContextManifest> {
  return getJSON<ContextManifest>("/api/context");
}

export async function getEvents(since = 0): Promise<EventsResponse> {
  return getJSON<EventsResponse>(`/api/events?since=${since}`);
}

export type StreamMessage =
  | { type: "events_appended"; payload: EventRecord[] }
  | { type: "active_changed"; payload: { active: string[] } }
  | { type: "state_changed"; payload: WorkspaceStateResponse }
  | { type: "keepalive"; payload: Record<string, never> };

export type StreamHandlers = {
  onEvents?: (events: EventRecord[]) => void;
  onActive?: (active: string[]) => void;
  onState?: (state: WorkspaceStateResponse) => void;
  onError?: (event: Event) => void;
  onOpen?: () => void;
};

/**
 * Subscribe to /api/stream via EventSource. Returns a close function.
 * The conductor pushes 'events_appended', 'active_changed',
 * 'state_changed', and 'keepalive' messages.
 */
export function subscribeStream(handlers: StreamHandlers): () => void {
  if (typeof window === "undefined") {
    return () => {
      // no-op on the server
    };
  }
  const url = `${base()}/api/stream`;
  const source = new EventSource(url);
  source.addEventListener("events_appended", (e) => {
    if (!handlers.onEvents) return;
    try {
      handlers.onEvents(JSON.parse((e as MessageEvent).data));
    } catch {
      // ignore malformed payload
    }
  });
  source.addEventListener("active_changed", (e) => {
    if (!handlers.onActive) return;
    try {
      const payload = JSON.parse((e as MessageEvent).data) as { active: string[] };
      handlers.onActive(payload.active);
    } catch {
      // ignore
    }
  });
  source.addEventListener("state_changed", (e) => {
    if (!handlers.onState) return;
    try {
      handlers.onState(JSON.parse((e as MessageEvent).data));
    } catch {
      // ignore
    }
  });
  source.onopen = () => handlers.onOpen?.();
  source.onerror = (e) => handlers.onError?.(e);
  return () => source.close();
}

export async function applyWizard(payload: WizardPayload): Promise<{ applied: string[] }> {
  const res = await fetch(`${base()}/api/wizard/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`/api/wizard/apply → ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as { applied: string[] };
}

export type SettingsPayload = {
  cost_ceiling_usd?: number;
  cost_enforce?: boolean;
  unavailability_policy?: "strict" | "substitute" | "substitute_aggressively";
  mode?: "interactive" | "autonomous";
};

export type SettingsApplyResponse = {
  applied: string[];
  rejected: Array<{ field: string; reason: string }>;
};

export async function applySettings(payload: SettingsPayload): Promise<SettingsApplyResponse> {
  const res = await fetch(`${base()}/api/settings/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  if (!res.ok && res.status !== 409) {
    throw new Error(`/api/settings/apply → ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as SettingsApplyResponse;
}
