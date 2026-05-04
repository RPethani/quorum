/**
 * Typed HTTP client for the canvas API surface (S4 in
 * `docs-specs/canvas-redesign.md`).
 *
 * Mounted under `/api/canvas/*` alongside the protocol-era endpoints.
 * The two surfaces coexist during migration; the new UI consumes only
 * this module.
 */

const DEFAULT_BASE = "http://127.0.0.1:8500";

const ENV_BASE = typeof process !== "undefined" ? process.env.NEXT_PUBLIC_QUORUM_API : undefined;

function base(): string {
  return ENV_BASE && ENV_BASE.length > 0 ? ENV_BASE : DEFAULT_BASE;
}

// ---------------------------------------------------------------------- //
// Types
// ---------------------------------------------------------------------- //

export type CanvasState = {
  title: string;
  created_at: string;
  message_counter: number;
  cost: { spent: number; cap: number; enforce: boolean };
  digester_handle: string;
  schema_version: number;
};

export type CanvasMessage = {
  id: string;
  author: string;
  ts: string;
  body: string;
};

export type CanvasMessagesResponse = {
  messages: CanvasMessage[];
};

export type CanvasArtifactSummary = {
  filename: string;
  size: number;
  modified_at: string;
};

export type CanvasArtifactDetail = CanvasArtifactSummary & {
  body: string;
};

export type CanvasArtifactsResponse = {
  artifacts: CanvasArtifactSummary[];
};

export type CanvasTurn = {
  handle: string;
  message: CanvasMessage | null;
  artifacts: { filename: string; archived: string | null }[];
  error: string | null;
};

export type CanvasDispatchResponse = {
  user_message: CanvasMessage;
  turns: CanvasTurn[];
};

// ---------------------------------------------------------------------- //
// HTTP helpers (kept tiny — no shared dependency on conductor.ts so the
// canvas surface is self-contained).
// ---------------------------------------------------------------------- //

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${base()}${path}`, { cache: "no-store" });
  if (!res.ok) throw new CanvasApiError(res.status, await res.text());
  return res.json() as Promise<T>;
}

async function postJSON<T>(path: string, body: unknown = {}): Promise<T> {
  const res = await fetch(`${base()}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new CanvasApiError(res.status, await res.text());
  return res.json() as Promise<T>;
}

async function patchJSON<T>(path: string, body: unknown = {}): Promise<T> {
  const res = await fetch(`${base()}${path}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new CanvasApiError(res.status, await res.text());
  return res.json() as Promise<T>;
}

async function delJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${base()}${path}`, { method: "DELETE" });
  if (!res.ok) throw new CanvasApiError(res.status, await res.text());
  return res.json() as Promise<T>;
}

export class CanvasApiError extends Error {
  status: number;
  raw: string;
  constructor(status: number, raw: string) {
    super(`canvas API ${status}: ${raw.slice(0, 200)}`);
    this.status = status;
    this.raw = raw;
  }
}

// ---------------------------------------------------------------------- //
// Endpoints
// ---------------------------------------------------------------------- //

export function getCanvasState(): Promise<CanvasState> {
  return getJSON<CanvasState>("/api/canvas/state");
}

export function updateCanvasState(patch: {
  title?: string;
  digester_handle?: string;
}): Promise<CanvasState> {
  return patchJSON<CanvasState>("/api/canvas/state", patch);
}

export function getCanvasMessages(): Promise<CanvasMessagesResponse> {
  return getJSON<CanvasMessagesResponse>("/api/canvas/messages");
}

export function sendCanvasMessage(body: string, author?: string): Promise<CanvasDispatchResponse> {
  return postJSON<CanvasDispatchResponse>("/api/canvas/messages", {
    body,
    ...(author ? { author } : {}),
  });
}

export function retryCanvasMessage(messageId: string): Promise<CanvasDispatchResponse> {
  return postJSON<CanvasDispatchResponse>(
    `/api/canvas/messages/${encodeURIComponent(messageId)}/retry`,
    {},
  );
}

