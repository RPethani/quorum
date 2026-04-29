"use client";

import { Button } from "@/components/ui/button";
import type { NextAction } from "@/lib/api/conductor";
import { AlertTriangle, ChevronDown, Copy, Lightbulb } from "lucide-react";
import { useState } from "react";

type DialogId = "setup" | "settings" | "add-agent" | "context" | "digestion";

const DIALOG_LABELS: Record<DialogId, string> = {
  setup: "Setup",
  settings: "Settings",
  "add-agent": "Add agent",
  context: "Context",
  digestion: "Digestion",
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
  return (
    <section className="border-b border-accent-warning/40 bg-accent-warning-weak text-fg-primary">
      <div className="px-6 py-2">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-accent-warning">
          <AlertTriangle size={14} strokeWidth={2} />
          {blocking.length === 1 ? "Action required" : `Action required · ${blocking.length}`}
        </div>
        <ul className="mt-1.5 divide-y divide-accent-warning/25">
          {blocking.map((a) => (
            <li key={a.id} className="flex items-center gap-3 py-1.5">
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium">{a.title}</div>
                <p className="text-xs text-fg-secondary truncate">{a.description}</p>
              </div>
              <ActionButton action={a} onOpenDialog={onOpenDialog} />
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------- //
// Tips — slim strip, single line, click to expand. No urgency colour.
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
  const first = tips[0];

  return (
    <section className="border-b border-border-default bg-recessed/60 text-sm">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-2 px-6 py-1.5 text-left hover:bg-recessed transition-colors"
      >
        <Lightbulb size={14} className="shrink-0 text-fg-tertiary" strokeWidth={1.5} />
        <span className="text-xs text-fg-secondary truncate">
          {tips.length > 1 ? `${tips.length} suggestions — ${first.title}` : first.title}
        </span>
        <ChevronDown
          size={12}
          className={`ml-auto shrink-0 text-fg-tertiary transition-transform ${
            expanded ? "rotate-180" : ""
          }`}
          strokeWidth={1.5}
        />
      </button>
      {expanded ? (
        <ul className="divide-y divide-border-default px-6 py-2">
          {tips.map((a) => (
            <li key={a.id} className="flex items-center gap-3 py-1.5">
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium">{a.title}</div>
                <p className="text-xs text-fg-secondary truncate">{a.description}</p>
              </div>
              <ActionButton action={a} onOpenDialog={onOpenDialog} />
            </li>
          ))}
        </ul>
      ) : null}
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
