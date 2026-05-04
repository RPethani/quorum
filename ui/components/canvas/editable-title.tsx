"use client";

import { updateCanvasState } from "@/lib/api/canvas";
import { cn } from "@/lib/utils";
import { Pencil } from "lucide-react";
import { useEffect, useRef, useState } from "react";

/**
 * Inline-editable workspace title.
 *
 * Click the title (or the pencil) to enter edit mode; Enter saves,
 * Escape cancels, blur saves. The component is optimistic — it
 * shows the new value as soon as the user commits, then reconciles
 * with the server's response (or rolls back on error).
 */
export function EditableTitle({
  title,
  onChanged,
}: {
  title: string;
  onChanged?: (newTitle: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(title);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Re-sync local value when server pushes a new title (e.g. SSE
    // refresh). Skip while the user is mid-edit so we don't clobber
    // their typing.
    if (!editing) setDraft(title);
  }, [title, editing]);

  useEffect(() => {
    if (editing) {
      const el = inputRef.current;
      if (el) {
        el.focus();
        el.select();
      }
    }
  }, [editing]);

  async function commit() {
    const next = draft.trim();
    if (!next) {
      setDraft(title);
      setEditing(false);
      return;
    }
    if (next === title) {
      setEditing(false);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const state = await updateCanvasState({ title: next });
      setDraft(state.title);
      onChanged?.(state.title);
      setEditing(false);
    } catch (e) {
      setError(_extractError(e));
      // Stay in edit mode so the user can fix the value.
    } finally {
      setSaving(false);
    }
  }

  function cancel() {
    setDraft(title);
    setError(null);
    setEditing(false);
  }

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => setEditing(true)}
        className={cn(
          "group inline-flex items-baseline gap-1.5 rounded-sm px-1 -mx-1",
          "text-sm font-semibold text-fg-primary",
          "hover:bg-recessed/60 transition-colors",
        )}
        aria-label="Rename workspace"
      >
        <span className="truncate max-w-[60ch]">{title}</span>
        <Pencil
          size={11}
          strokeWidth={2}
          className="text-fg-tertiary opacity-0 group-hover:opacity-100 transition-opacity shrink-0 self-center"
        />
      </button>
    );
  }

  return (
    <div className="inline-flex items-center gap-2">
      <input
        ref={inputRef}
        type="text"
        value={draft}
        disabled={saving}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            void commit();
          } else if (e.key === "Escape") {
            e.preventDefault();
            cancel();
          }
        }}
        onBlur={() => void commit()}
        maxLength={200}
        className={cn(
          "rounded-sm border border-accent-primary/40 bg-canvas px-1 py-0.5",
          "text-sm font-semibold text-fg-primary",
          "focus:outline-none focus:ring-2 focus:ring-accent-primary/30",
          "min-w-[20ch]",
          saving && "opacity-60",
        )}
      />
      {error ? <span className="text-[11px] text-accent-danger">{error}</span> : null}
    </div>
  );
}

function _extractError(e: unknown): string {
  if (e instanceof Error) {
    // CanvasApiError has shape "canvas API 400: {...}". Pull the inner
    // error if we can — the user shouldn't see the envelope.
    const m = e.message.match(/^canvas API \d+:\s*(.+)$/);
    if (m) {
      try {
        const obj = JSON.parse(m[1]);
        if (typeof obj?.error === "string") return obj.error;
      } catch {
        /* fall through */
      }
      return m[1];
    }
    return e.message;
  }
  return String(e);
}
