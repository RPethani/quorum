"use client";

import { Tooltip } from "@/components/ui/tooltip";
import type { ParticipantRow, WorkspaceStateResponse } from "@/lib/api/conductor";
import { cn } from "@/lib/utils";
import { Plus } from "lucide-react";
import { ParticipantAvatar, tooltipFor } from "./participant-avatar";

/**
 * The horizontal strip directly under the main header.
 *
 *   left  — plain-text status line, items separated by `|`. Order
 *           is by user-importance (status first, what-you-must-do
 *           second, what-AIs-are-doing third, money fourth,
 *           connection last). Items show their current value at
 *           all times.
 *   right — overlapping participant avatar stack + add button.
 */
export function SecondaryHeader({
  state,
  participants,
  agentsWorking,
  questionsForYou,
  streamConnected,
  onParticipantClick,
  onAddParticipant,
}: {
  state: WorkspaceStateResponse | null;
  participants: ParticipantRow[];
  agentsWorking: number;
  questionsForYou: number;
  streamConnected: boolean;
  onParticipantClick: (handle: string) => void;
  onAddParticipant: () => void;
}) {
  const cost = state?.cost ?? null;
  const costPct = cost ? Math.round((cost.fraction || 0) * 100) : 0;
  const stateValue = stateToLabel(state?.state);
  return (
    <div className="flex items-center justify-between gap-4 border-b border-border-default bg-recessed px-6 py-1.5 min-h-[40px]">
      <ul className="flex items-center divide-x divide-border-default text-[12px]">
        <Item
          label="Status"
          value={stateValue}
          tone={state?.state === "ACTIVE" ? "default" : "warning"}
          tooltip="Workspace lifecycle state"
        />
        <Item
          label="Awaiting your input"
          value={`${questionsForYou}`}
          tone={questionsForYou > 0 ? "warning" : "default"}
          tooltip="Open questions waiting on a human answer"
        />
        <Item
          label="AI activity"
          value={`${agentsWorking}`}
          tone={agentsWorking > 0 ? "primary" : "default"}
          tooltip="Participants currently dispatching a move"
        />
        <Item
          label="Spend"
          value={
            cost
              ? `$${cost.spent_usd.toFixed(2)} of $${cost.ceiling_usd.toFixed(0)} (${costPct}%)`
              : "—"
          }
          tone={costPct > 80 ? "warning" : "default"}
          tooltip="Total spend over the cost ceiling"
        />
        <Item
          label="Stream"
          value={streamConnected ? "Live" : "Offline"}
          tone={streamConnected ? "default" : "warning"}
          tooltip={
            streamConnected
              ? "Live event stream connected"
              : "Lost the live stream — falling back to polling"
          }
        />
      </ul>
      <ParticipantStack
        participants={participants}
        onParticipantClick={onParticipantClick}
        onAddParticipant={onAddParticipant}
      />
    </div>
  );
}

function Item({
  label,
  value,
  tone,
  tooltip,
}: {
  label: string;
  value: string;
  tone: "default" | "primary" | "warning";
  tooltip: string;
}) {
  const valueClass = {
    default: "text-fg-primary",
    primary: "text-accent-primary",
    warning: "text-accent-warning",
  }[tone];
  return (
    <li className="px-3 first:pl-0 last:pr-0">
      <Tooltip label={tooltip} side="bottom" align="center">
        <span className="inline-flex items-baseline gap-1.5 cursor-help">
          <span className="text-fg-tertiary">{label}:</span>
          <span className={cn("font-medium tabular-nums", valueClass)}>{value}</span>
        </span>
      </Tooltip>
    </li>
  );
}

function ParticipantStack({
  participants,
  onParticipantClick,
  onAddParticipant,
}: {
  participants: ParticipantRow[];
  onParticipantClick: (handle: string) => void;
  onAddParticipant: () => void;
}) {
  return (
    <div className="flex items-center">
      <ul className="flex items-center -space-x-2">
        {participants.map((p) => (
          <li key={p.handle} className="relative">
            <Tooltip label={tooltipFor(p)} side="bottom" align="center">
              <button
                type="button"
                onClick={() => onParticipantClick(p.handle)}
                aria-label={tooltipFor(p)}
                className="block rounded-full transition-transform hover:translate-y-[-1px] hover:z-10"
              >
                <ParticipantAvatar participant={p} />
              </button>
            </Tooltip>
          </li>
        ))}
      </ul>
      <Tooltip label="Add a participant" side="bottom" align="end">
        <button
          type="button"
          onClick={onAddParticipant}
          aria-label="Add a participant"
          className="ml-2 inline-flex h-6 w-6 items-center justify-center rounded-full border border-dashed border-border-default text-fg-tertiary hover:border-accent-primary hover:text-accent-primary transition-colors"
        >
          <Plus size={12} strokeWidth={2.5} />
        </button>
      </Tooltip>
    </div>
  );
}

function stateToLabel(state: string | undefined): string {
  if (!state) return "—";
  if (state === "ACTIVE") return "Active";
  if (state === "PAUSED") return "Paused";
  if (state === "INITIALIZED") return "Setup needed";
  if (state === "ARCHIVED") return "Archived";
  return state;
}
