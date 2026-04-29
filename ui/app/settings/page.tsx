"use client";

import { ThemeToggle } from "@/components/design-system/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { ManifestProgressBar } from "@/components/workspace/manifest-progress";
import { ParticipantsList } from "@/components/workspace/participants-list";
import {
  type ContextManifest,
  type ManifestResponse,
  type ParticipantRow,
  type SettingsApplyResponse,
  type WorkspaceStateResponse,
  applySettings,
  getContextManifest,
  getManifest,
  getParticipants,
  getState,
} from "@/lib/api/conductor";
import { Lock, Save, Settings2 } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

/**
 * Phase-9 settings page. Eight panels per design-doc §9.8 Tier 2,
 * mostly read-only with edit affordances on the live-editable fields
 * (cost ceiling, unavailability policy, mode-when-INITIALIZED). Frozen
 * fields show a lock indicator.
 *
 * Permissions panel ships in Phase 11 (broker); here it shows the
 * "broker disabled in v1" copy plus the workspace's allowlist.
 */
export default function SettingsPage() {
  const [state, setState] = useState<WorkspaceStateResponse | null>(null);
  const [participants, setParticipants] = useState<ParticipantRow[]>([]);
  const [manifest, setManifest] = useState<ManifestResponse | null>(null);
  const [context, setContext] = useState<ContextManifest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savingMessage, setSavingMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const [s, p, m, c] = await Promise.all([
        getState(),
        getParticipants(),
        getManifest(),
        getContextManifest(),
      ]);
      setState(s);
      setParticipants(p);
      setManifest(m);
      setContext(c);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const isInitialized = state?.state === "INITIALIZED";

  return (
    <div className="min-h-screen bg-canvas text-fg-primary">
      <header className="flex items-center justify-between border-b border-border-default bg-elevated px-6 py-3">
        <div className="flex items-center gap-3">
          <Link
            href="/workspace"
            className="font-semibold tracking-tight hover:text-accent-primary transition-colors"
          >
            Quorum
          </Link>
          <span className="text-fg-tertiary">/</span>
          <span className="font-medium">Settings</span>
          <Settings2 size={14} className="text-fg-tertiary" strokeWidth={1.5} />
        </div>
        <ThemeToggle />
      </header>

      <main className="mx-auto max-w-3xl space-y-6 px-6 py-8">
        {error ? (
          <Card className="border-accent-danger">
            <CardContent className="text-sm text-accent-danger">API error. {error}</CardContent>
          </Card>
        ) : null}

        {savingMessage ? (
          <Card className="border-accent-success">
            <CardContent className="text-sm text-accent-success">{savingMessage}</CardContent>
          </Card>
        ) : null}

        {/* Panel 1 — Participants */}
        <Card>
          <CardHeader>
            <CardTitle>Participants</CardTitle>
            <p className="text-sm text-fg-secondary">
              Registered handles, transports, and health. Quotas and CLI commands are edited in{" "}
              <code className="font-mono">registers/participants.md</code> for v1.
            </p>
          </CardHeader>
          <CardContent>
            <ParticipantsList participants={participants} />
          </CardContent>
        </Card>

        {/* Panel 2 — Context */}
        <Card>
          <CardHeader>
            <CardTitle>Context</CardTitle>
            <p className="text-sm text-fg-secondary">
              Repos, documents, web URLs, notes. Add via{" "}
              <code className="font-mono">quorum context add-…</code> CLI for v1; UI panels land in
              a follow-up.
            </p>
          </CardHeader>
          <CardContent className="text-sm">
            <ContextSummary context={context} />
          </CardContent>
        </Card>

        {/* Panel 3 — Permissions (broker placeholder) */}
        <Card>
          <CardHeader>
            <CardTitle>
              Permissions <Badge variant="muted">broker comes in Phase 11</Badge>
            </CardTitle>
            <p className="text-sm text-fg-secondary">
              v1 passes restrictive <code className="font-mono">--allowedTools</code> flags to CLIs
              that support them. Out-of-allowlist requests fail moves cleanly. The opt-in live
              broker (with permission-request cards in this UI) ships in Phase 11.
            </p>
          </CardHeader>
        </Card>

        {/* Panel 4 — How decisions get made */}
        <Card>
          <CardHeader>
            <CardTitle>How decisions get made</CardTitle>
            <p className="text-sm text-fg-secondary">
              The decider is read from each deliberation's frontmatter. v1 default:{" "}
              <code className="font-mono">@human-rohan</code>. Decider panels and deputy deciders
              are edited in <code className="font-mono">config.yaml</code>.
            </p>
          </CardHeader>
        </Card>

        {/* Panel 5 — When agents are unavailable */}
        <UnavailabilityPanel
          state={state}
          onSaved={(msg) => {
            setSavingMessage(msg);
            void refresh();
          }}
        />

        {/* Panel 6 — When the human is unavailable */}
        <Card>
          <CardHeader>
            <CardTitle>When the human is unavailable</CardTitle>
            <p className="text-sm text-fg-secondary">
              Human-timeout policy lives in <code className="font-mono">config.yaml</code>'s{" "}
              <code className="font-mono">human_timeout</code> block. v1: deputy decisions for
              tactical-and-below stakes after a 30-minute timeout. UI editor in a follow-up.
            </p>
          </CardHeader>
        </Card>

        {/* Panel 7 — Workspace lifecycle */}
        <LifecyclePanel
          state={state}
          isInitialized={isInitialized}
          onSaved={(msg) => {
            setSavingMessage(msg);
            void refresh();
          }}
        />

        {/* Panel 8 — Manifest */}
        <Card>
          <CardHeader>
            <CardTitle>Manifest</CardTitle>
            <p className="text-sm text-fg-secondary">
              Outcome manifest progress. Edit the manifest itself in{" "}
              <code className="font-mono">outcome-manifest.md</code>; the bootstrapper produces the
              initial draft.
            </p>
          </CardHeader>
          <CardContent>
            <ManifestProgressBar progress={manifest?.progress ?? null} />
            {manifest?.exists ? (
              <Textarea
                readOnly
                value={manifest.markdown}
                className="mt-4 min-h-[12rem] font-mono text-xs leading-relaxed"
              />
            ) : null}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}

function ContextSummary({ context }: { context: ContextManifest | null }) {
  if (!context) return <p className="text-fg-tertiary">Loading…</p>;
  const counts = [
    ["repos", context.repos.length],
    ["docs", context.docs.length],
    ["urls", context.urls.length],
    ["notes", context.notes.length],
  ] as const;
  return (
    <div className="grid grid-cols-4 gap-4 text-center">
      {counts.map(([label, n]) => (
        <div key={label}>
          <div className="text-2xl font-semibold tabular-nums">{n}</div>
          <div className="text-xs uppercase tracking-wider text-fg-tertiary">{label}</div>
        </div>
      ))}
    </div>
  );
}

function UnavailabilityPanel({
  state,
  onSaved,
}: {
  state: WorkspaceStateResponse | null;
  onSaved: (msg: string) => void;
}) {
  const [policy, setPolicy] = useState<"strict" | "substitute" | "substitute_aggressively">(
    "substitute",
  );
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      const res = await applySettings({ unavailability_policy: policy });
      announce(res, onSaved);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          When agents are unavailable <Badge variant="primary">live</Badge>
        </CardTitle>
        <p className="text-sm text-fg-secondary">
          Drives substitution when a routed handle is unavailable. Takes effect on the next
          unavailability event; in-flight work is not disturbed.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {(["strict", "substitute", "substitute_aggressively"] as const).map((p) => (
          <button
            type="button"
            key={p}
            onClick={() => setPolicy(p)}
            className={`block w-full rounded-md border px-4 py-2 text-left text-sm transition-colors ${
              policy === p
                ? "border-accent-primary bg-accent-primary-weak"
                : "border-border-default hover:bg-recessed"
            }`}
          >
            <div className="font-medium">{p}</div>
            <div className="text-xs text-fg-secondary">{policyBlurb(p)}</div>
          </button>
        ))}
        <Button variant="primary" onClick={save} disabled={saving || !state}>
          <Save size={14} /> Save
        </Button>
      </CardContent>
    </Card>
  );
}

