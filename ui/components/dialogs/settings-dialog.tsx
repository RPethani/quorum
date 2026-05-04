"use client";

import { Dialog } from "@/components/ui/dialog";
import { type ComposerSendKey, SETTINGS, useSetting } from "@/lib/settings/store";
import { cn } from "@/lib/utils";

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
}: {
  open: boolean;
  onClose: () => void;
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
      </div>
    </Dialog>
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
