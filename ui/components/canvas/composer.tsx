"use client";

import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import type { ParticipantRow } from "@/lib/api/conductor";
import { type ComposerSendKey, SETTINGS, useSetting } from "@/lib/settings/store";
import { cn } from "@/lib/utils";
import { Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";

/**
 * Chat composer at the bottom of the canvas pane.
 *
 * D11 commitments:
 *   - multi-line textarea, auto-grows to ~6 lines
 *   - Enter inserts a newline; **send is button-only**
 *   - `@` opens an autocomplete popover listing enabled participants
 *   - send button at bottom-right
 */
export function Composer({
  participants,
  onSend,
  disabled,
  placeholder = "Type a message and @mention a participant…",
}: {
  participants: ParticipantRow[];
  onSend: (body: string) => void | Promise<void>;
  disabled?: boolean;
  placeholder?: string;
}) {
  const [body, setBody] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [mention, setMention] = useState<{ start: number; query: string } | null>(null);
  const [highlightedIdx, setHighlightedIdx] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [sendKey] = useSetting<ComposerSendKey>(
    SETTINGS.composerSendKey.key,
    SETTINGS.composerSendKey.default,
  );

  // Auto-grow textarea up to ~6 lines.
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    const max = 6 * 24; // 6 lines at 24px line-height
    ta.style.height = `${Math.min(ta.scrollHeight, max)}px`;
  }, []);

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const value = e.target.value;
    setBody(value);
    // Auto-grow.
    e.target.style.height = "auto";
    const max = 6 * 24;
    e.target.style.height = `${Math.min(e.target.scrollHeight, max)}px`;

    // Detect @mention in progress at cursor position.
    const cursor = e.target.selectionStart;
    const upToCursor = value.slice(0, cursor);
    const match = upToCursor.match(/(?:^|\s)@([\w-]*)$/);
    if (match) {
      setMention({ start: cursor - match[1].length, query: match[1].toLowerCase() });
      // Reset highlight to first option whenever the query changes.
      setHighlightedIdx(0);
    } else {
      setMention(null);
    }
  }

  function pickMention(handle: string) {
    if (!mention) return;
    const before = body.slice(0, mention.start);
    const after = body.slice(mention.start + mention.query.length);
    const inserted = `${handle.replace(/^@/, "")} `;
    const next = before + inserted + after;
    setBody(next);
    setMention(null);
    requestAnimationFrame(() => {
      const ta = textareaRef.current;
      if (ta) {
        const pos = before.length + inserted.length;
        ta.focus();
        ta.setSelectionRange(pos, pos);
      }
    });
  }

  async function handleSend() {
    const trimmed = body.trim();
    if (!trimmed || submitting || disabled) return;
    // Clear the composer optimistically so the user can keep typing
    // the next thought while the agent's reply is still in flight.
    // If the send actually fails (network drop, conductor down), we
    // put the text back so they don't lose what they typed.
    setSubmitting(true);
    setBody("");
    setMention(null);
    const ta = textareaRef.current;
    if (ta) ta.style.height = "auto";
    try {
      await onSend(trimmed);
    } catch (err) {
      // Restore the body so the user can retry (or copy out their text).
      setBody(trimmed);
      // Re-throw so the caller can surface a toast / error state.
      throw err;
    } finally {
      setSubmitting(false);
    }
  }

  const filteredParticipants = mention
    ? participants
        .filter((p) => p.transport === "cli")
        .filter((p) => p.handle.toLowerCase().slice(1).startsWith(mention.query))
        .slice(0, 8)
    : [];

  // Keep the highlight in-bounds whenever the filtered set shrinks.
  useEffect(() => {
    if (mention && highlightedIdx >= filteredParticipants.length) {
      setHighlightedIdx(Math.max(0, filteredParticipants.length - 1));
    }
  }, [mention, highlightedIdx, filteredParticipants.length]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Mention popover takes priority over the textarea's own keys.
    if (mention && filteredParticipants.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setHighlightedIdx((i) => (i + 1) % filteredParticipants.length);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setHighlightedIdx(
          (i) => (i - 1 + filteredParticipants.length) % filteredParticipants.length,
        );
        return;
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        const pick = filteredParticipants[highlightedIdx] ?? filteredParticipants[0];
        if (pick) pickMention(pick.handle);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setMention(null);
        return;
      }
    }
    // No mention popover open — apply the user's chosen send-key behaviour.
    if (e.key === "Enter" && sendKey === "enter" && !e.shiftKey) {
      // Send on Enter; Shift+Enter inserts a newline (Slack/Discord style).
      e.preventDefault();
      void handleSend();
      return;
    }
    // `sendKey === "button"` — Enter inserts a newline, send is button-only
    // (D11 default). Shift+Enter behaves the same.
  }

  return (
    // The composer wraps an inset "input card" so the user sees the
    // chat area, then a clear visual gap, then a discrete input zone.
    // Outer wrapper carries the top-edge separation from the message
    // scroll; the inner card is where you type.
    <div className="relative border-t border-border-default bg-recessed/60 px-3 py-3">
      {mention && filteredParticipants.length > 0 ? (
        <div
          className="absolute bottom-full left-3 mb-2 max-w-sm rounded-md border border-border-default bg-elevated shadow-md"
          // Don't steal focus when the user clicks inside — the textarea
          // stays focused so the keyboard navigation keeps working.
          onMouseDown={(e) => e.preventDefault()}
        >
          <ul className="py-1">
            {filteredParticipants.map((p, idx) => {
              const isHighlighted = idx === highlightedIdx;
              return (
                <li key={p.handle}>
                  <button
                    type="button"
                    onClick={() => pickMention(p.handle)}
                    onMouseEnter={() => setHighlightedIdx(idx)}
                    className={cn(
                      "flex w-full items-center justify-between gap-3 px-3 py-1.5 text-left text-sm",
                      isHighlighted
                        ? "bg-accent-primary-weak text-accent-primary"
                        : "hover:bg-recessed text-fg-primary",
                    )}
                  >
                    <span className="font-medium">{p.handle}</span>
                    <span
                      className={cn(
                        "text-[11px]",
                        isHighlighted ? "text-accent-primary/80" : "text-fg-tertiary",
                      )}
                    >
                      {p.display_name || ""}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
          <div className="border-t border-border-default px-3 py-1 text-[10px] text-fg-tertiary">
            <kbd className="font-sans">↑↓</kbd> to navigate · <kbd className="font-sans">Enter</kbd>{" "}
            or <kbd className="font-sans">Tab</kbd> to insert · <kbd className="font-sans">Esc</kbd>{" "}
            to close
          </div>
        </div>
      ) : null}

      <div className="rounded-lg border border-border-default bg-elevated shadow-sm">
        <div className="flex items-end gap-2 px-2 py-1.5">
          <textarea
            ref={textareaRef}
            value={body}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled || submitting}
            rows={1}
            className={cn(
              "min-h-[32px] flex-1 resize-none rounded-md border-0",
              "bg-transparent px-2 py-1.5 text-sm text-fg-primary placeholder:text-fg-tertiary",
              "focus:outline-none focus:ring-0",
              disabled && "cursor-not-allowed opacity-60",
            )}
          />
          <Tooltip label="Send message" side="top" align="end">
            <Button
              variant="primary"
              size="md"
              onClick={() => void handleSend()}
              disabled={!body.trim() || submitting || disabled}
              aria-label="Send message"
            >
              <Send size={14} strokeWidth={2.5} />
            </Button>
          </Tooltip>
        </div>
      </div>
      {/* Per-setting keyboard hint. Doubles as a sanity check: if you
          change the setting and this line flips, the wiring is good. */}
      <p className="mt-1.5 px-1 text-[10px] text-fg-tertiary">
        {sendKey === "enter" ? (
          <>
            <kbd className="font-sans">Enter</kbd> to send ·{" "}
            <kbd className="font-sans">Shift+Enter</kbd> for newline
          </>
        ) : (
          <>
            <kbd className="font-sans">Enter</kbd> for newline · click send to submit
          </>
        )}
      </p>
    </div>
  );
}
