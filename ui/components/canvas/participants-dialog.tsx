"use client";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ParticipantAvatar } from "@/components/workspace/participant-avatar";
import type { ParticipantRow } from "@/lib/api/conductor";
import { cn } from "@/lib/utils";
import { Plus } from "lucide-react";

/**
 * Participants dialog — the single place users see "who's in the
 * workspace" and the live health of each. Opens from the avatar
 * stack in the header (per the user's UX call: clicking any avatar
 * funnels here rather than a per-avatar drill-down).
 *
 * MVP scope:
 *   - List of participants with avatar + handle + display name + live status
 *   - "Add participant" button at the bottom (opens AddAgentDialog —
 *     handled by the caller)
 *   - Edit / remove rows: deferred until the conductor exposes those
 *     endpoints (today only POST /api/participants exists)
 */
export function ParticipantsDialog({
  open,
  onClose,
  participants,
  onAdd,
}: {
  open: boolean;
  onClose: () => void;
  participants: ParticipantRow[];
  onAdd: () => void;
}) {
  const cli = participants.filter((p) => p.transport === "cli");
  const human = participants.find((p) => p.transport === "manual");
  const hasAny = participants.length > 0;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Participants"
      description={
        cli.length === 0
          ? "Add at least one AI participant to start brainstorming."
          : `${cli.length} AI participant${cli.length === 1 ? "" : "s"} configured.`
      }
      size="md"
    >
      {hasAny ? (
        <ul className="flex flex-col gap-2">
          {cli.map((p) => (
            <ParticipantRowDisplay key={p.handle} participant={p} />
          ))}
          {human ? <ParticipantRowDisplay participant={human} /> : null}
        </ul>
      ) : (
        <div className="rounded-md border border-dashed border-border-default bg-canvas/50 px-4 py-8 text-center">
          <p className="text-sm text-fg-tertiary">No participants yet.</p>
        </div>
      )}

      <div className="mt-5 flex items-center justify-between gap-2 border-t border-border-default pt-4">
        <p className="text-[11px] text-fg-tertiary">
          Edit and remove via <code className="font-mono">registers/participants.md</code> for now.
        </p>
        <Button variant="primary" size="sm" onClick={onAdd}>
          <Plus size={12} strokeWidth={2.5} />
          Add participant
        </Button>
      </div>
    </Dialog>
  );
}

function ParticipantRowDisplay({ participant }: { participant: ParticipantRow }) {
  const status = _statusFor(participant);
  return (
    <li
      className={cn(
        "flex items-center gap-3 rounded-md border border-border-default bg-canvas px-3 py-2.5",
      )}
    >
      <ParticipantAvatar participant={participant} size={32} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-semibold text-fg-primary truncate">
            {participant.display_name || participant.handle}
          </span>
          <span className="text-[11px] font-mono text-fg-tertiary truncate">
            {participant.handle}
          </span>
        </div>
        {participant.cli_command ? (
          <p className="mt-0.5 truncate font-mono text-[11px] text-fg-tertiary">
            {participant.cli_command}
          </p>
        ) : null}
      </div>
      <span
        className={cn(
          "shrink-0 inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium",
          status.bg,
          status.text,
          status.border,
        )}
      >
        <span className={cn("inline-block h-1.5 w-1.5 rounded-full", status.dot)} />
        {status.label}
      </span>
    </li>
  );
}

function _statusFor(p: ParticipantRow) {
  if (p.transport === "manual") {
    return {
      label: "you",
      bg: "bg-accent-primary-weak",
      text: "text-accent-primary",
      border: "border-accent-primary/30",
      dot: "bg-accent-primary",
    };
  }
  const live = p.live_health;
  if (live?.on_path === true) {
    return {
      label: "ready",
      bg: "bg-accent-success-weak",
      text: "text-accent-success",
      border: "border-accent-success/30",
      dot: "bg-accent-success",
    };
  }
  if (live?.on_path === false) {
    return {
      label: live.note || "not reachable",
      bg: "bg-accent-danger-weak",
      text: "text-accent-danger",
      border: "border-accent-danger/30",
      dot: "bg-accent-danger",
    };
  }
  return {
    label: "unknown",
    bg: "bg-recessed",
    text: "text-fg-tertiary",
    border: "border-border-default",
    dot: "bg-fg-tertiary",
  };
}
