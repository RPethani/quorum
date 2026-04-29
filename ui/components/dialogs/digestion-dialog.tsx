"use client";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import {
  type DigestionState,
  type ParticipantRow,
  getDigestions,
  getParticipants,
  queueDigest,
} from "@/lib/api/conductor";
import { CheckCircle2, Loader2, Play, RefreshCw, XCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

/**
 * Digestion control panel.
 *
 * Lists every registered repo with its current digestion state, the
 * proposed digester (resolved server-side from relevance + override),
 * and a per-row override dropdown. "Run digest" kicks off the
 * background queue; the dialog polls every 2s while anything is
 * queued or running so the user sees progress without leaving the
 * page.
 */
export function DigestionDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [states, setStates] = useState<DigestionState[]>([]);
  const [participants, setParticipants] = useState<ParticipantRow[]>([]);
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [s, p] = await Promise.all([getDigestions(), getParticipants()]);
      setStates(s);
      setParticipants(p);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    void refresh();
  }, [open, refresh]);

  // Poll while anything is in flight.
  useEffect(() => {
    if (!open) return;
    const inFlight = states.some((s) => s.status === "queued" || s.status === "running");
    if (!inFlight) return;
    const id = setInterval(() => void refresh(), 2000);
    return () => clearInterval(id);
  }, [open, states, refresh]);

  const cliHandles = participants.filter((p) => p.transport === "cli");
  const pending = states.filter((s) => !s.digest_exists && s.status !== "running");
  const allDone = states.length > 0 && states.every((s) => s.digest_exists);
  const docCount = states.filter((s) => s.kind === "doc").length;
  const repoCount = states.filter((s) => s.kind === "repo").length;
  const [bulkDigester, setBulkDigester] = useState<string>("__per-row__");
  const [bulkBusy, setBulkBusy] = useState(false);

  function applyBulkDigester() {
    if (bulkDigester === "__per-row__") return;
    setOverrides((prev) => {
      const next = { ...prev };
      for (const s of states) {
        if (s.digest_exists) continue;
        if (s.status === "queued" || s.status === "running") continue;
        next[s.name] = bulkDigester;
      }
      return next;
    });
  }

  async function digestAll() {
    setBulkBusy(true);
    setError(null);
    try {
      for (const s of pending) {
        const choice =
          overrides[s.name] ??
          (bulkDigester !== "__per-row__" ? bulkDigester : null) ??
          s.proposed_digester ??
          undefined;
        await queueDigest(s.name, choice ?? undefined, s.kind);
      }
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBulkBusy(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Digestion"
      description="Each repo gets a one-time agent-driven summary so subsequent agents can read a token-efficient digest instead of the full source."
      size="lg"
    >
      <div className="space-y-4">
        {error ? <p className="text-sm text-accent-danger">{error}</p> : null}

        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-xs text-fg-tertiary">
            {states.length === 0 ? (
              <span>Nothing needs digestion yet. Add repos or docs from the Context dialog.</span>
            ) : allDone ? (
              <span className="text-accent-success">All context digested.</span>
            ) : (
              <span>
                {pending.length} of {states.length} pending — {repoCount} repo
                {repoCount === 1 ? "" : "s"}, {docCount} large doc
                {docCount === 1 ? "" : "s"}.
              </span>
            )}
          </div>
          <Button variant="outline" size="sm" onClick={() => void refresh()}>
            <RefreshCw size={12} /> Refresh
          </Button>
        </div>

        {pending.length > 0 ? (
          <div className="flex flex-wrap items-center gap-2 rounded-md border border-border-default bg-recessed/60 px-3 py-2 text-xs">
            <span className="text-fg-tertiary">Apply to all pending:</span>
            <select
              value={bulkDigester}
              onChange={(e) => setBulkDigester(e.target.value)}
              className="h-7 rounded-sm border border-border-default bg-elevated px-2 text-xs"
            >
              <option value="__per-row__">Per-row default</option>
              {cliHandles.map((h) => (
                <option key={h.handle} value={h.handle}>
                  {h.handle}
                </option>
              ))}
            </select>
            <Button
              variant="outline"
              size="sm"
              onClick={applyBulkDigester}
              disabled={bulkDigester === "__per-row__"}
              title="Set the chosen digester on every pending row"
            >
              Apply
            </Button>
            <span className="ml-auto text-fg-tertiary">{pending.length} ready to run</span>
            <Button
              variant="primary"
              size="sm"
              onClick={() => void digestAll()}
              disabled={bulkBusy || pending.length === 0}
            >
              {bulkBusy ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
              Digest all pending
            </Button>
          </div>
        ) : null}

        <ul className="divide-y divide-border-default rounded-md border border-border-default bg-recessed">
          {states.map((s) => {
            const proposed = s.chosen_digester || s.proposed_digester || "(none)";
            const choice = overrides[s.name] ?? proposed;
            return (
              <li key={s.name} className="px-4 py-3 text-sm">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{s.name}</span>
                      <span className="rounded-full bg-recessed px-2 py-0.5 text-xs uppercase tracking-wider text-fg-tertiary">
                        {s.kind}
                      </span>
                      <StatusBadge state={s} />
                      <span className="text-xs text-fg-tertiary">
                        relevance: <span className="font-mono">{s.relevance}</span>
                      </span>
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-fg-secondary">
                      <span>Digester:</span>
                      <select
                        value={choice}
                        onChange={(e) =>
                          setOverrides((prev) => ({ ...prev, [s.name]: e.target.value }))
                        }
                        disabled={s.status === "queued" || s.status === "running"}
                        className="h-7 rounded-sm border border-border-default bg-elevated px-2 text-xs"
                      >
                        {s.proposed_digester ? (
                          <option value={s.proposed_digester}>
                            {s.proposed_digester} (proposed for {s.relevance})
                          </option>
                        ) : null}
                        {cliHandles
                          .filter((h) => h.handle !== s.proposed_digester)
                          .map((h) => (
                            <option key={h.handle} value={h.handle}>
                              {h.handle}
                            </option>
                          ))}
                      </select>
                    </div>
                    {s.last_digested_at ? (
                      <p className="mt-1 text-xs text-fg-tertiary">
                        Last digested {s.last_digested_at}.
                      </p>
                    ) : null}
                    {s.error ? <p className="mt-1 text-xs text-accent-danger">{s.error}</p> : null}
                  </div>
                  <Button
                    variant="primary"
                    size="sm"
                    disabled={busy === s.name || s.status === "queued" || s.status === "running"}
                    onClick={async () => {
                      setBusy(s.name);
                      try {
                        await queueDigest(s.name, choice, s.kind);
                        await refresh();
                      } catch (e) {
                        setError(e instanceof Error ? e.message : String(e));
                      } finally {
                        setBusy(null);
                      }
                    }}
                  >
                    {s.status === "queued" || s.status === "running" || busy === s.name ? (
                      <Loader2 size={12} className="animate-spin" />
                    ) : (
                      <Play size={12} />
                    )}
                    {s.digest_exists ? "Re-digest" : "Digest"}
                  </Button>
                </div>
              </li>
            );
          })}
          {states.length === 0 ? (
            <li className="px-4 py-6 text-sm text-fg-tertiary text-center">Nothing to digest.</li>
          ) : null}
        </ul>

        <p className="text-xs text-fg-tertiary">
          Digestion runs in the background — close this dialog anytime. Progress is tracked in{" "}
          <code className="font-mono">runtime/services/digestions.json</code>.
        </p>
      </div>
    </Dialog>
  );
}

function StatusBadge({ state }: { state: DigestionState }) {
  if (state.status === "running") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-accent-primary-weak px-2 py-0.5 text-xs text-accent-primary">
        <Loader2 size={10} className="animate-spin" /> running
      </span>
    );
  }
  if (state.status === "queued") {
    return (
      <span className="rounded-full bg-accent-primary-weak px-2 py-0.5 text-xs text-accent-primary">
        queued
      </span>
    );
  }
  if (state.status === "failed") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-accent-danger-weak px-2 py-0.5 text-xs text-accent-danger">
        <XCircle size={10} /> failed
      </span>
    );
  }
  if (state.digest_exists) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-accent-success-weak px-2 py-0.5 text-xs text-accent-success">
        <CheckCircle2 size={10} /> ready
      </span>
    );
  }
  return (
    <span className="rounded-full bg-accent-warning-weak px-2 py-0.5 text-xs text-accent-warning">
      needs digest
    </span>
  );
}
