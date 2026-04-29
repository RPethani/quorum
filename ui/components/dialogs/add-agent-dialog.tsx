"use client";

import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { addAgent, getParticipants } from "@/lib/api/conductor";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

type VerifyResult =
  | { state: "idle" }
  | { state: "verifying"; handle: string }
  | { state: "ok"; handle: string }
  | { state: "fail"; handle: string; note: string };

/**
 * Add a CLI participant to participants.md without leaving the
 * workspace. Pick a preset (the common CLIs we know about) or roll
 * a custom handle.
 *
 * The form is intentionally minimal — we only collect what the
 * conductor's router actually needs at the start. Quotas, permission
 * capability, account labels are tucked behind "Advanced".
 */
type Preset = {
  handle: string;
  label: string;
  cliCommand: string;
  model: string;
  blurb: string;
};

const PRESETS: Preset[] = [
  {
    handle: "@claude",
    label: "Claude (Sonnet)",
    cliCommand: "claude",
    model: "sonnet",
    blurb: "Anthropic Claude via the official `claude` CLI.",
  },
  {
    handle: "@claude-opus",
    label: "Claude (Opus)",
    cliCommand: "claude --model opus",
    model: "opus",
    blurb: "Higher-quality, slower, more expensive than Sonnet.",
  },
  {
    handle: "@codex",
    label: "OpenAI Codex",
    cliCommand: "codex",
    model: "gpt-5",
    blurb: "OpenAI's coding agent CLI.",
  },
  {
    handle: "@gemini",
    label: "Google Gemini",
    cliCommand: "gemini",
    model: "gemini-2.5-pro",
    blurb: "Google Gemini via the `gemini` CLI.",
  },
];

