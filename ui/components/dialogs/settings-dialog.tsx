"use client";

import { Dialog } from "@/components/ui/dialog";
import { updateCanvasState } from "@/lib/api/canvas";
import type { ParticipantRow } from "@/lib/api/conductor";
import { type ComposerSendKey, SETTINGS, useSetting } from "@/lib/settings/store";
import { cn } from "@/lib/utils";
import { useState } from "react";

/**
 * Settings dialog — a single home for user-preference toggles.
 *
 * Sections grow over time. Each section is a small group with a
 * heading + one or more controls. Settings persist via `useSetting`
 * (localStorage-backed); changes propagate to all consumers
 * immediately via the store's pub-sub.
 */
export function SettingsDialog({
  open,
  onClose,
  digesterHandle,
  participants,
  onDigesterChanged,
}: {
  open: boolean;
  onClose: () => void;
  digesterHandle: string;
  participants: ParticipantRow[];
  onDigesterChanged: () => void;
}) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Settings"
      description="Preferences for this browser. Workspace-level settings (cost cap, etc.) will move to a dedicated section later."
      size="md"
    >
      <div className="flex flex-col gap-6">
        <ComposerSection />
        <DefaultAgentsSection
          digesterHandle={digesterHandle}
          participants={participants}
          onChanged={onDigesterChanged}
        />
      </div>
    </Dialog>
  );
}

// ---------------------------------------------------------------------- //
// Default agents — workspace-level (writes through to state.yaml).
// ---------------------------------------------------------------------- //

function DefaultAgentsSection({
  digesterHandle,
  participants,
  onChanged,
}: {
  digesterHandle: string;
  participants: ParticipantRow[];
  onChanged: () => void;
}) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function set(handle: string) {
    setSaving(true);
    setError(null);
    try {
      await updateCanvasState({ digester_handle: handle });
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Section
      title="Default agents"
      description="Which participant the conductor reaches for when a system task needs an agent (e.g. summarising a repo for context)."
    >
      <div className="flex items-center gap-2">
        <span className="text-[12px] text-fg-secondary">Digester</span>
        <select
          value={digesterHandle}
          disabled={saving}
          onChange={(e) => void set(e.target.value)}
          className="rounded-md border border-border-default bg-elevated px-2 py-1 text-sm text-fg-primary focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
        >
          <option value="">— none —</option>
          {participants.map((p) => (
            <option key={p.handle} value={p.handle}>
              {p.handle}
            </option>
          ))}
        </select>
      </div>
      {error ? <p className="mt-2 text-xs text-accent-danger">{error}</p> : null}
    </Section>
  );
}

// ---------------------------------------------------------------------- //
// Composer behaviour
// ---------------------------------------------------------------------- //

function ComposerSection() {
  const [value, setValue] = useSetting<ComposerSendKey>(
    SETTINGS.composerSendKey.key,
    SETTINGS.composerSendKey.default,
  );

  return (
    <Section
      title="Chat input"
      description="What pressing Enter does when you're typing a message."
    >
      <RadioRow<ComposerSendKey>
        name="composer-send-key"
        value={value}
        onChange={setValue}
        options={[
          {
            value: "button",
            label: "Enter inserts a newline",
            sub: "Send is button-only. Best for long messages, lists, and code blocks — Enter never cuts you off mid-thought.",
          },
          {
            value: "enter",
            label: "Enter sends, Shift+Enter for newline",
            sub: "Slack / Discord-style. Faster for short back-and-forth chats.",
          },
        ]}
      />
    </Section>
  );
}

// ---------------------------------------------------------------------- //
// Helpers — kept in this file for now since there's only one section.
// ---------------------------------------------------------------------- //

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h3 className="text-sm font-semibold text-fg-primary">{title}</h3>
      {description ? <p className="mt-0.5 text-[12px] text-fg-tertiary">{description}</p> : null}
      <div className="mt-3">{children}</div>
    </section>
  );
}

function RadioRow<T extends string>({
  name,
  value,
  onChange,
  options,
}: {
  name: string;
  value: T;
  onChange: (next: T) => void;
  options: { value: T; label: string; sub?: string }[];
}) {
  return (
    <ul className="flex flex-col gap-2" role="radiogroup">
      {options.map((opt) => {
        const selected = opt.value === value;
        return (
          <li key={opt.value}>
            <label
              className={cn(
                "flex cursor-pointer items-start gap-3 rounded-md border px-3 py-2.5 transition-colors",
                selected
                  ? "border-accent-primary/60 bg-accent-primary-weak/40"
                  : "border-border-default bg-canvas hover:bg-recessed/60",
              )}
            >
              <input
                type="radio"
                name={name}
                value={opt.value}
                checked={selected}
                onChange={() => onChange(opt.value)}
                className="mt-0.5 shrink-0 h-3.5 w-3.5 accent-accent-primary"
              />
              <div className="min-w-0 flex-1">
                <p
                  className={cn(
                    "text-sm font-medium",
                    selected ? "text-accent-primary" : "text-fg-primary",
                  )}
                >
                  {opt.label}
                </p>
                {opt.sub ? (
                  <p className="mt-0.5 text-[12px] text-fg-tertiary leading-snug">{opt.sub}</p>
                ) : null}
              </div>
            </label>
          </li>
        );
      })}
    </ul>
  );
}
