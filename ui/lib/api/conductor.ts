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
