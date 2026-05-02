"use client";

import { ThemeToggle } from "@/components/design-system/theme-toggle";
import { AddAgentDialog } from "@/components/dialogs/add-agent-dialog";
import { ContextDialog } from "@/components/dialogs/context-dialog";
import { DigestionDialog } from "@/components/dialogs/digestion-dialog";
import { NewDeliberationDialog } from "@/components/dialogs/new-deliberation-dialog";
import { PermissionsDialog } from "@/components/dialogs/permissions-dialog";
import { RawEditorDialog } from "@/components/dialogs/raw-editor-dialog";
import { SettingsDialog } from "@/components/dialogs/settings-dialog";
import { SetupDialog } from "@/components/dialogs/setup-dialog";
import { SystemFlowDiagram } from "@/components/flow/system-flow-diagram";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Tooltip } from "@/components/ui/tooltip";
import { ActivityFeed } from "@/components/workspace/activity-feed";
import { ComposeMoveForm } from "@/components/workspace/compose-move-form";
import { DeliberationsList } from "@/components/workspace/deliberations-list";
import { HomeView } from "@/components/workspace/home-view";
import { ManifestProgressBar } from "@/components/workspace/manifest-progress";
import { NextStepsPanel } from "@/components/workspace/next-steps-panel";
import { ParticipantsList } from "@/components/workspace/participants-list";
import { SecondaryHeader } from "@/components/workspace/secondary-header";
import {
  type DeliberationDetail,
  type DeliberationListItem,
  type EventRecord,
  type InboxSummary,
  type ManifestResponse,
  type NextAction,
  type ParticipantRow,
  type WorkspaceStateResponse,
  getDeliberation,
  getDeliberations,
  getDigestions,
  getEvents,
  getInboxes,
  getManifest,
  getNextActions,
  getOpenAsks,
  getParticipants,
  getPlan,
  getState,
  subscribeStream,
} from "@/lib/api/conductor";
import {
  BookOpen,
  Code2,
  FilePlus,
  KeyRound,
  Settings2,
  SlidersHorizontal,
  Sparkles,
  Wand2,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

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
  const [composeOpen, setComposeOpen] = useState(false);
  const [setupOpen, setSetupOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [addAgentOpen, setAddAgentOpen] = useState(false);
  const [contextOpen, setContextOpen] = useState(false);
  const [digestionOpen, setDigestionOpen] = useState(false);
  const [permissionsOpen, setPermissionsOpen] = useState(false);
  const [rawEditorOpen, setRawEditorOpen] = useState(false);
  const [newDelibOpen, setNewDelibOpen] = useState(false);
  const [setupNeeded, setSetupNeeded] = useState<boolean | null>(null);
  const [nextActions, setNextActions] = useState<NextAction[]>([]);
  const [digestionInFlight, setDigestionInFlight] = useState(0);
  // Surface mode toggle. Default is Simple (Ask-based home view); the
  // user can drop into Advanced for the original three-pane layout
  // when they need the audit trail or to author moves manually.
  const [mode, setMode] = useState<"simple" | "advanced">("simple");
  const [reloadKey, setReloadKey] = useState(0);
  const bumpReload = useCallback(() => setReloadKey((k) => k + 1), []);
  // Source-of-truth counts for the secondary header pills. Pulled
  // every refresh + every 5s so they don't drift.
  const [agentsWorking, setAgentsWorking] = useState(0);
  const [questionsForYou, setQuestionsForYou] = useState(0);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, m, ds, ps, ev, ib, na] = await Promise.all([
        getState(),
        getManifest(),
        getDeliberations(),
        getParticipants(),
        getEvents(0),
        getInboxes(),
        getNextActions().catch(() => []),
      ]);
      setState(s);
      setManifest(m);
      setList(ds);
      setParticipants(ps);
      setEvents(ev.events);
      setInboxes(ib);
      setNextActions(na);
      // The Setup wizard is only useful for first-time scaffold; once
      // the conductor stops nagging us with run-setup we hide the
      // header button so re-clicking doesn't reset answers.
      setSetupNeeded(na.some((a) => a.id === "run-setup"));
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

  // Poll the secondary-header counts. The previous "N composing /
  // M pending for you" pills read from `activeMarkers` (SSE marker
  // files that survive crashed subprocesses) and `inboxes` (which
  // counts FYI tags as "for you"). Both gave wrong numbers. The
  // accurate sources are:
  //   agentsWorking  — non-manual planner items currently dispatchable
  //   questionsForYou — open Asks (1 row = 1 actionable question)
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const [plan, asks] = await Promise.all([getPlan(), getOpenAsks().catch(() => [])]);
        if (!alive) return;
        setAgentsWorking(plan.items.filter((i) => !i.is_manual).length);
        setQuestionsForYou(asks.length);
      } catch {
        // ignore blips
      }
    };
    void tick();
    const id = setInterval(() => void tick(), 5000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  // Lightweight digestion pulse — polls every 3s so we can flash a
  // "Digesting N…" chip in the header even when the dialog is closed.
  // When the in-flight count drops to zero we also re-fetch the
  // next-actions banner, since digestion completion isn't on the SSE
  // stream and the banner would otherwise stay stale until the user
  // reloads.
  useEffect(() => {
    let alive = true;
    let prev = 0;
    const tick = async () => {
      try {
        const rows = await getDigestions();
        if (!alive) return;
        const inFlight = rows.filter((r) => r.status === "queued" || r.status === "running").length;
        setDigestionInFlight(inFlight);
        // Edge: just finished. Refresh next-actions and the
        // deliberation list (the bundle composition changes once a
        // doc / repo is digested).
        if (prev > 0 && inFlight === 0) {
          void getNextActions()
            .then(setNextActions)
            .catch(() => {});
          void getDeliberations().then(setList);
        }
        prev = inFlight;
      } catch {
        // network blip — leave the previous value
      }
    };
    void tick();
    const id = setInterval(() => void tick(), 3000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

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
        // The server replays the full event log on subscribe; we've
        // already fetched it via getEvents(0). Dedupe by stable
        // JSON identity so the SSE replay doesn't double the feed.
        setEvents((prev) => {
          const seen = new Set(prev.map((e) => JSON.stringify(e)));
          const fresh = incoming.filter((e) => !seen.has(JSON.stringify(e)));
          return fresh.length ? [...prev, ...fresh] : prev;
        });
        // Refresh derived data that's not on the stream yet.
        void getDeliberations().then(setList);
        void getInboxes().then(setInboxes);
        void getNextActions()
          .then(setNextActions)
          .catch(() => {});
        // Tell the Home view to re-fetch Asks; new moves often mean
        // a new Ask appeared (or an existing one was satisfied).
        bumpReload();
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
  }, [bumpReload]);

  useEffect(() => {
    if (selectedId) {
      void getDeliberation(selectedId)
        .then(setActive)
        .catch(() => setActive(null));
    } else {
      setActive(null);
    }
  }, [selectedId]);

  return (
    <div className="flex h-screen flex-col bg-canvas text-fg-primary">
      <Header
        mode={mode}
        onModeChange={setMode}
        onOpenSetup={() => setSetupOpen(true)}
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenContext={() => setContextOpen(true)}
        onOpenPermissions={() => setPermissionsOpen(true)}
        onOpenRawEditor={() => setRawEditorOpen(true)}
        onNewDeliberation={() => setNewDelibOpen(true)}
        showSetup={setupNeeded ?? false}
      />
      {error ? (
        <div className="border-b border-accent-danger bg-accent-danger-weak px-6 py-2 text-sm text-accent-danger">
          API error. {error}. Make sure <code className="font-mono">quorum serve</code> is running.
        </div>
      ) : null}
      <NextStepsPanel
        actions={nextActions}
        onOpenDialog={(id) => {
          if (id === "setup") setSetupOpen(true);
          else if (id === "settings") setSettingsOpen(true);
          else if (id === "add-agent") setAddAgentOpen(true);
          else if (id === "context") setContextOpen(true);
          else if (id === "digestion") setDigestionOpen(true);
          else if (id === "permissions") setPermissionsOpen(true);
          else if (id === "raw-editor") setRawEditorOpen(true);
          else if (id === "new-deliberation") setNewDelibOpen(true);
        }}
      />
      <SecondaryHeader
        state={state}
        participants={participants}
        agentsWorking={agentsWorking}
        questionsForYou={questionsForYou}
        streamConnected={streamConnected}
        onParticipantClick={() => setSettingsOpen(true)}
        onAddParticipant={() => setAddAgentOpen(true)}
      />
      {mode === "simple" ? (
        <main className="flex flex-1 min-h-0 min-w-0">
          <div className="w-[30%] min-w-0 border-r border-border-default flex flex-col">
            <HomeView events={events} deliberations={list} reloadKey={reloadKey} />
          </div>
          <div className="w-[70%] min-w-0">
            <SystemFlowDiagram reloadKey={reloadKey} />
          </div>
        </main>
      ) : (
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
                {active.human_next_action ? (
                  <div className="mb-3 rounded-md border border-accent-primary/40 bg-accent-primary-weak px-3 py-2.5">
                    <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-accent-primary">
                      Your turn ·{" "}
                      <span className="font-mono">{active.human_next_action.move_type}</span>
                    </div>
                    <p className="mt-1 text-sm">{active.human_next_action.expected}</p>
                    <div className="mt-2.5">
                      <Button variant="primary" size="sm" onClick={() => setComposeOpen(true)}>
                        Compose {active.human_next_action.move_type}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="mb-3">
                    <Button variant="primary" size="sm" onClick={() => setComposeOpen(true)}>
                      Compose move
                    </Button>
                  </div>
                )}
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
          </aside>
        </div>
      )}
      {composeOpen && active ? (
        <ComposeMoveForm
          deliberationId={active.id}
          defaultAuthor={participants.find((p) => p.transport === "manual")?.handle ?? "@human"}
          defaultMoveType={
            (active.human_next_action?.move_type as
              | "ANSWER"
              | "DECISION"
              | "INTERJECTION"
              | "OVERRIDE"
              | "REOPEN"
              | "DROP"
              | "STEER"
              | "CLARIFY"
              | "QUESTION"
              | undefined) ?? undefined
          }
          onClose={() => setComposeOpen(false)}
          onAppended={() => {
            void getDeliberation(active.id).then(setActive);
            void getDeliberations().then(setList);
          }}
        />
      ) : null}
      <SetupDialog
        open={setupOpen}
        onClose={() => setSetupOpen(false)}
        onApplied={() => void refresh()}
      />
      <SettingsDialog
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onAddAgent={() => {
          setSettingsOpen(false);
          setAddAgentOpen(true);
        }}
      />
      <AddAgentDialog
        open={addAgentOpen}
        onClose={() => setAddAgentOpen(false)}
        onAdded={() => void refresh()}
      />
      <ContextDialog open={contextOpen} onClose={() => setContextOpen(false)} />
      <DigestionDialog open={digestionOpen} onClose={() => setDigestionOpen(false)} />
      <PermissionsDialog open={permissionsOpen} onClose={() => setPermissionsOpen(false)} />
      <RawEditorDialog open={rawEditorOpen} onClose={() => setRawEditorOpen(false)} />
      <NewDeliberationDialog
        open={newDelibOpen}
        onClose={() => setNewDelibOpen(false)}
        onCreated={(id) => {
          setSelectedId(id);
          void refresh();
        }}
      />
    </div>
  );
}

function Header({
  mode,
  onModeChange,
  onOpenSetup,
  onOpenSettings,
  onOpenContext,
  onOpenPermissions,
  onOpenRawEditor,
  onNewDeliberation,
  showSetup,
}: {
  mode: "simple" | "advanced";
  onModeChange: (m: "simple" | "advanced") => void;
  onOpenSetup: () => void;
  onOpenSettings: () => void;
  onOpenContext: () => void;
  onOpenPermissions: () => void;
  onOpenRawEditor: () => void;
  onNewDeliberation: () => void;
  showSetup: boolean;
}) {
  // Identity, surface-mode toggle, and dialog access. Spend, state,
  // participants, and other operational signals live in the secondary
  // header so this row stays calm.
  return (
    <header className="flex items-center justify-between gap-4 border-b border-border-default bg-elevated px-6 py-3">
      <div className="flex items-center gap-4 min-w-0">
        <span className="font-semibold tracking-tight">Quorum</span>
        <ModeToggle mode={mode} onChange={onModeChange} />
      </div>
      <div className="flex items-center gap-2">
        {showSetup ? (
          <IconBtn onClick={onOpenSetup} title="Run first-time setup">
            <Wand2 size={14} />
          </IconBtn>
        ) : null}
        <IconBtn onClick={onNewDeliberation} title="Start a new deliberation">
          <FilePlus size={14} />
        </IconBtn>
        <IconBtn onClick={onOpenContext} title="Manage context">
          <BookOpen size={14} />
        </IconBtn>
        <IconBtn onClick={onOpenPermissions} title="Pending permission requests">
          <KeyRound size={14} />
        </IconBtn>
        <IconBtn onClick={onOpenSettings} title="Open settings">
          <Settings2 size={14} />
        </IconBtn>
        <IconBtn onClick={onOpenRawEditor} title="Raw editor (advanced)">
          <Code2 size={14} />
        </IconBtn>
        <ThemeToggle />
      </div>
    </header>
  );
}

const MODE_OPTIONS = [
  { value: "simple", label: "Simple", Icon: Sparkles },
  { value: "advanced", label: "Advanced", Icon: SlidersHorizontal },
] as const;

function ModeToggle({
  mode,
  onChange,
}: {
  mode: "simple" | "advanced";
  onChange: (m: "simple" | "advanced") => void;
}) {
  // Same segmented-control shape as ThemeToggle: bordered container
  // with `p-0.5` so the active segment has visible inset. Icon-only
  // buttons; label appears on hover via the `title` attribute.
  return (
    <div
      aria-label="Surface mode"
      className="inline-flex items-center gap-0 rounded-md border border-border-default bg-elevated p-0.5"
    >
      {MODE_OPTIONS.map(({ value, label, Icon }) => {
        const active = mode === value;
        return (
          <Tooltip key={value} label={label}>
            <button
              type="button"
              aria-pressed={active}
              aria-label={label}
              onClick={() => onChange(value)}
              className={`inline-flex h-7 w-7 items-center justify-center rounded-sm transition-colors duration-100 ${
                active
                  ? "bg-accent-primary-weak text-accent-primary"
                  : "text-fg-secondary hover:text-fg-primary"
              }`}
            >
              <Icon size={14} strokeWidth={1.5} />
            </button>
          </Tooltip>
        );
      })}
    </div>
  );
}

function IconBtn({
  children,
  onClick,
  disabled,
  title,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  title: string;
}) {
  return (
    <Tooltip label={title}>
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        aria-label={title}
        className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-border-default text-fg-secondary hover:bg-recessed hover:text-fg-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {children}
      </button>
    </Tooltip>
  );
}

function badgeForState(state: string): "neutral" | "primary" | "success" | "warning" | "danger" {
  if (state === "DECIDED" || state === "COMPLETED") return "success";
  if (state.startsWith("BLOCKED") || state === "PAUSED") return "warning";
  if (state === "ARCHIVED" || state === "ABANDONED") return "danger";
  if (state === "ACTIVE" || state === "OPEN" || state === "IN_REVIEW") return "primary";
  return "neutral";
}
