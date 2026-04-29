"use client";

import { ThemeToggle } from "@/components/design-system/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ActivityFeed } from "@/components/workspace/activity-feed";
import { DeliberationsList } from "@/components/workspace/deliberations-list";
import { ManifestProgressBar } from "@/components/workspace/manifest-progress";
import { ParticipantsList } from "@/components/workspace/participants-list";
import {
  type DeliberationDetail,
  type DeliberationListItem,
  type EventRecord,
  type InboxSummary,
  type ManifestResponse,
  type ParticipantRow,
  type WorkspaceStateResponse,
  getDeliberation,
  getDeliberations,
  getEvents,
  getInboxes,
  getManifest,
  getParticipants,
  getState,
  subscribeStream,
} from "@/lib/api/conductor";
import { ChevronRight, Loader2, RotateCw } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

/**
 * Phase-7 three-pane workspace shell. Polling-based; live WebSocket
 * pushes arrive in Phase 8.
 *
 *   Left pane   Deliberations list (click to select)
 *   Middle      Selected deliberation rendered as <pre> Markdown +
 *               manifest progress bar + workspace header
 *   Right       Activity feed (top), participants list (bottom)
 *
 * Pre-requisite: `quorum serve` running on localhost:8500. Override
 * with `?api=http://host:port` in the URL.
 */
