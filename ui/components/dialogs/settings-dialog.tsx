"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { ManifestProgressBar } from "@/components/workspace/manifest-progress";
import { ParticipantsList } from "@/components/workspace/participants-list";
import {
  type ContextManifest,
  type ManifestResponse,
  type ParticipantRow,
  type SettingsApplyResponse,
  type SettingsResponse,
  type WorkspaceStateResponse,
  applySettings,
  getContextManifest,
  getManifest,
  getParticipants,
  getSettings,
  getState,
} from "@/lib/api/conductor";
import { Lock, Plus, Save } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

type Tier = "frozen" | "live" | "live-with-effects";

const TIER_BADGE_CLASSES: Record<Tier, string> = {
  frozen: "bg-recessed text-fg-tertiary border border-border-default",
  live: "bg-accent-success-weak text-accent-success border border-accent-success/40",
  "live-with-effects": "bg-accent-warning-weak text-accent-warning border border-accent-warning/40",
};

const TIER_BADGE_LABELS: Record<Tier, string> = {
  frozen: "frozen",
  live: "live",
  "live-with-effects": "live · takes effect later",
};

function TierBadge({ tier }: { tier: Tier }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${TIER_BADGE_CLASSES[tier]}`}
      title={
        tier === "frozen"
          ? "Frozen after the workspace's first start. To change, fork the workspace."
          : tier === "live"
            ? "Saved values apply immediately."
            : "Saved values take effect on the next relevant event (e.g. an unavailability)."
      }
    >
      {TIER_BADGE_LABELS[tier]}
    </span>
  );
}

/**
 * Settings dialog — same eight panels as the previous full-page
 * settings, just rendered inside the workspace's modal layer.
 */
export function SettingsDialog({
  open,
  onClose,
  onAddAgent,
}: {
  open: boolean;
  onClose: () => void;
  onAddAgent?: () => void;
}) {
  const [state, setState] = useState<WorkspaceStateResponse | null>(null);
  const [participants, setParticipants] = useState<ParticipantRow[]>([]);
  const [manifest, setManifest] = useState<ManifestResponse | null>(null);
  const [context, setContext] = useState<ContextManifest | null>(null);
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savingMessage, setSavingMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const [s, p, m, c, sv] = await Promise.all([
        getState(),
        getParticipants(),
        getManifest(),
        getContextManifest(),
        getSettings(),
      ]);
      setState(s);
      setParticipants(p);
      setManifest(m);
      setContext(c);
      setSettings(sv);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    void refresh();
  }, [open, refresh]);

  const isInitialized = state?.state === "INITIALIZED";

  return (
    <Dialog open={open} onClose={onClose} title="Settings" size="lg">
      <div className="space-y-6">
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

        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <CardTitle>Participants</CardTitle>
                <p className="text-sm text-fg-secondary">
                  Registered handles, transports, and health. Quotas and CLI commands are edited in{" "}
                  <code className="font-mono">registers/participants.md</code> for v1.
                </p>
              </div>
              {onAddAgent ? (
                <button
                  type="button"
                  onClick={onAddAgent}
                  className="shrink-0 rounded-md border border-border-default px-2.5 py-1 text-xs font-medium hover:bg-recessed transition-colors inline-flex items-center gap-1"
                  title="Add an agent"
                >
                  <Plus size={12} strokeWidth={2} /> Add
                </button>
              ) : null}
            </div>
          </CardHeader>
          <CardContent>
            <ParticipantsList participants={participants} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Context</CardTitle>
            <p className="text-sm text-fg-secondary">
              Repos, documents, web URLs, notes. Manage from the Context dialog.
            </p>
          </CardHeader>
          <CardContent className="text-sm">
            <ContextSummary context={context} />
          </CardContent>
        </Card>

        <DigesterDefaultsPanel
          settings={settings}
          participants={participants}
          onSaved={(msg) => {
            setSavingMessage(msg);
            void refresh();
          }}
        />

        <RoutingOverridesPanel
          settings={settings}
          participants={participants}
          onSaved={(msg) => {
            setSavingMessage(msg);
            void refresh();
          }}
        />

        <AutoApprovePanel
          settings={settings}
          onSaved={(msg) => {
            setSavingMessage(msg);
            void refresh();
          }}
        />

        <UnavailabilityPanel
          state={state}
          onSaved={(msg) => {
            setSavingMessage(msg);
            void refresh();
          }}
        />

        <LifecyclePanel
          state={state}
          isInitialized={isInitialized}
          onSaved={(msg) => {
            setSavingMessage(msg);
            void refresh();
          }}
        />

        <Card>
          <CardHeader>
            <CardTitle>Manifest</CardTitle>
            <p className="text-sm text-fg-secondary">
              Outcome manifest progress. Edit the manifest itself in{" "}
              <code className="font-mono">outcome-manifest.md</code>.
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
      </div>
    </Dialog>
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
          When agents are unavailable <TierBadge tier="live-with-effects" />
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
          Workspace lifecycle <TierBadge tier="live" /> <TierBadge tier="frozen" />
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

// ---------------------------------------------------------------------- //
// Digester defaults — relevance-tier model selection (design-doc §1.8)
// ---------------------------------------------------------------------- //

function DigesterDefaultsPanel({
  settings,
  participants,
  onSaved,
}: {
  settings: SettingsResponse | null;
  participants: ParticipantRow[];
  onSaved: (msg: string) => void;
}) {
  const [high, setHigh] = useState("");
  const [medium, setMedium] = useState("");
  const [low, setLow] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!settings) return;
    setHigh(settings.digester_defaults.high || "");
    setMedium(settings.digester_defaults.medium || "");
    setLow(settings.digester_defaults.low || "");
  }, [settings]);

  const cliHandles = participants.filter((p) => p.transport === "cli");

  async function save() {
    setSaving(true);
    try {
      const res = await applySettings({
        digester_defaults: {
          ...(high ? { high } : {}),
          ...(medium ? { medium } : {}),
          ...(low ? { low } : {}),
        },
      });
      announce(res, onSaved);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Digester defaults <TierBadge tier="live" />
        </CardTitle>
        <p className="text-sm text-fg-secondary">
          Default agent for digesting context sources, per relevance level. Per-source overrides on
          Add or in the Digestion dialog still take priority.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {(
          [
            ["high", high, setHigh, "@claude-opus"],
            ["medium", medium, setMedium, "@claude-sonnet"],
            ["low", low, setLow, "@claude-haiku"],
          ] as const
        ).map(([level, value, setter, canonical]) => (
          <div key={level} className="grid grid-cols-[100px_1fr] items-center gap-2">
            <span className="text-xs uppercase tracking-wider text-fg-tertiary">{level}</span>
            <select
              value={value}
              onChange={(e) => setter(e.target.value)}
              className="h-9 rounded-sm border border-border-default bg-elevated px-3 text-sm"
            >
              <option value="">canonical default ({canonical})</option>
              {cliHandles.map((h) => (
                <option key={h.handle} value={h.handle}>
                  {h.handle}
                </option>
              ))}
            </select>
          </div>
        ))}
        <Button variant="primary" onClick={save} disabled={saving}>
          <Save size={14} /> Save
        </Button>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------- //
// Routing overrides — workspace-level role pin (Layer 2)
// ---------------------------------------------------------------------- //

const ROUTING_ROLES = [
  "proposer",
  "critic",
  "synthesizer",
  "decider",
  "deputy_decider",
  "ratifier",
  "explainer",
  "questioner",
  "answerer",
] as const;

function RoutingOverridesPanel({
  settings,
  participants,
  onSaved,
}: {
  settings: SettingsResponse | null;
  participants: ParticipantRow[];
  onSaved: (msg: string) => void;
}) {
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!settings) return;
    setOverrides({ ...settings.routing_overrides });
  }, [settings]);

  const cliHandles = participants.filter((p) => p.transport === "cli" || p.transport === "manual");

  async function save() {
    setSaving(true);
    try {
      const res = await applySettings({ routing_overrides: overrides });
      announce(res, onSaved);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Routing overrides <TierBadge tier="live" />
        </CardTitle>
        <p className="text-sm text-fg-secondary">
          Workspace-level pin for a role (Layer 2). Per-deliberation pins still override these.
          Leave blank to fall through to fitness-based routing.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {ROUTING_ROLES.map((role) => (
          <div key={role} className="grid grid-cols-[120px_1fr] items-center gap-2">
            <span className="text-xs uppercase tracking-wider text-fg-tertiary">
              {role.replace("_", " ")}
            </span>
            <select
              value={overrides[role] || ""}
              onChange={(e) =>
                setOverrides((prev) => {
                  const next = { ...prev };
                  if (e.target.value) next[role] = e.target.value;
                  else delete next[role];
                  return next;
                })
              }
              className="h-9 rounded-sm border border-border-default bg-elevated px-3 text-sm"
            >
              <option value="">(no override — fitness-based)</option>
              {cliHandles.map((h) => (
                <option key={h.handle} value={h.handle}>
                  {h.handle}
                </option>
              ))}
            </select>
          </div>
        ))}
        <Button variant="primary" onClick={save} disabled={saving}>
          <Save size={14} /> Save
        </Button>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------- //
// Auto-approve permissions — convenience for low-stakes calls.
// ---------------------------------------------------------------------- //

function AutoApprovePanel({
  settings,
  onSaved,
}: {
  settings: SettingsResponse | null;
  onSaved: (msg: string) => void;
}) {
  const [policy, setPolicy] = useState<string>("none");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!settings) return;
    setPolicy(settings.auto_approve_stakes_below || "none");
  }, [settings]);

  async function save() {
    setSaving(true);
    try {
      const res = await applySettings({
        auto_approve_stakes_below: policy as
          | "trivial"
          | "tactical"
          | "strategic"
          | "irreversible"
          | "none",
      });
      announce(res, onSaved);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Permission auto-approval <TierBadge tier="live" />
        </CardTitle>
        <p className="text-sm text-fg-secondary">
          The conductor auto-approves permission requests at or below this stake tier. Anything
          stricter still requires your explicit decision.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        <select
          value={policy}
          onChange={(e) => setPolicy(e.target.value)}
          className="h-9 rounded-sm border border-border-default bg-elevated px-3 text-sm"
        >
          <option value="none">none — every request requires approval</option>
          <option value="trivial">≤ trivial</option>
          <option value="tactical">≤ tactical</option>
          <option value="strategic">≤ strategic</option>
          <option value="irreversible">≤ irreversible (most permissive)</option>
        </select>
        <Button variant="primary" onClick={save} disabled={saving}>
          <Save size={14} /> Save
        </Button>
      </CardContent>
    </Card>
  );
}
