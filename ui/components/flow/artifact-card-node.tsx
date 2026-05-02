"use client";

import { Tooltip } from "@/components/ui/tooltip";
import type { ArtifactBox } from "@/lib/flow/types";
import { cn } from "@/lib/utils";
import { Handle, Position } from "@xyflow/react";
import { Check, CircleDashed, FileText, Loader2, Slash } from "lucide-react";
import { memo } from "react";

/**
 * One artifact = one node. The S4 stage renders the row of these
 * cards horizontally with the active one positioned on the spine
 * (x=0) so the sub-flow edge above it stays perfectly vertical.
 *
 * Width is fixed at ARTIFACT_WIDTH so the layout can compute the
 * x positions of neighbours from a single offset.
 */
export const ARTIFACT_WIDTH = 112;

export type ArtifactCardData = {
  artifact: ArtifactBox;
  /** True if this artifact is the active one (sub-flow edge points to it). */
  active: boolean;
  /** "live" = active stage, "done" = past stage being inspected. */
  tone?: "live" | "done";
};

function ArtifactCardNodeImpl({ data }: { data: ArtifactCardData }) {
  const { artifact, active, tone = "live" } = data;
  return (
    <div style={{ width: ARTIFACT_WIDTH }} className={cn(tone === "done" && "opacity-70")}>
      <Handle
        type="target"
        position={Position.Top}
        className="!opacity-0 !pointer-events-none"
        isConnectable={false}
      />
      <Tooltip
        label={`${artifact.filename} — ${labelFor(artifact.state)}`}
        triggerClassName="!flex w-full"
      >
        <div
          className={cn(
            "flex flex-col items-start gap-0.5 rounded-md border px-2 py-1.5 w-full overflow-hidden",
            "transition-colors duration-150",
            toneFor(artifact.state),
            active && "ring-2 ring-accent-primary/50 shadow-md",
          )}
        >
          <div className="flex items-center gap-1">
            <StateIcon state={artifact.state} />
            <FileText size={10} className="text-fg-tertiary" strokeWidth={1.5} />
          </div>
          <p className="font-mono text-[10px] leading-tight text-fg-secondary truncate w-full text-left">
            {artifact.filename}
          </p>
          <p className="text-[9px] leading-tight text-fg-tertiary truncate w-full text-left">
            {labelFor(artifact.state)}
          </p>
        </div>
      </Tooltip>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!opacity-0 !pointer-events-none"
        isConnectable={false}
      />
    </div>
  );
}

export const ArtifactCardNode = memo(ArtifactCardNodeImpl);

function StateIcon({ state }: { state: ArtifactBox["state"] }) {
  if (state === "done")
    return <Check size={12} strokeWidth={2.5} className="text-accent-success" />;
  if (state === "active") return <Loader2 size={12} className="animate-spin text-accent-primary" />;
  if (state === "abandoned")
    return <Slash size={12} strokeWidth={2} className="text-accent-danger" />;
  return <CircleDashed size={12} strokeWidth={2} className="text-fg-tertiary" />;
}

function toneFor(state: ArtifactBox["state"]) {
  switch (state) {
    case "done":
      return "bg-accent-success-weak/30 border-accent-success/30 text-fg-secondary";
    case "active":
      return "bg-accent-primary-weak border-accent-primary/40 text-accent-primary";
    case "abandoned":
      return "bg-accent-danger-weak/40 border-accent-danger/30 text-fg-secondary";
    default:
      return "bg-canvas border-border-default text-fg-tertiary";
  }
}

function labelFor(state: ArtifactBox["state"]) {
  switch (state) {
    case "done":
      return "Done";
    case "active":
      return "In progress";
    case "abandoned":
      return "Abandoned";
    default:
      return "Pending";
  }
}
