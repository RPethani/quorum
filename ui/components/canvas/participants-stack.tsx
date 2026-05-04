"use client";

import { Tooltip } from "@/components/ui/tooltip";
import { ParticipantAvatar, tooltipFor } from "@/components/workspace/participant-avatar";
import type { ParticipantRow } from "@/lib/api/conductor";
import { cn } from "@/lib/utils";
import { Plus } from "lucide-react";

/**
 * Compact avatar stack for the workspace header.
 *
 * Reads as a single composed control: up to MAX overlapping avatars,
 * an optional `+N` chip for overflow, and a final dashed "+ slot"
 * that adds a new participant. The slot uses the same circular
 * shape and overlap pattern as the avatars so the eye sees one
 * group "people in this workspace + add another" — not two
 * unrelated affordances.
 *
 * Clicking any avatar (or the `+N` chip) opens the participants
 * dialog. Clicking the `+ slot` opens the add-agent dialog directly.
 */
export const STACK_MAX = 5;

export function ParticipantsStack({
  participants,
  onOpen,
  onAdd,
}: {
  participants: ParticipantRow[];
  onOpen: () => void;
  onAdd: () => void;
}) {
  // Filter to CLI participants — humans aren't in the registry as
  // chat-able agents and shouldn't crowd the stack.
  const visible = participants.filter((p) => p.transport === "cli");
  const shown = visible.slice(0, STACK_MAX);
  const overflow = visible.length - shown.length;

  if (visible.length === 0) {
    // Empty state is handled by the parent header (the "0 participants
    // — add one" warning button); render nothing here.
    return null;
  }

  return (
    <ul className="flex items-center -space-x-2">
      {shown.map((p) => (
        <li key={p.handle} className="relative">
          <Tooltip label={tooltipFor(p)} side="bottom" align="end">
            <button
              type="button"
              onClick={onOpen}
              aria-label={`${tooltipFor(p)} — open participants`}
              className="block rounded-full ring-2 ring-elevated transition-transform hover:scale-105"
            >
              <ParticipantAvatar participant={p} size={26} />
            </button>
          </Tooltip>
        </li>
      ))}
      {overflow > 0 ? (
        <li className="relative">
          <Tooltip label={`Show all ${visible.length} participants`} side="bottom" align="end">
            <button
              type="button"
              onClick={onOpen}
              aria-label={`Show all ${visible.length} participants`}
              className={cn(
                "inline-flex h-[26px] w-[26px] items-center justify-center rounded-full",
                "ring-2 ring-elevated border border-border-default bg-canvas",
                "text-[10px] font-semibold text-fg-secondary",
                "hover:bg-recessed hover:text-fg-primary transition-colors",
              )}
            >
              +{overflow}
            </button>
          </Tooltip>
        </li>
      ) : null}
      {/* The "+ slot" — composed visually with the stack so the eye
          reads "people here + add another" as one group. */}
      <li className="relative">
        <Tooltip label="Add participant" side="bottom" align="end">
          <button
            type="button"
            onClick={onAdd}
            aria-label="Add participant"
            className={cn(
              "inline-flex h-[26px] w-[26px] items-center justify-center rounded-full",
              "ring-2 ring-elevated border border-dashed border-border-emphasis bg-canvas",
              "text-fg-tertiary hover:bg-accent-primary-weak hover:text-accent-primary",
              "hover:border-accent-primary/60 transition-colors",
            )}
          >
            <Plus size={12} strokeWidth={2.5} />
          </button>
        </Tooltip>
      </li>
    </ul>
  );
}
