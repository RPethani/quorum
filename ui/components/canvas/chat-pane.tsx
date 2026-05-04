"use client";

import type { CanvasMessage } from "@/lib/api/canvas";
import { retryCanvasMessage, sendCanvasMessage } from "@/lib/api/canvas";
import type { ParticipantRow } from "@/lib/api/conductor";
import { useEffect, useRef, useState } from "react";
import { Composer } from "./composer";
import { MessageRow } from "./message-row";
import { TypingIndicator } from "./typing-indicator";

/**
 * Left pane of the canvas — chronological conversation thread + the
 * composer at the bottom. Keeps the latest message in view by
 * auto-scrolling on append.
 */
export function ChatPane({
  messages,
  participants,
  onAfterSend,
}: {
  messages: CanvasMessage[];
  participants: ParticipantRow[];
  onAfterSend?: () => void;
}) {
  const scrollerRef = useRef<HTMLDivElement>(null);
  const [pendingHandles, setPendingHandles] = useState<string[]>([]);

  // Auto-scroll on new messages or new typing indicators. We use a
  // composite dep so the effect re-runs when either count changes.
  const visibleCount = messages.length + pendingHandles.length;
  useEffect(() => {
    void visibleCount; // referenced so the effect re-runs on count change
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [visibleCount]);

  async function handleSend(body: string) {
    // Optimistically render typing indicators for each @mention. When
    // the message has no @mentions we mirror the conductor's
    // implicit-fallback rule (route to whoever the user last @-mentioned)
    // so the indicator shows up immediately rather than after the agent
    // replies. Empty mentions list = no implicit target = no indicator.
    let mentions = extractMentions(body);
    if (mentions.length === 0) {
      const implicit = inferImplicitMention(messages, participants);
      if (implicit) mentions = [implicit];
    }
    setPendingHandles(mentions);
    try {
      await sendCanvasMessage(body);
    } finally {
      setPendingHandles([]);
      onAfterSend?.();
    }
  }

  async function handleRetry(messageId: string) {
    // Mirror the conductor's retry routing: find the human message
    // that triggered this @system error, render its @mentions as
    // pending so the user sees "X is thinking…" right away instead of
    // staring at a frozen error card.
    const retryMentions = inferRetryMentions(messages, messageId, participants);
    setPendingHandles(retryMentions);
    try {
      await retryCanvasMessage(messageId);
    } finally {
      setPendingHandles([]);
      onAfterSend?.();
    }
  }

  const isEmpty = messages.length === 0 && pendingHandles.length === 0;
  const composerDisabled = participants.filter((p) => p.transport === "cli").length === 0;

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollerRef} className="flex-1 overflow-y-auto">
        {isEmpty ? (
          <ChatEmptyHint composerDisabled={composerDisabled} />
        ) : (
          <ul className="divide-y divide-border-default/40">
            {messages.map((m) => (
              <li key={m.id}>
                <MessageRow message={m} onRetry={handleRetry} />
              </li>
            ))}
            {pendingHandles.map((h) => (
              <li key={`pending-${h}`}>
                <TypingIndicator handle={h} />
              </li>
            ))}
          </ul>
        )}
      </div>

      <Composer
        participants={participants}
        onSend={handleSend}
        disabled={composerDisabled}
        placeholder={
          composerDisabled
            ? "Add a participant to enable the composer"
            : "Type a message and @mention a participant…"
        }
      />
    </div>
  );
}

// ---------------------------------------------------------------------- //
// Mention helpers — kept in lock-step with the conductor's dispatcher
// (`canvas/dispatcher.py::dispatch`) so the optimistic typing indicators
// match the agents that will actually be invoked server-side.
// ---------------------------------------------------------------------- //

const MENTION_RE = /(?:^|\s)@([\w-]+)/g;

function extractMentions(body: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const m of body.matchAll(MENTION_RE)) {
    const handle = `@${m[1]}`;
    if (seen.has(handle)) continue;
    seen.add(handle);
    out.push(handle);
  }
  return out;
}

function isHumanAuthored(author: string, agents: Set<string>): boolean {
  return author !== "@system" && !agents.has(author);
}

/**
 * Find the most recent human message with at least one @mention and
 * return that message's *last* @mention — matching dispatcher's rule
 * for the no-mention follow-up case.
 */
function inferImplicitMention(
  messages: CanvasMessage[],
  participants: ParticipantRow[],
): string | null {
  const agents = new Set(participants.map((p) => p.handle));
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (!isHumanAuthored(m.author, agents)) continue;
    const ms = extractMentions(m.body);
    if (ms.length > 0) return ms[ms.length - 1];
  }
  return null;
}

/**
 * For a retry on `errorId`, walk backward to the human message that
 * triggered the failure and return *all* of its @mentions — the
 * conductor's retry handler re-dispatches the whole list.
 */
function inferRetryMentions(
  messages: CanvasMessage[],
  errorId: string,
  participants: ParticipantRow[],
): string[] {
  const agents = new Set(participants.map((p) => p.handle));
  const idx = messages.findIndex((m) => m.id === errorId);
  if (idx < 0) return [];
  for (let i = idx - 1; i >= 0; i--) {
    const m = messages[i];
    if (!isHumanAuthored(m.author, agents)) continue;
    const ms = extractMentions(m.body);
    if (ms.length > 0) return ms;
  }
  return [];
}

function ChatEmptyHint({ composerDisabled }: { composerDisabled: boolean }) {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="max-w-sm px-6 text-center">
        <p className="text-sm text-fg-secondary">
          {composerDisabled
            ? "Add a participant to start. Then type a message and @mention them."
            : "Type a message and @mention a participant to start the brainstorm."}
        </p>
      </div>
    </div>
  );
}
