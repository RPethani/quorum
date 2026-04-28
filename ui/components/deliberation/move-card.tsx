import { HandleAvatar } from "@/components/design-system/handle-avatar";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export type MoveType =
  | "PROPOSAL"
  | "CRITIQUE"
  | "SYNTHESIS"
  | "DECISION"
  | "QUESTION"
  | "ANSWER"
  | "EXPLANATION"
  | "INTERJECTION"
  | "ABSTAIN";

export type MoveCardState = "complete" | "composing" | "failed";

export type MoveCardProps = {
  moveType: MoveType;
  author: string;
  timestamp: string;
  state?: MoveCardState;
  targets?: string;
  children?: ReactNode;
  className?: string;
};

// Per-move-type left-border color. Subtle category cues only.
const ACCENT_BY_TYPE: Record<MoveType, string> = {
  PROPOSAL: "border-l-neutral-400 dark:border-l-neutral-600",
  CRITIQUE: "border-l-neutral-400 dark:border-l-neutral-600",
  SYNTHESIS: "border-l-neutral-400 dark:border-l-neutral-600",
  DECISION: "border-l-accent-success",
  QUESTION: "border-l-accent-warning",
  ANSWER: "border-l-accent-warning",
  EXPLANATION: "border-l-accent-muted",
  INTERJECTION: "border-l-accent-muted",
  ABSTAIN: "border-l-neutral-300 dark:border-l-neutral-700",
};

/**
 * Phase 2 skeleton of MoveCard. Establishes the visual contract used by
 * Phase 7 (full deliberation timeline). Shape, typography, and state
 * variants are settled here; richer body rendering comes later.
 */
export function MoveCard({
  moveType,
  author,
  timestamp,
  state = "complete",
  targets,
  children,
  className,
}: MoveCardProps) {
  return (
    <article
      aria-label={`${moveType} by ${author}`}
      className={cn(
        "border-l-4 border border-border-default bg-elevated rounded-md p-4",
        ACCENT_BY_TYPE[moveType],
        state === "composing" && "border-l-accent-primary composing-pulse",
        state === "failed" && "bg-accent-danger-weak border-l-accent-danger",
        className,
      )}
    >
      <header className="flex items-center gap-3 text-xs">
        <HandleAvatar handle={author} size="sm" />
        <span
          className={cn(
            "label-caps font-mono font-semibold tracking-wide text-fg-primary",
            state === "failed" && "line-through",
          )}
        >
          {moveType}
        </span>
        <span className="font-mono text-fg-tertiary">{author}</span>
        <span className="text-fg-tertiary">·</span>
        <time className="font-mono text-fg-tertiary">{timestamp}</time>
        {targets ? (
          <>
            <span className="text-fg-tertiary">→ targets</span>
            <span className="font-mono text-fg-tertiary">{targets}</span>
          </>
        ) : null}
      </header>
      {children ? <div className="pt-3 text-sm text-fg-primary">{children}</div> : null}
    </article>
  );
}
