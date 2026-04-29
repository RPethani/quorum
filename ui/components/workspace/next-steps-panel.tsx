"use client";

import { Button } from "@/components/ui/button";
import type { NextAction } from "@/lib/api/conductor";
import { AlertTriangle, ChevronDown, Copy, Lightbulb } from "lucide-react";
import { useState } from "react";

type DialogId = "setup" | "settings" | "add-agent" | "context";

const DIALOG_LABELS: Record<DialogId, string> = {
  setup: "Setup",
  settings: "Settings",
  "add-agent": "Add agent",
  context: "Context",
};

/**
 * Persistent guidance panel above the deliberation pane.
 *
 * Three rendering modes, driven by action severity:
 *   1. Has blocking action → full-width amber banner with title +
 *      description + a primary action button. Visually obvious that
 *      collaboration cannot proceed until this is resolved.
 *   2. Only suggested / info actions → collapsed single-line strip
 *      (small bulb + "N tips"); click to expand the list.
 *   3. No actions → renders nothing.
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

  if (blocking.length > 0) {
    return <BlockingBanner blocking={blocking} tips={tips} onOpenDialog={onOpenDialog} />;
  }
  return <TipsStrip tips={tips} onOpenDialog={onOpenDialog} />;
}

// ---------------------------------------------------------------------- //
// Blocking — full-width amber banner. Until cleared, the user knows
// they're stuck and has a one-click path forward.
// ---------------------------------------------------------------------- //

function BlockingBanner({
  blocking,
  tips,
  onOpenDialog,
}: {
  blocking: NextAction[];
  tips: NextAction[];
  onOpenDialog: (id: DialogId) => void;
}) {
  const primary = blocking.find((a) => a.primary) ?? blocking[0];
  const otherBlocking = blocking.filter((a) => a.id !== primary.id);
  const [expanded, setExpanded] = useState(false);
  const extraCount = otherBlocking.length + tips.length;

  return (
    <section className="border-b border-accent-warning/40 bg-accent-warning-weak text-fg-primary">
      <div className="flex items-start gap-3 px-6 py-3">
        <AlertTriangle size={18} className="mt-0.5 shrink-0 text-accent-warning" strokeWidth={2} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-xs font-semibold uppercase tracking-wider text-accent-warning">
              Action required
            </span>
            <h3 className="text-sm font-semibold">{primary.title}</h3>
          </div>
          <p className="mt-1 text-sm text-fg-secondary">{primary.description}</p>
          {extraCount > 0 ? (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="mt-2 inline-flex items-center gap-1 text-xs text-fg-tertiary hover:text-fg-primary transition-colors"
            >
              <ChevronDown
                size={12}
                className={`transition-transform ${expanded ? "rotate-180" : ""}`}
                strokeWidth={2}
              />
              {expanded ? "Hide" : `${extraCount} more`}
            </button>
          ) : null}
          {expanded ? (
            <ul className="mt-3 space-y-3 border-t border-accent-warning/30 pt-3">
              {[...otherBlocking, ...tips].map((a) => (
                <li key={a.id} className="flex items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium">{a.title}</div>
                    <p className="mt-0.5 text-xs text-fg-secondary">{a.description}</p>
                  </div>
                  <ActionButton action={a} onOpenDialog={onOpenDialog} compact />
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        <ActionButton action={primary} onOpenDialog={onOpenDialog} />
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
        <ul className="space-y-3 border-t border-border-default px-6 py-3">
          {tips.map((a) => (
            <li key={a.id} className="flex items-start gap-3">
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium">{a.title}</div>
                <p className="mt-0.5 text-xs text-fg-secondary">{a.description}</p>
              </div>
              <ActionButton action={a} onOpenDialog={onOpenDialog} compact />
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
  compact = false,
}: {
  action: NextAction;
  onOpenDialog: (id: DialogId) => void;
  compact?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  if (action.kind === "info") return null;
  const size = compact ? "sm" : "sm";
  if (action.kind === "dialog" && action.payload) {
    const id = action.payload as DialogId;
    return (
      <Button variant="primary" size={size} onClick={() => onOpenDialog(id)} className="shrink-0">
        {DIALOG_LABELS[id] || `Open ${id}`}
      </Button>
    );
  }
  if (action.kind === "cli" && action.payload) {
    return (
      <Button
        variant={compact ? "outline" : "primary"}
        size={size}
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
