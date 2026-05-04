"use client";

import {
  type CanvasArtifactDetail,
  type CanvasArtifactSummary,
  type CanvasMessage,
  type CanvasState,
  getCanvasArtifact,
  getCanvasMessages,
  getCanvasState,
  listCanvasArtifacts,
} from "@/lib/api/canvas";
import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Hooks for the canvas view.
 *
 * The conductor's existing SSE stream (`/api/stream`) emits a
 * `state_changed` event whenever `state.yaml` mtime changes — and the
 * dispatcher bumps `state.yaml` on every message via
 * `next_message_id`, so we get a free trigger to re-fetch on each turn.
 *
 * The hooks below subscribe once to that stream and re-fetch their
 * resource on every `state_changed` payload. Initial fetch happens on
 * mount.
 */
const SSE_URL = `${
  typeof process !== "undefined" && process.env.NEXT_PUBLIC_QUORUM_API
    ? process.env.NEXT_PUBLIC_QUORUM_API
    : "http://127.0.0.1:8500"
}/api/stream`;

type UnsubscribeFn = () => void;

/**
 * Subscribe to the conductor's SSE stream and call `onTick` whenever
 * the workspace state changes. Returns an unsubscribe function.
 */
function subscribeToTicks(onTick: () => void): UnsubscribeFn {
  if (typeof window === "undefined" || typeof EventSource === "undefined") {
    return () => {};
  }
  const es = new EventSource(SSE_URL);
  const handler = () => onTick();
  // Trigger on every event type the conductor emits — any of them
  // implies "something happened, you may want to re-fetch".
  es.addEventListener("state_changed", handler);
  es.addEventListener("events_appended", handler);
  es.addEventListener("active_changed", handler);
  return () => {
    es.removeEventListener("state_changed", handler);
    es.removeEventListener("events_appended", handler);
    es.removeEventListener("active_changed", handler);
    es.close();
  };
}

// ---------------------------------------------------------------------- //
// useCanvasState
// ---------------------------------------------------------------------- //

export function useCanvasState(): {
  state: CanvasState | null;
  error: string | null;
  reload: () => void;
} {
  const [state, setState] = useState<CanvasState | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setState(await getCanvasState());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void reload();
    const unsub = subscribeToTicks(() => void reload());
    return unsub;
  }, [reload]);

  return { state, error, reload };
}

// ---------------------------------------------------------------------- //
// useCanvasMessages
// ---------------------------------------------------------------------- //

export function useCanvasMessages(): {
  messages: CanvasMessage[];
  error: string | null;
  reload: () => void;
} {
  const [messages, setMessages] = useState<CanvasMessage[]>([]);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const r = await getCanvasMessages();
      setMessages(r.messages);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void reload();
    const unsub = subscribeToTicks(() => void reload());
    return unsub;
  }, [reload]);

  return { messages, error, reload };
}

// ---------------------------------------------------------------------- //
// useCanvasArtifacts (list + currently-open detail)
// ---------------------------------------------------------------------- //

export function useCanvasArtifacts(activeFilename: string | null): {
  artifacts: CanvasArtifactSummary[];
  active: CanvasArtifactDetail | null;
  prevActive: string | null;
  error: string | null;
  reload: () => void;
} {
  const [artifacts, setArtifacts] = useState<CanvasArtifactSummary[]>([]);
  const [active, setActive] = useState<CanvasArtifactDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Track the previous active body so the artifact pane can render a
  // diff overlay on update (D6).
  const prevBodyRef = useRef<string | null>(null);
  const [prevActive, setPrevActive] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const list = await listCanvasArtifacts();
      setArtifacts(list.artifacts);
      if (activeFilename) {
        const detail = await getCanvasArtifact(activeFilename);
        if (prevBodyRef.current !== null && prevBodyRef.current !== detail.body) {
          setPrevActive(prevBodyRef.current);
        }
        prevBodyRef.current = detail.body;
        setActive(detail);
      } else {
        setActive(null);
        prevBodyRef.current = null;
        setPrevActive(null);
      }
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [activeFilename]);

  useEffect(() => {
    void reload();
    const unsub = subscribeToTicks(() => void reload());
    return unsub;
  }, [reload]);

  return { artifacts, active, prevActive, error, reload };
}