export function listCanvasArtifacts(): Promise<CanvasArtifactsResponse> {
  return getJSON<CanvasArtifactsResponse>("/api/canvas/artifacts");
}

export function getCanvasArtifact(filename: string): Promise<CanvasArtifactDetail> {
  return getJSON<CanvasArtifactDetail>(`/api/canvas/artifacts/${encodeURIComponent(filename)}`);
}

export function deleteCanvasArtifact(
  filename: string,
): Promise<{ filename: string; archived: string }> {
  return delJSON(`/api/canvas/artifacts/${encodeURIComponent(filename)}`);
}

// ---------------------------------------------------------------------- //
// Context entries
// ---------------------------------------------------------------------- //

export type CanvasContextEntry = {
  id: string;
  kind: "repo" | "doc" | "note";
  name: string;
  added_at: string;
  source: string;
  digest_status: "" | "pending" | "running" | "ready" | "failed";
  digest_summary: string;
  digest_error: string;
  digest_at: string | null;
  source_git_ref: string;
  stale: boolean;
  body: string;
};

export type CanvasContextListResponse = { entries: CanvasContextEntry[] };

export function listCanvasContext(): Promise<CanvasContextListResponse> {
  return getJSON<CanvasContextListResponse>("/api/canvas/context");
}

export function addCanvasRepo(
  source: string,
  name?: string,
): Promise<{ entry: CanvasContextEntry }> {
  return postJSON("/api/canvas/context", { kind: "repo", source, ...(name ? { name } : {}) });
}

export function addCanvasDoc(
  source: string,
  name?: string,
): Promise<{ entry: CanvasContextEntry }> {
  return postJSON("/api/canvas/context", { kind: "doc", source, ...(name ? { name } : {}) });
}

export function addCanvasNote(name: string, body: string): Promise<{ entry: CanvasContextEntry }> {
  return postJSON("/api/canvas/context", { kind: "note", name, body });
}

export function removeCanvasContext(id: string): Promise<{ removed: CanvasContextEntry }> {
  return delJSON(`/api/canvas/context/${encodeURIComponent(id)}`);
}

export function refreshCanvasContext(id: string): Promise<{ entry: CanvasContextEntry }> {
  return postJSON(`/api/canvas/context/${encodeURIComponent(id)}/refresh`, {});
}

export function digestCanvasContext(
  id: string,
  handle?: string,
): Promise<{ entry: CanvasContextEntry }> {
  return postJSON(`/api/canvas/context/${encodeURIComponent(id)}/digest`, handle ? { handle } : {});
}

// ---------------------------------------------------------------------- //
// Remediations
// ---------------------------------------------------------------------- //

export type CanvasRemediation = {
  id: string;
  title: string;
  description: string;
  handle: string;
};

export function applyCanvasRemediation(
  id: string,
  handle: string,
): Promise<{ applied: string; summary: string }> {
  return postJSON("/api/canvas/remediations/apply", { id, handle });
}

/**
 * Parse a remediation marker out of a message body, returning both
 * the visible body (with the marker stripped) and the structured
 * remediation. The dispatcher embeds the marker as a single-line
 * HTML comment: `<!-- remediation: {"id":"...","handle":"@x",...} -->`.
 */
export function parseRemediation(body: string): {
  visible: string;
  remediation: CanvasRemediation | null;
} {
  const re = /<!--\s*remediation:\s*(\{.*?\})\s*-->/;
  const match = body.match(re);
  if (!match) return { visible: body, remediation: null };
  try {
    const obj = JSON.parse(match[1]);
    if (
      typeof obj?.id === "string" &&
      typeof obj?.handle === "string" &&
      typeof obj?.title === "string" &&
      typeof obj?.description === "string"
    ) {
      return {
        visible: body.replace(re, "").trimEnd(),
        remediation: obj as CanvasRemediation,
      };
    }
  } catch {
    /* fall through */
  }
  return { visible: body, remediation: null };
}
