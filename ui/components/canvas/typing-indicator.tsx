"use client";

import { ParticipantAvatar } from "@/components/workspace/participant-avatar";
import { cn } from "@/lib/utils";

/**
 * Per D8: when an `@mention`ed agent is generating, render a small
 * "<name> is thinking…" placeholder card with the participant's
 * avatar. When the response arrives the placeholder is replaced
 * in-place by the full message.
 */
export function TypingIndicator({ handle }: { handle: string }) {
  return (
    <article className="flex gap-3 px-4 py-3 border-l-2 border-border-default opacity-80">
      <ParticipantAvatar participant={{ handle, transport: "cli" }} size={28} />
      <div className="min-w-0 flex-1">
        <header className="flex items-baseline gap-2">
          <span className="text-sm font-semibold text-fg-primary">{handle.replace(/^@/, "")}</span>
        </header>
        <div className="mt-1 flex items-center gap-2 text-sm text-fg-tertiary">
          <span>is thinking</span>
          <span className="inline-flex gap-0.5">
            <Dot delay="0ms" />
            <Dot delay="150ms" />
            <Dot delay="300ms" />
          </span>
        </div>
      </div>
    </article>
  );
}

function Dot({ delay }: { delay: string }) {
  return (
    <span
      className={cn("inline-block h-1.5 w-1.5 rounded-full bg-fg-tertiary composing-pulse")}
      style={{ animationDelay: delay }}
    />
  );
}
