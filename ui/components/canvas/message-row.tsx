"use client";

import { Dialog } from "@/components/ui/dialog";
import { Markdown } from "@/components/ui/markdown";
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
        // Compact spacing: ~10px vertical padding + ~10px gap reads
        // dense enough to scan a long thread without feeling crowded.
        "flex gap-2.5 px-4 py-2.5 transition-colors",
        // System / warning messages keep their distinct treatment so
        // failures and other operator-attention items pop visually.
        // Everything else (human + AI) renders on a clean white surface
        // — no left-border accent, no per-author tint. The brand-glyph
        // avatar already carries the "who said what" signal.
        isSystem
          ? "border-l-2 border-accent-warning/60 bg-accent-warning-weak/30"
          : "bg-elevated hover:bg-recessed/40",
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

        {isSystem ? (
          <SystemErrorBody body={visible} />
        ) : (
          <div className="mt-0.5">
            <Markdown body={visible} colorMentions />
          </div>
        )}

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

/**
 * Render the body of an `@system` (error) message in collapsed form:
 * just the first line, with a "Show full error" link that opens the
 * complete text in a dialog. Remediation cards and the Retry button
 * still render inline beneath this — only the verbose stack trace is
 * tucked away.
 */
function SystemErrorBody({ body }: { body: string }) {
  const [dialogOpen, setDialogOpen] = useState(false);
  // Whitespace-trim the first line so leading newlines from CLI
  // output (e.g. "\n\nError: ...") don't render as an empty preview.
  const trimmed = body.replace(/^\s+/, "");
  const newlineIdx = trimmed.indexOf("\n");
  const firstLine = newlineIdx === -1 ? trimmed : trimmed.slice(0, newlineIdx);
  const hasMore = trimmed.length > firstLine.length;

  return (
    <>
      <div className="mt-0.5 whitespace-pre-wrap break-words text-sm leading-relaxed text-fg-secondary">
        {firstLine}
      </div>
      {hasMore ? (
        <button
          type="button"
          onClick={() => setDialogOpen(true)}
          // `block` ensures the button takes its own line, so the
          // sibling Retry button below sits below it (not next to it
          // when no remediation card sits between them).
          className="mt-1 block text-[11px] font-medium text-accent-primary hover:underline"
        >
          Show full error
        </button>
      ) : null}
      {dialogOpen ? (
        <Dialog
          open
          onClose={() => setDialogOpen(false)}
          title="Error details"
          description="Full output from the participant CLI."
          size="lg"
        >
          <pre className="whitespace-pre-wrap break-words rounded-md border border-border-default bg-canvas px-3 py-2 font-mono text-[11px] leading-relaxed text-fg-primary">
            {body}
          </pre>
        </Dialog>
      ) : null}
    </>
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
