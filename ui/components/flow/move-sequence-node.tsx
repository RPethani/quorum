"use client";

import { Tooltip } from "@/components/ui/tooltip";
import {
  MOVE_STEP_LABEL,
  type MoveSequence,
  type MoveStep,
  type StepState,
} from "@/lib/flow/types";
import { cn } from "@/lib/utils";
import { detectVendorFromHandle, vendorColor } from "@/lib/vendor";
import { Handle, Position } from "@xyflow/react";
import { Check, CircleDashed, Loader2 } from "lucide-react";
import { memo } from "react";
import { NodeFrame } from "./node-frame";

const STEPS: MoveStep[] = ["propose", "critique", "synthesise", "decide"];

/**
 * Shows the per-deliberation move sequence for the active stage.
 * Renders the four steps Propose → Critique → Synthesise → Decide
 * with the active step pulsing and a status-note line below.
 *
 * Used by S3, the active-deliberation slot in S4, and S5.
 */
export type MoveSequenceData = {
  sequence: MoveSequence;
  /** Optional title shown above the row of step badges. */
  title?: string;
  /** "live" = active stage, "done" = past stage being inspected. */
  tone?: "live" | "done";
};

function MoveSequenceNodeImpl({ data }: { data: MoveSequenceData }) {
  const { sequence, title, tone = "live" } = data;
  const handleColor = sequence.activeHandle
    ? vendorColor(detectVendorFromHandle(sequence.activeHandle))
    : undefined;
  return (
    <NodeFrame>
      <Handle
        type="target"
        position={Position.Top}
        className="!opacity-0 !pointer-events-none"
        isConnectable={false}
      />
      <div
        className={cn(
          "rounded-md border border-border-default bg-elevated px-3 py-2 min-w-[360px] max-w-[440px] shadow-sm",
          tone === "done" && "opacity-70",
        )}
      >
        {title ? (
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-fg-tertiary">
            {title}
          </div>
        ) : null}
        <ol className="flex items-center gap-1">
          {STEPS.map((step, i) => (
            <li key={step} className="flex items-center gap-1">
              <StepBadge
                step={step}
                state={sequence.steps[step]}
                participant={sequence.steps[step] === "active" ? sequence.activeHandle : null}
                participantColor={sequence.steps[step] === "active" ? handleColor : undefined}
                substituted={sequence.steps[step] === "active" && sequence.substituted}
              />
              {i < STEPS.length - 1 ? (
                <span
                  className={cn(
                    "h-px w-3 shrink-0",
                    sequence.steps[step] === "done" ? "bg-accent-primary/40" : "bg-border-default",
                  )}
                />
              ) : null}
            </li>
          ))}
        </ol>
        <p className="mt-2 text-[11px] text-fg-secondary">{sequence.statusNote}</p>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!opacity-0 !pointer-events-none"
        isConnectable={false}
      />
    </NodeFrame>
  );
}

export const MoveSequenceNode = memo(MoveSequenceNodeImpl);

function StepBadge({
  step,
  state,
  participant,
  participantColor,
  substituted,
}: {
  step: MoveStep;
  state: StepState;
  participant: string | null;
  participantColor?: string;
  substituted: boolean;
}) {
  const tone = toneFor(state);
  const label = MOVE_STEP_LABEL[step];
  const tooltip = participant
    ? `${label} — ${shortName(participant)}${substituted ? " (substituted)" : ""}`
    : label;
  return (
    <Tooltip label={tooltip}>
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium",
          tone.bg,
          tone.text,
          tone.border,
          state === "active" && "ring-2 ring-accent-primary/30 animate-pulse",
        )}
      >
        <StateIcon state={state} color={participantColor} />
        <span className="uppercase tracking-wider">{label}</span>
        {substituted ? (
          <span className="ml-1 rounded bg-accent-warning-weak px-1 text-[9px] text-accent-warning">
            swap
          </span>
        ) : null}
      </span>
    </Tooltip>
  );
}

function StateIcon({ state, color }: { state: StepState; color?: string }) {
  if (state === "done") return <Check size={10} strokeWidth={2.5} />;
  if (state === "active") {
    return <Loader2 size={10} className="animate-spin" style={color ? { color } : undefined} />;
  }
  if (state === "failed") return <span className="h-1.5 w-1.5 rounded-full bg-accent-danger" />;
  return <CircleDashed size={10} strokeWidth={2} />;
}

function toneFor(state: StepState) {
  switch (state) {
    case "active":
      return {
        bg: "bg-accent-primary-weak",
        text: "text-accent-primary",
        border: "border-accent-primary/40",
      };
    case "done":
      return {
        bg: "bg-recessed",
        text: "text-fg-secondary",
        border: "border-border-default",
      };
    case "failed":
      return {
        bg: "bg-accent-danger-weak",
        text: "text-accent-danger",
        border: "border-accent-danger/40",
      };
    default:
      return {
        bg: "bg-canvas",
        text: "text-fg-tertiary",
        border: "border-border-default",
      };
  }
}

function shortName(handle: string): string {
  if (!handle) return "Someone";
  const m: Record<string, string> = {
    "@claude-opus": "Claude (Opus)",
    "@claude": "Claude",
    "@gemini": "Gemini",
    "@codex": "Codex",
    "@rakesh": "You",
  };
  return m[handle] ?? handle.replace(/^@/, "");
}
