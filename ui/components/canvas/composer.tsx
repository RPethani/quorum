"use client";

import { Button } from "@/components/ui/button";
import type { ParticipantRow } from "@/lib/api/conductor";
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
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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
    setSubmitting(true);
    try {
      await onSend(trimmed);
      setBody("");
      setMention(null);
      const ta = textareaRef.current;
      if (ta) ta.style.height = "auto";
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

  return (
    <div className="relative border-t border-border-default bg-elevated">
      {mention && filteredParticipants.length > 0 ? (
        <div className="absolute bottom-full left-3 mb-2 max-w-sm rounded-md border border-border-default bg-elevated shadow-md">
          <ul className="py-1">
            {filteredParticipants.map((p) => (
              <li key={p.handle}>
                <button
                  type="button"
                  onClick={() => pickMention(p.handle)}
                  className="flex w-full items-center justify-between gap-3 px-3 py-1.5 text-left text-sm hover:bg-recessed"
                >
                  <span className="font-medium text-fg-primary">{p.handle}</span>
                  <span className="text-[11px] text-fg-tertiary">{p.display_name || ""}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="flex items-end gap-2 px-3 py-2">
        <textarea
          ref={textareaRef}
          value={body}
          onChange={handleChange}
          placeholder={placeholder}
          disabled={disabled || submitting}
          rows={1}
          className={cn(
            "min-h-[36px] flex-1 resize-none rounded-md border border-border-default",
            "bg-canvas px-3 py-2 text-sm text-fg-primary placeholder:text-fg-tertiary",
            "focus:outline-none focus:ring-2 focus:ring-accent-primary/30",
            disabled && "cursor-not-allowed opacity-60",
          )}
        />
        <Button
          variant="primary"
          size="md"
          onClick={() => void handleSend()}
          disabled={!body.trim() || submitting || disabled}
          aria-label="Send message"
        >
          <Send size={14} strokeWidth={2.5} />
        </Button>
      </div>
    </div>
  );
}