export default function WorkspacePage() {
  const [state, setState] = useState<WorkspaceStateResponse | null>(null);
  const [manifest, setManifest] = useState<ManifestResponse | null>(null);
  const [list, setList] = useState<DeliberationListItem[]>([]);
  const [participants, setParticipants] = useState<ParticipantRow[]>([]);
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [inboxes, setInboxes] = useState<InboxSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [active, setActive] = useState<DeliberationDetail | null>(null);
  const [activeMarkers, setActiveMarkers] = useState<string[]>([]);
  const [streamConnected, setStreamConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, m, ds, ps, ev, ib] = await Promise.all([
        getState(),
        getManifest(),
        getDeliberations(),
        getParticipants(),
        getEvents(0),
        getInboxes(),
      ]);
      setState(s);
      setManifest(m);
      setList(ds);
      setParticipants(ps);
      setEvents(ev.events);
      setInboxes(ib);
      const next = selectedId ?? ds[0]?.id ?? null;
      if (next !== selectedId) setSelectedId(next);
      if (next) {
        try {
          setActive(await getDeliberation(next));
        } catch {
          setActive(null);
        }
      } else {
        setActive(null);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [selectedId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Phase-8 SSE subscription. EventSource keeps the connection alive
  // and pushes events_appended / active_changed / state_changed
  // messages; we patch local state in place. A polling fallback every
  // 30s recovers from a dropped connection without a UI refresh.
  useEffect(() => {
    let inboxesTimer: ReturnType<typeof setInterval> | null = null;
    const close = subscribeStream({
      onOpen: () => setStreamConnected(true),
      onError: () => setStreamConnected(false),
      onEvents: (incoming) => {
        setEvents((prev) => [...prev, ...incoming]);
        // Refresh derived data that's not on the stream yet.
        void getDeliberations().then(setList);
        void getInboxes().then(setInboxes);
      },
      onActive: (markers) => setActiveMarkers(markers),
      onState: (s) => setState(s),
    });
    inboxesTimer = setInterval(() => {
      void getInboxes().then(setInboxes);
    }, 30_000);
    return () => {
      close();
      if (inboxesTimer) clearInterval(inboxesTimer);
    };
  }, []);

  useEffect(() => {
    if (selectedId) {
      void getDeliberation(selectedId)
        .then(setActive)
        .catch(() => setActive(null));
    } else {
      setActive(null);
    }
  }, [selectedId]);

  const yourTurn = useMemo(
    () =>
      inboxes.find((ib) => ib.handle.toLowerCase().includes("human") && ib.pending_count > 0) ??
      null,
    [inboxes],
  );

  return (
    <div className="flex h-screen flex-col bg-canvas text-fg-primary">
      <Header
        state={state}
        loading={loading}
        onRefresh={refresh}
        yourTurnPending={yourTurn?.pending_count ?? 0}
        activeCount={activeMarkers.length}
        streamConnected={streamConnected}
      />
      {error ? (
        <div className="border-b border-accent-danger bg-accent-danger-weak px-6 py-2 text-sm text-accent-danger">
          API error. {error}. Make sure <code className="font-mono">quorum serve</code> is running.
        </div>
      ) : null}
      <div className="flex flex-1 min-h-0">
        <aside className="w-[280px] shrink-0 border-r border-border-default bg-recessed flex flex-col">
          <div className="px-4 py-3 border-b border-border-default">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-fg-tertiary">
              Deliberations
            </h2>
          </div>
          <div className="flex-1 overflow-y-auto">
            <DeliberationsList items={list} selectedId={selectedId} onSelect={setSelectedId} />
          </div>
          <div className="border-t border-border-default p-4">
            <ManifestProgressBar progress={manifest?.progress ?? null} />
          </div>
        </aside>

        <main className="flex-1 min-w-0 overflow-y-auto">
          {active ? (
            <article className="mx-auto max-w-3xl px-6 py-6">
              <div className="mb-3 flex items-center justify-between gap-2">
                <h1 className="text-xl font-semibold">
                  <span className="font-mono text-fg-tertiary">#{active.id}</span> {active.title}
                </h1>
                <Badge variant={badgeForState(active.status)}>{active.status}</Badge>
              </div>
              <Separator />
              <pre className="mt-4 overflow-x-auto whitespace-pre-wrap rounded-md border border-border-default bg-recessed p-4 font-mono text-xs leading-relaxed">
                {active.markdown}
              </pre>
            </article>
          ) : (
            <div className="flex h-full flex-col items-center justify-center px-6 text-center">
              <p className="text-sm text-fg-tertiary">
                {list.length
                  ? "Select a deliberation from the left."
                  : "No deliberations yet. The seed is opened automatically when you run “quorum step” or “quorum start”."}
              </p>
            </div>
          )}
        </main>

        <aside className="w-[360px] shrink-0 border-l border-border-default flex flex-col">
          <div className="px-4 py-3 border-b border-border-default flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-fg-tertiary">
              Activity
            </h2>
            <span className="font-mono text-xs text-fg-tertiary">{events.length} events</span>
          </div>
          <div className="flex-1 overflow-y-auto">
            <ActivityFeed events={events} />
          </div>
          <div className="border-t border-border-default py-3">
            <h2 className="px-4 mb-2 text-xs font-semibold uppercase tracking-wider text-fg-tertiary">
              Participants
            </h2>
            <ParticipantsList participants={participants} />
          </div>
        </aside>
      </div>
    </div>
  );
}

function Header({
  state,
  loading,
  onRefresh,
  yourTurnPending,
  activeCount,
  streamConnected,
}: {
  state: WorkspaceStateResponse | null;
  loading: boolean;
  onRefresh: () => void;
  yourTurnPending: number;
  activeCount: number;
  streamConnected: boolean;
}) {
  const costPct = state ? Math.round((state.cost.fraction || 0) * 100) : 0;
  return (
    <header className="flex items-center justify-between gap-4 border-b border-border-default bg-elevated px-6 py-3">
      <div className="flex items-center gap-3 min-w-0">
        <Link
          href="/"
          className="font-semibold tracking-tight hover:text-accent-primary transition-colors"
        >
          Quorum
        </Link>
        <ChevronRight size={14} className="text-fg-tertiary" strokeWidth={1.5} />
        <span className="font-mono text-sm text-fg-secondary truncate">
          {state ? state.workspace_id.slice(0, 12) : "…"}
        </span>
        {state ? <Badge variant={badgeForState(state.state)}>{state.state}</Badge> : null}
        {state ? (
          <span
            className={`font-mono text-xs ${
              costPct > 80 ? "text-accent-warning" : "text-fg-tertiary"
            }`}
          >
            ${state.cost.spent_usd.toFixed(2)} / ${state.cost.ceiling_usd.toFixed(2)} ({costPct}%)
          </span>
        ) : null}
        {activeCount > 0 ? (
          <Badge variant="primary" className="composing-pulse">
            {activeCount} composing
          </Badge>
        ) : null}
      </div>
      <div className="flex items-center gap-2">
        <span
          className="font-mono text-xs text-fg-tertiary"
          title={streamConnected ? "Live: SSE connected" : "Polling fallback"}
        >
          {streamConnected ? "● live" : "○ polling"}
        </span>
        {yourTurnPending > 0 ? (
          <Badge variant="warning">{yourTurnPending} pending for you</Badge>
        ) : null}
        <Button variant="outline" size="sm" onClick={onRefresh} disabled={loading}>
          {loading ? <Loader2 size={14} className="animate-spin" /> : <RotateCw size={14} />}
          Refresh
        </Button>
        <ThemeToggle />
      </div>
    </header>
  );
}

function badgeForState(state: string): "neutral" | "primary" | "success" | "warning" | "danger" {
  if (state === "DECIDED" || state === "COMPLETED") return "success";
  if (state.startsWith("BLOCKED") || state === "PAUSED") return "warning";
  if (state === "ARCHIVED" || state === "ABANDONED") return "danger";
  if (state === "ACTIVE" || state === "OPEN" || state === "IN_REVIEW") return "primary";
  return "neutral";
}