function LifecyclePanel({
  state,
  isInitialized,
  onSaved,
}: {
  state: WorkspaceStateResponse | null;
  isInitialized: boolean;
  onSaved: (msg: string) => void;
}) {
  const [ceiling, setCeiling] = useState<string>(state ? state.cost.ceiling_usd.toString() : "50");
  const [enforce, setEnforce] = useState<boolean>(state?.cost.enforce ?? true);
  const [mode, setMode] = useState<"interactive" | "autonomous">(
    (state?.mode as "interactive" | "autonomous") ?? "interactive",
  );
  useEffect(() => {
    if (!state) return;
    setCeiling(state.cost.ceiling_usd.toString());
    setEnforce(state.cost.enforce);
    setMode(state.mode);
  }, [state]);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      const payload = {
        cost_ceiling_usd: Number.parseFloat(ceiling),
        cost_enforce: enforce,
        ...(isInitialized ? { mode } : {}),
      };
      const res = await applySettings(payload);
      announce(res, onSaved);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Workspace lifecycle <Badge variant="primary">live</Badge>
        </CardTitle>
        <p className="text-sm text-fg-secondary">
          Cost ceiling and (until first start) workspace mode.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <label
            className="mb-1 block text-xs font-medium uppercase tracking-wider text-fg-tertiary"
            htmlFor="ceiling"
          >
            Cost ceiling (USD)
          </label>
          <div className="flex items-center gap-2">
            <Input
              id="ceiling"
              type="number"
              min="0"
              step="0.50"
              value={ceiling}
              onChange={(e) => setCeiling(e.target.value)}
              className="max-w-[12rem]"
            />
            <label className="flex items-center gap-1.5 text-xs text-fg-secondary">
              <input
                type="checkbox"
                checked={enforce}
                onChange={(e) => setEnforce(e.target.checked)}
              />
              enforce (pause workspace at cap)
            </label>
          </div>
        </div>

        <div>
          <label
            className="mb-1 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-fg-tertiary"
            htmlFor="mode"
          >
            Mode
            {!isInitialized ? (
              <Lock size={12} className="text-fg-tertiary" strokeWidth={1.5} />
            ) : null}
          </label>
          <select
            id="mode"
            value={mode}
            onChange={(e) => setMode(e.target.value as "interactive" | "autonomous")}
            disabled={!isInitialized}
            className="h-9 rounded-sm border border-border-default bg-elevated px-3 text-sm disabled:opacity-50"
          >
            <option value="interactive">interactive</option>
            <option value="autonomous">autonomous</option>
          </select>
          {!isInitialized ? (
            <p className="mt-1 text-xs text-fg-tertiary">
              Frozen after first start. To change, fork the workspace.
            </p>
          ) : null}
        </div>

        <Button variant="primary" onClick={save} disabled={saving || !state}>
          <Save size={14} /> Save
        </Button>
      </CardContent>
    </Card>
  );
}

function policyBlurb(p: string): string {
  switch (p) {
    case "strict":
      return "Wait for the original handle. Don't substitute.";
    case "substitute":
      return "Substitute with a similar-fitness handle.";
    case "substitute_aggressively":
      return "Substitute with anything available; maximum throughput.";
    default:
      return "";
  }
}

function announce(res: SettingsApplyResponse, onSaved: (msg: string) => void): void {
  const parts: string[] = [];
  if (res.applied.length) parts.push(`Applied: ${res.applied.join(", ")}`);
  if (res.rejected.length) {
    parts.push(`Rejected: ${res.rejected.map((r) => `${r.field} (${r.reason})`).join(", ")}`);
  }
  onSaved(parts.join(" — "));
}
