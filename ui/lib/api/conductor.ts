/**
 * Thin client for the conductor's HTTP API (see conductor/src/.../server/http_app.py).
 *
 * Phase 5 ships read endpoints + POST /api/step. Phase 8 adds WebSocket
 * pushes; until then we poll.
 */

const DEFAULT_BASE = "http://127.0.0.1:8500";

// `NEXT_PUBLIC_QUORUM_API` is injected by the conductor when it spawns
// `next dev` via `quorum up` (see services.py), so the UI lands on
// whichever port the server actually bound. The `?api=` query override
// is kept as a debugging escape hatch.
const ENV_BASE = typeof process !== "undefined" ? process.env.NEXT_PUBLIC_QUORUM_API : undefined;

function base(): string {
  if (typeof window !== "undefined") {
    const param = new URLSearchParams(window.location.search).get("api");
    if (param) return param;
  }
  return ENV_BASE || DEFAULT_BASE;
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
  human_pending: number;
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
  const res = await fetchOrFriendlyError(`${base()}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`${path} → ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

async function postJSON<T>(path: string): Promise<T> {
  const res = await fetchOrFriendlyError(`${base()}${path}`, {
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

export type LiveHealth = {
  on_path: boolean | null;
  note: string;
  transport: string;
};

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
  live_health: LiveHealth | null;
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

export type NextAction = {
  id: string;
  title: string;
  description: string;
  kind: "dialog" | "cli" | "info";
  severity: "blocking" | "suggested" | "info";
  payload?: string;
  primary: boolean;
};

export type WizardPayload = {
  manifest_template?: string | null;
  mode?: "interactive" | "autonomous";
  unavailability_policy?: "strict" | "substitute" | "substitute_aggressively";
  cost_ceiling_usd?: number;
  problem_statement?: string;
  human_handle?: string;
};

/**
 * Wraps a fetch call so the UI can show an actionable error message
 * when the conductor's HTTP server isn't running. Browser fetch throws
 * a TypeError with message "Failed to fetch" / "NetworkError when
 * attempting to fetch resource" / "Load failed" depending on the
 * browser; we map those into a single canned message.
 */
async function fetchOrFriendlyError(input: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch (e: unknown) {
    if (e instanceof TypeError && /failed to fetch|networkerror|load failed/i.test(e.message)) {
      throw new Error(
        `Could not reach the conductor at ${input}. Is \`quorum serve\` running? From the workspace folder: run \`quorum serve\` in a separate terminal (default port 8500), then retry.`,
      );
    }
    throw e;
  }
}

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

export async function getNextActions(): Promise<NextAction[]> {
  const body = await getJSON<{ actions: NextAction[] }>("/api/next-actions");
  return body.actions;
}

export type AddAgentPayload = {
  handle: string;
  display_name?: string;
  cli_command?: string;
  model?: string;
  transport?: string;
  permission_capability?: string;
  account_label?: string;
  quota_daily?: number;
  quota_per_deliberation?: number;
};

export async function addContextRepo(payload: {
  path: string;
  name?: string;
  role?: string;
  relevance?: string;
}): Promise<{ name: string }> {
  return contextPost("repos", payload);
}

export async function addContextDoc(payload: {
  path: string;
  name?: string;
}): Promise<{ name: string }> {
  return contextPost("docs", payload);
}

export async function addContextNote(payload: {
  name: string;
  text: string;
}): Promise<{ name: string }> {
  return contextPost("notes", payload);
}

export async function addContextUrl(payload: {
  url: string;
  name?: string;
  role?: string;
}): Promise<{ name: string }> {
  return contextPost("urls", payload);
}

export type DigestionState = {
  name: string;
  relevance: string;
  proposed_digester: string | null;
  chosen_digester: string | null;
  status: "idle" | "queued" | "running" | "ok" | "failed";
  started_at: string | null;
  completed_at: string | null;
  duration_s: number | null;
  error: string | null;
  digest_exists: boolean;
  last_digested_at: string | null;
  kind: "repo" | "doc";
};

export async function getDigestions(): Promise<DigestionState[]> {
  const body = await getJSON<{ repos: DigestionState[] }>("/api/context/digestions");
  return body.repos;
}

export async function queueDigest(
  name: string,
  digester?: string,
  kind: "repo" | "doc" = "repo",
): Promise<DigestionState> {
  const res = await fetchOrFriendlyError(`${base()}/api/context/digest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, kind, ...(digester ? { digester } : {}) }),
    cache: "no-store",
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { error?: string };
    throw new Error(body.error || `Queue digest failed: ${res.status}`);
  }
  return (await res.json()) as DigestionState;
}

export async function refreshUrl(name: string): Promise<{ refreshed: string }> {
  const res = await fetchOrFriendlyError(`${base()}/api/context/urls/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
    cache: "no-store",
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { error?: string };
    throw new Error(body.error || `Refresh failed: ${res.status}`);
  }
  return (await res.json()) as { refreshed: string };
}

export type FsEntry = { name: string; path: string; is_dir: boolean };
export type FsListing = {
  path: string;
  parent: string | null;
  home: string;
  entries: FsEntry[];
};

export async function listFs(
  path: string | null,
  mode: "dirs" | "files" = "dirs",
): Promise<FsListing> {
  const params = new URLSearchParams();
  if (path) params.set("path", path);
  params.set("mode", mode);
  return getJSON<FsListing>(`/api/fs/list?${params.toString()}`);
}

async function contextPost(
  kind: "repos" | "docs" | "notes" | "urls",
  payload: Record<string, unknown>,
): Promise<{ name: string }> {
  const res = await fetchOrFriendlyError(`${base()}/api/context/${kind}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { error?: string };
    throw new Error(body.error || `Add ${kind.slice(0, -1)} failed: ${res.status}`);
  }
  return (await res.json()) as { name: string };
}

export async function addAgent(payload: AddAgentPayload): Promise<{ handle: string }> {
  const res = await fetchOrFriendlyError(`${base()}/api/participants`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { error?: string };
    throw new Error(body.error || `Add agent failed: ${res.status}`);
  }
  return (await res.json()) as { handle: string };
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
  const res = await fetchOrFriendlyError(`${base()}/api/wizard/apply`, {
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

// ----- Phase-10 endpoints -------------------------------------------------- //

export type RawListing = {
  files: { path: string; exists: boolean; size_bytes: number }[];
};
export type RawFile = { path: string; content: string };

export type AppendMovePayload = {
  deliberation_id: string;
  move_type: string;
  author?: string;
  targets?: string | null;
  sections: Record<string, string>;
};

export type AppendMoveResponse = {
  appended: boolean;
  move_type: string;
  deliberation_id: string;
  inboxes_notified: string[];
};

export async function getRawListing(): Promise<RawListing> {
  return getJSON<RawListing>("/api/raw");
}

export async function getRawFile(path: string): Promise<RawFile> {
  return getJSON<RawFile>(`/api/raw/${path}`);
}

export async function saveRawFile(path: string, content: string): Promise<void> {
  const res = await fetch(`${base()}/api/raw/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`/api/raw/${path} → ${res.status} ${res.statusText}`);
  }
}

export async function appendMove(payload: AppendMovePayload): Promise<AppendMoveResponse> {
  const res = await fetch(`${base()}/api/moves`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  const body = (await res.json()) as AppendMoveResponse | { error: string };
  if (!res.ok) {
    const errMsg = "error" in body ? body.error : "";
    throw new Error(`/api/moves → ${res.status} ${res.statusText}: ${errMsg}`);
  }
  return body as AppendMoveResponse;
}