export function AddAgentDialog({
  open,
  onClose,
  onAdded,
}: {
  open: boolean;
  onClose: () => void;
  onAdded?: (handle: string) => void;
}) {
  const [preset, setPreset] = useState<string | null>(null);
  const [handle, setHandle] = useState("");
  const [cliCommand, setCliCommand] = useState("");
  const [model, setModel] = useState("");
  const [accountLabel, setAccountLabel] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [verify, setVerify] = useState<VerifyResult>({ state: "idle" });

  useEffect(() => {
    if (!open) return;
    // Reset on each open so re-opening after success starts fresh.
    setPreset(null);
    setHandle("");
    setCliCommand("");
    setModel("");
    setAccountLabel("");
    setError(null);
    setSubmitting(false);
    setVerify({ state: "idle" });
  }, [open]);

  function applyPreset(p: Preset) {
    setPreset(p.handle);
    setHandle(p.handle);
    setCliCommand(p.cliCommand);
    setModel(p.model);
  }

  async function submit() {
    setSubmitting(true);
    setError(null);
    setVerify({ state: "idle" });
    try {
      const res = await addAgent({
        handle: handle.trim(),
        display_name: preset
          ? PRESETS.find((p) => p.handle === preset)?.label || ""
          : handle.trim().replace(/^@/, ""),
        cli_command: cliCommand.trim(),
        model: model.trim() || "n/a",
        transport: "cli",
        account_label: accountLabel.trim(),
      });
      // Run a verification step against the freshly-added handle.
      // If the configured CLI isn't on PATH, surface that here so the
      // user can fix it before the loop tries to invoke the agent.
      setVerify({ state: "verifying", handle: res.handle });
      const ps = await getParticipants();
      const row = ps.find((p) => p.handle === res.handle);
      const live = row?.live_health;
      if (live && live.on_path === true) {
        setVerify({ state: "ok", handle: res.handle });
        onAdded?.(res.handle);
        // Brief pause so the user sees the green state before close.
        setTimeout(onClose, 600);
      } else if (live) {
        setVerify({
          state: "fail",
          handle: res.handle,
          note: live.note || "CLI command isn't on PATH.",
        });
        onAdded?.(res.handle);
      } else {
        // No live_health (non-cli transport) — treat as added.
        onAdded?.(res.handle);
        onClose();
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  const valid = handle.trim().length > 0 && cliCommand.trim().length > 0;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Add an AI agent"
      description="Pick a preset or define a custom CLI handle. The conductor will append a row to registers/participants.md."
      size="md"
    >
      <div className="space-y-5">
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-fg-tertiary">
            Pick a preset
          </p>
          <div className="grid grid-cols-2 gap-2">
            {PRESETS.map((p) => (
              <button
                type="button"
                key={p.handle}
                onClick={() => applyPreset(p)}
                className={`text-left rounded-md border px-3 py-2 transition-colors ${
                  preset === p.handle
                    ? "border-accent-primary bg-accent-primary-weak"
                    : "border-border-default hover:bg-recessed"
                }`}
              >
                <div className="font-mono text-xs text-fg-tertiary">{p.handle}</div>
                <div className="text-sm font-medium">{p.label}</div>
                <div className="mt-0.5 text-xs text-fg-secondary">{p.blurb}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="border-t border-border-default pt-5">
          <p className="mb-3 text-xs font-medium uppercase tracking-wider text-fg-tertiary">
            Or fill in manually
          </p>
          <div className="space-y-3">
            <Field label="Handle" hint="Starts with @, lowercase letters/digits/hyphens.">
              <Input
                value={handle}
                onChange={(e) => setHandle(e.target.value)}
                placeholder="@claude"
                className="font-mono"
              />
            </Field>
            <Field label="CLI command" hint="The command Quorum will invoke.">
              <Input
                value={cliCommand}
                onChange={(e) => setCliCommand(e.target.value)}
                placeholder="claude"
                className="font-mono"
              />
            </Field>
            <Field label="Model" hint="Free text — used for routing fitness lookups.">
              <Input
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="sonnet"
                className="font-mono"
              />
            </Field>
            <Field label="Account label" hint="Optional. Distinguishes multiple subscriptions.">
              <Input
                value={accountLabel}
                onChange={(e) => setAccountLabel(e.target.value)}
                placeholder="personal"
              />
            </Field>
          </div>
        </div>

        {error ? <p className="text-sm text-accent-danger">{error}</p> : null}

        {verify.state === "verifying" ? (
          <div className="flex items-center gap-2 rounded-md border border-border-default bg-recessed px-3 py-2 text-sm">
            <Loader2 size={14} className="animate-spin text-fg-tertiary" />
            <span>Verifying {verify.handle} is reachable…</span>
          </div>
        ) : null}
        {verify.state === "ok" ? (
          <div className="flex items-center gap-2 rounded-md border border-accent-success/40 bg-accent-success-weak px-3 py-2 text-sm text-accent-success">
            <CheckCircle2 size={14} />
            <span>{verify.handle} is reachable. Ready to collaborate.</span>
          </div>
        ) : null}
        {verify.state === "fail" ? (
          <div className="rounded-md border border-accent-danger/40 bg-accent-danger-weak px-3 py-2 text-sm">
            <div className="flex items-center gap-2 font-medium text-accent-danger">
              <XCircle size={14} />
              <span>{verify.handle} isn't reachable</span>
            </div>
            <p className="mt-1 text-fg-secondary">{verify.note}</p>
            <p className="mt-1 text-xs text-fg-tertiary">
              The row was added to participants.md. Fix the CLI command in Settings or install the
              tool, then re-verify by re-fetching participants.
            </p>
          </div>
        ) : null}
      </div>

      <DialogFooter>
        <Button variant="outline" onClick={onClose} disabled={submitting}>
          {verify.state === "fail" ? "Close" : "Cancel"}
        </Button>
        {verify.state !== "fail" ? (
          <Button variant="primary" onClick={submit} disabled={!valid || submitting}>
            {submitting ? <Loader2 size={14} className="animate-spin" /> : null}
            Add agent
          </Button>
        ) : null}
      </DialogFooter>
    </Dialog>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <fieldset className="block border-0 p-0">
      <legend className="mb-1 block text-xs font-medium uppercase tracking-wider text-fg-tertiary">
        {label}
      </legend>
      {children}
      {hint ? <p className="mt-1 text-xs text-fg-tertiary">{hint}</p> : null}
    </fieldset>
  );
}
