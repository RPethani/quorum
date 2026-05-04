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
    // Optimistically render typing indicators for each @mention.
    const mentions = Array.from(body.matchAll(/(?:^|\s)@([\w-]+)/g)).map((m) => `@${m[1]}`);
    setPendingHandles(mentions);
    try {
      await sendCanvasMessage(body);
    } finally {
      setPendingHandles([]);
      onAfterSend?.();
    }
  }

  async function handleRetry(messageId: string) {
    try {
      await retryCanvasMessage(messageId);
    } finally {
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
