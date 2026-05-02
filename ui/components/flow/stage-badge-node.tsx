"use client";

import { STAGE_LABEL, type StageId, type StepState } from "@/lib/flow/types";
import { cn } from "@/lib/utils";
import { Handle, Position } from "@xyflow/react";
import { Check, CircleDashed, Loader2 } from "lucide-react";
import { memo } from "react";
import { NodeFrame } from "./node-frame";

/**
 * One node per master-flow stage in the top-level chain. Renders as
 * a compact pill in collapsed form; the active stage's pill carries
 * a pulse ring; clicking a non-active stage toggles its expansion
 * state (handled by the parent diagram).
 */
export type StageBadgeData = {
  stage: StageId;
  state: StepState;
  expanded: boolean;
  onToggle?: (stage: StageId) => void;
};

function StageBadgeNodeImpl({ data }: { data: StageBadgeData }) {
  const { stage, state, expanded, onToggle } = data;
  const label = STAGE_LABEL[stage];

  const tone = toneFor(state);

  return (
    <NodeFrame>
      <Handle
        type="target"
        position={Position.Top}
        className="!opacity-0 !pointer-events-none"
        isConnectable={false}
      />
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onToggle?.(stage);
        }}
        onMouseDown={(e) => e.stopPropagation()}
        className={cn(
          // `nodrag` / `nopan` opt out of React Flow's drag/pan
          // capture so the click reaches our handler.
          "nodrag nopan",
          "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium",
          "transition-colors duration-150 cursor-pointer",
          tone.bg,
          tone.text,
          tone.border,
          state === "active" && "shadow-sm",
          expanded && "ring-2 ring-accent-primary/30",
        )}
      >
        <StateIcon state={state} />
        <span>{label}</span>
      </button>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!opacity-0 !pointer-events-none"
        isConnectable={false}
      />
    </NodeFrame>
  );
}

export const StageBadgeNode = memo(StageBadgeNodeImpl);

function StateIcon({ state }: { state: StepState }) {
  if (state === "done") return <Check size={12} strokeWidth={2.5} />;
  if (state === "active") return <Loader2 size={12} className="animate-spin" />;
  if (state === "failed") return <span className="h-2 w-2 rounded-full bg-accent-danger" />;
  return <CircleDashed size={12} strokeWidth={2} />;
}

function toneFor(state: StepState): { bg: string; text: string; border: string } {
  switch (state) {
    case "active":
      return {
        bg: "bg-accent-primary-weak",
        text: "text-accent-primary",
        border: "border-accent-primary/50",
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
        border: "border-accent-danger/50",
      };
    case "skipped":
      return {
        bg: "bg-recessed",
        text: "text-fg-tertiary",
        border: "border-border-default",
      };
    default:
      return {
        bg: "bg-canvas",
        text: "text-fg-tertiary",
        border: "border-border-default",
      };
  }
}
