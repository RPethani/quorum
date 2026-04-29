"use client";

import { Button } from "@/components/ui/button";
import type { NextAction } from "@/lib/api/conductor";
import { AlertTriangle, ChevronDown, Copy, Lightbulb } from "lucide-react";
import { useState } from "react";

type DialogId = "setup" | "settings" | "add-agent" | "context" | "digestion" | "permissions";

const DIALOG_LABELS: Record<DialogId, string> = {
  setup: "Setup",
  settings: "Settings",
  "add-agent": "Add agent",
  context: "Context",
  digestion: "Digestion",
  permissions: "Permissions",
};

/**
 * Persistent guidance panel above the deliberation pane.
 *
 * Two surfaces, no parent/child structure:
 *   1. Blocking actions render as a flat list of equal-weight cards
 *      inside one amber container. Each card is a single row: icon,
 *      title, description, action. Compact — nothing collapses below.
 *   2. Suggested actions render as a slim collapsible strip.
 *   3. With nothing pending, nothing is rendered.
 */
export function NextStepsPanel({
  actions,
  onOpenDialog,
}: {
  actions: NextAction[];
  onOpenDialog: (id: DialogId) => void;
}) {
  if (actions.length === 0) return null;
  const blocking = actions.filter((a) => a.severity === "blocking");
  const tips = actions.filter((a) => a.severity !== "blocking");
  return (
    <>
      {blocking.length > 0 ? (
        <BlockingList blocking={blocking} onOpenDialog={onOpenDialog} />
      ) : null}
      {tips.length > 0 ? <TipsStrip tips={tips} onOpenDialog={onOpenDialog} /> : null}
    </>
  );
}

// ---------------------------------------------------------------------- //
// Blocking — flat list, equal weight per item.
// ---------------------------------------------------------------------- //

function BlockingList({
  blocking,
  onOpenDialog,
}: {
  blocking: NextAction[];
  onOpenDialog: (id: DialogId) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const eyebrow =
    blocking.length === 1 ? "Action required" : `Action required · ${blocking.length}`;
  return (
    <BannerSection
      tone="warning"
      eyebrow={eyebrow}
      icon={<AlertTriangle size={11} strokeWidth={2.5} />}
      items={expanded ? blocking : []}
      onOpenDialog={onOpenDialog}
      headerExtra={
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="ml-auto inline-flex items-center gap-1 text-[10px] font-medium uppercase tracking-wider text-accent-warning hover:opacity-80 transition-opacity"
        >
          {expanded ? "Hide" : blocking.length === 1 ? "Show" : `${blocking.length} items`}
          <ChevronDown
            size={10}
            strokeWidth={2}
            className={`transition-transform ${expanded ? "rotate-180" : ""}`}
          />
        </button>
      }
    />
  );
}

// ---------------------------------------------------------------------- //
// Tips — same shape as blocking, neutral colour, collapsible by default.
// ---------------------------------------------------------------------- //

function TipsStrip({
  tips,
  onOpenDialog,
}: {
  tips: NextAction[];
  onOpenDialog: (id: DialogId) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  if (tips.length === 0) return null;
  const eyebrow = tips.length === 1 ? "Suggestion" : `Suggestions · ${tips.length}`;
  return (
    <BannerSection
      tone="info"
      eyebrow={eyebrow}
      icon={<Lightbulb size={11} strokeWidth={2.5} />}
      items={expanded ? tips : []}
      onOpenDialog={onOpenDialog}
      headerExtra={
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="ml-auto inline-flex items-center gap-1 text-[10px] font-medium uppercase tracking-wider text-fg-tertiary hover:text-fg-primary transition-colors"
        >
          {expanded ? "Hide" : tips.length === 1 ? "Show" : `${tips.length} items`}
          <ChevronDown
            size={10}
            strokeWidth={2}
            className={`transition-transform ${expanded ? "rotate-180" : ""}`}
          />
        </button>
      }
    />
  );
}

// ---------------------------------------------------------------------- //
// Shared banner shape — same typography, spacing, and rhythm; only the
// colour family changes.
// ---------------------------------------------------------------------- //

const TONES: Record<
  "warning" | "info",
  {
    section: string;
    divider: string;
    eyebrow: string;
  }
> = {
  warning: {
    section: "border-b border-accent-warning/40 bg-accent-warning-weak",
    divider: "divide-accent-warning/25",
    eyebrow: "text-accent-warning",
  },
  info: {
    section: "border-b border-border-default bg-recessed/60",
    divider: "divide-border-default",
    eyebrow: "text-fg-tertiary",
  },
};

function BannerSection({
  tone,
  eyebrow,
  icon,
  items,
  onOpenDialog,
  headerExtra,
}: {
  tone: "warning" | "info";
  eyebrow: string;
  icon: React.ReactNode;
  items: NextAction[];
  onOpenDialog: (id: DialogId) => void;
  headerExtra?: React.ReactNode;
}) {
  const t = TONES[tone];
  return (
    <section className={`${t.section} text-fg-primary`}>
      <div className="px-6 py-1.5">
        <div
          className={`flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider ${t.eyebrow}`}
        >
          {icon}
          {eyebrow}
          {headerExtra}
        </div>
        {items.length > 0 ? (
          <ul className={`divide-y ${t.divider}`}>
            {items.map((a) => (
              <li key={a.id} className="flex items-center gap-3 py-1">
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-semibold">{a.title}</div>
                  <p className="text-[11px] text-fg-secondary truncate leading-tight">
                    {a.description}
                  </p>
                </div>
                <ActionButton action={a} onOpenDialog={onOpenDialog} />
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------- //
// Action button — copies CLI commands, opens dialogs, no-op on info.
// ---------------------------------------------------------------------- //

function ActionButton({
  action,
  onOpenDialog,
}: {
  action: NextAction;
  onOpenDialog: (id: DialogId) => void;
}) {
  const [copied, setCopied] = useState(false);
  if (action.kind === "info") return null;
  if (action.kind === "dialog" && action.payload) {
    const id = action.payload as DialogId;
    return (
      <Button variant="primary" size="sm" onClick={() => onOpenDialog(id)} className="shrink-0">
        {DIALOG_LABELS[id] || `Open ${id}`}
      </Button>
    );
  }
  if (action.kind === "cli" && action.payload) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={() => {
          if (action.payload) {
            void navigator.clipboard.writeText(action.payload);
            setCopied(true);
            setTimeout(() => setCopied(false), 1200);
          }
        }}
        title={`Copy: ${action.payload}`}
        className="shrink-0"
      >
        <Copy size={12} />
        <code className="font-mono text-xs">{action.payload}</code>
        {copied ? <span className="text-fg-tertiary">copied</span> : null}
      </Button>
    );
  }
  return null;
}
