"use client";

import { ParticipantAvatar } from "@/components/workspace/participant-avatar";
import {
  CanvasApiError,
  type CanvasMessage,
  type CanvasRemediation,
  applyCanvasRemediation,
  parseRemediation,
} from "@/lib/api/canvas";
import { cn } from "@/lib/utils";
import { AlertTriangle, Check, Loader2, RotateCcw, Wrench } from "lucide-react";
import { useState } from "react";

/**
 * One row in the conversation canvas.
 *
 * Per D2 + D4: a Slack/Discord-style row with the participant's brand
 * glyph in a small avatar and a left-border accent so the user can
 * scan the canvas for *who said what* without reading names.
 *
 * Failure messages from `@system` (per D14) render in a warning tone
 * with an inline retry button.
 */
export function MessageRow({
  message,
  onRetry,
}: {
  message: CanvasMessage;
  onRetry?: (messageId: string) => void;
}) {
  const isSystem = message.author === "@system";
  const isHuman = message.author.startsWith("@") && !isSystem && _looksHuman(message.author);
  const { visible, remediation } = parseRemediation(message.body);

  return (
    <article
      className={cn(
        "flex gap-3 px-4 py-3 border-l-2 transition-colors",
        isSystem
          ? "border-accent-warning/60 bg-accent-warning-weak/30"
          : isHuman
            ? "border-accent-primary/40 bg-accent-primary-weak/10"
            : "border-border-default hover:bg-recessed/40",
      )}
    >
      {isSystem ? (
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-warning-weak">
          <AlertTriangle size={14} className="text-accent-warning" strokeWidth={2.5} />
        </div>
      ) : (
        <ParticipantAvatar
          participant={{ handle: message.author, transport: isHuman ? "manual" : "cli" }}
          size={28}
        />
      )}

      <div className="min-w-0 flex-1">
        <header className="flex items-baseline gap-2">
          <span className="text-sm font-semibold text-fg-primary">
            {_displayName(message.author)}
          </span>
          <time
            dateTime={message.ts}
            className="text-[11px] text-fg-tertiary tabular-nums"
            title={message.ts}
          >
            {_formatTime(message.ts)}
          </time>
        </header>

        <div
          className={cn(
            "mt-1 whitespace-pre-wrap text-sm leading-relaxed text-fg-primary",
            isSystem && "text-fg-secondary",
          )}
        >
          {visible}
        </div>

        {remediation ? <RemediationCard rem={remediation} /> : null}

        {isSystem && onRetry ? (
          <button
            type="button"
            onClick={() => onRetry(message.id)}
            className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-accent-warning/40 bg-elevated px-2 py-1 text-[11px] font-medium text-accent-warning hover:bg-accent-warning-weak"
          >
            <RotateCcw size={11} strokeWidth={2.5} />
            Retry
          </button>
        ) : null}
      </div>
    </article>
  );
}

function RemediationCard({ rem }: { rem: CanvasRemediation }) {
  const [state, setState] = useState<"idle" | "applying" | "applied" | "error">("idle");
  const [summary, setSummary] = useState<string>("");

  async function handleApply() {
    setState("applying");
    try {
      const r = await applyCanvasRemediation(rem.id, rem.handle);
      setSummary(r.summary);
      setState("applied");
    } catch (e) {
      setSummary(_extractError(e));
      setState("error");
    }
  }

  const summaryHasMultipleLines = summary.includes("\n");

  return (
    <div className="mt-3 rounded-md border border-accent-warning/40 bg-elevated px-3 py-2">
      <div className="flex items-baseline gap-2">
        <Wrench size={12} className="text-accent-warning" strokeWidth={2.5} />
        <span className="text-[12px] font-semibold text-fg-primary">{rem.title}</span>
      </div>
      <p className="mt-1 text-[11px] leading-snug text-fg-secondary whitespace-pre-wrap">
        {rem.description}
      </p>
      <div className="mt-2">
        <button
          type="button"
          onClick={handleApply}
          disabled={state === "applying" || state === "applied"}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-medium",
            state === "applied"
              ? "border-accent-success/40 bg-accent-success-weak text-accent-success cursor-default"
              : state === "error"
                ? "border-accent-danger/40 bg-accent-danger-weak text-accent-danger"
                : "border-accent-warning/40 bg-canvas text-accent-warning hover:bg-accent-warning-weak",
          )}
        >
          {state === "applying" ? <Loader2 size={11} className="animate-spin" /> : null}
          {state === "applied" ? <Check size={11} strokeWidth={2.5} /> : null}
          {state === "idle" || state === "error" ? <Wrench size={11} strokeWidth={2.5} /> : null}
          {state === "applied"
            ? "Applied"
            : state === "applying"
              ? "Applying…"
              : state === "error"
                ? "Try again"
                : "Apply fix"}
        </button>
      </div>
      {summary ? (
        summaryHasMultipleLines ? (
          <pre
            className={cn(
              "mt-2 whitespace-pre-wrap break-words rounded-md border px-3 py-2 font-mono text-[11px] leading-relaxed",
              state === "applied"
                ? "border-accent-success/30 bg-accent-success-weak/30 text-fg-secondary"
                : "border-accent-danger/30 bg-accent-danger-weak/30 text-fg-primary",
            )}
          >
            {summary}
          </pre>
        ) : (
          <p
            className={cn(
              "mt-2 text-[11px]",
              state === "applied" ? "text-fg-secondary" : "text-accent-danger",
            )}
          >
            {summary}
          </p>
        )
      ) : null}
    </div>
  );
}

/**
 * Pull the inner `error` field out of a `CanvasApiError`'s JSON
 * body so the user sees the conductor's helpful message instead of
 * the wrapped "canvas API 400: {…}" envelope.
 */
function _extractError(e: unknown): string {
  if (e instanceof CanvasApiError) {
    try {
      const body = JSON.parse(e.raw);
      if (typeof body?.error === "string") return body.error;
    } catch {
      /* not JSON — fall through */
    }
    return e.raw;
  }
  return e instanceof Error ? e.message : String(e);
}

function _displayName(handle: string): string {
  if (handle === "@system") return "System";
  const stripped = handle.replace(/^@/, "");
  return stripped.charAt(0).toUpperCase() + stripped.slice(1);
}

function _looksHuman(handle: string): boolean {
  // Heuristic — known human-shaped handles. The conductor doesn't tag
  // messages with "is_human" so we infer from the handle.
  return handle.startsWith("@human-") || handle === "@rakesh" || handle === "@user";
}

function _formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
