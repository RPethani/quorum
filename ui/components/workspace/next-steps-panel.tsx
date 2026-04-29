"use client";

import { Button } from "@/components/ui/button";
import type { NextAction } from "@/lib/api/conductor";
import { ChevronRight, Copy, Sparkles } from "lucide-react";
import { useState } from "react";

/**
 * Persistent "What's next" panel surfaced above the deliberation pane
 * on the workspace page. Renders the actions list returned by
 * /api/next-actions; each action is either:
 *   - dialog: clicking opens a known modal (setup/settings).
 *   - cli: clicking copies the command to the clipboard.
 *   - info: read-only nudge.
 */
export function NextStepsPanel({
  actions,
  onOpenDialog,
}: {
  actions: NextAction[];
  onOpenDialog: (id: "setup" | "settings") => void;
}) {
  if (actions.length === 0) return null;
  const primary = actions.find((a) => a.primary) ?? actions[0];
  const secondary = actions.filter((a) => a.id !== primary.id);
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border-b border-border-default bg-recessed">
      <div className="mx-auto max-w-5xl px-6 py-3">
        <div className="flex items-start gap-3">
          <Sparkles size={16} className="mt-0.5 shrink-0 text-accent-primary" strokeWidth={1.5} />
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold">{primary.title}</h3>
              <ActionButton action={primary} onOpenDialog={onOpenDialog} />
            </div>
            <p className="mt-1 text-sm text-fg-secondary">{primary.description}</p>
            {secondary.length > 0 ? (
              <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                className="mt-2 inline-flex items-center gap-1 text-xs text-fg-tertiary hover:text-fg-primary transition-colors"
              >
                <ChevronRight
                  size={12}
                  className={`transition-transform ${expanded ? "rotate-90" : ""}`}
                  strokeWidth={1.5}
                />
                {expanded ? "Hide" : `Show ${secondary.length} more`}
              </button>
            ) : null}
            {expanded ? (
              <ul className="mt-3 space-y-3">
                {secondary.map((a) => (
                  <li key={a.id} className="flex items-start gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium">{a.title}</div>
                      <p className="mt-0.5 text-xs text-fg-secondary">{a.description}</p>
                    </div>
                    <ActionButton action={a} onOpenDialog={onOpenDialog} />
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

function ActionButton({
  action,
  onOpenDialog,
}: {
  action: NextAction;
  onOpenDialog: (id: "setup" | "settings") => void;
}) {
  const [copied, setCopied] = useState(false);
  if (action.kind === "info") return null;
  if (action.kind === "dialog" && action.payload) {
    const id = action.payload as "setup" | "settings";
    return (
      <Button variant="primary" size="sm" onClick={() => onOpenDialog(id)}>
        Open {action.payload}
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
      >
        <Copy size={12} />
        <code className="font-mono text-xs">{action.payload}</code>
        {copied ? <span className="text-fg-tertiary">copied</span> : null}
      </Button>
    );
  }
  return null;
}
