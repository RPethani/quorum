"use client";

import { Button } from "@/components/ui/button";
import type { SetupCheck } from "@/lib/flow/types";
import { cn } from "@/lib/utils";
import { Handle, Position } from "@xyflow/react";
import { AlertTriangle, Check, Info, X } from "lucide-react";
import { memo } from "react";
import { NodeFrame } from "./node-frame";

/**
 * S2 setup checklist node. One row per check (problem statement,
 * participants, context). Surfaces a "Start collaboration" button at
 * the bottom that's enabled only when the locked S2→S3 bar is met.
 */
export type SetupChecklistData = {
  checks: SetupCheck[];
  startReady: boolean;
  onStart?: () => void;
  /** "live" = active stage, "done" = past stage being inspected. */
  tone?: "live" | "done";
};

function SetupChecklistNodeImpl({ data }: { data: SetupChecklistData }) {
  const tone = data.tone ?? "live";
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
          "rounded-md border border-border-default bg-elevated p-3 min-w-[320px] shadow-sm",
          tone === "done" && "opacity-70",
        )}
      >
        <ul className="flex flex-col gap-1.5">
          {data.checks.map((c) => (
            <li key={c.id} className="flex items-center gap-2 text-xs">
              <Icon state={c.state} />
              <span className="font-medium text-fg-primary">{c.label}</span>
              {c.detail ? <span className="text-fg-tertiary truncate">— {c.detail}</span> : null}
            </li>
          ))}
        </ul>
        <div className="mt-3">
          <Button
            variant="primary"
            size="sm"
            disabled={!data.startReady}
            onClick={() => data.onStart?.()}
          >
            Start collaboration
          </Button>
        </div>
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

export const SetupChecklistNode = memo(SetupChecklistNodeImpl);

function Icon({ state }: { state: SetupCheck["state"] }) {
  const cls = "shrink-0";
  switch (state) {
    case "pass":
      return <Check size={14} strokeWidth={2.5} className={cn(cls, "text-accent-success")} />;
    case "fail":
      return <X size={14} strokeWidth={2.5} className={cn(cls, "text-accent-danger")} />;
    case "warn":
      return <AlertTriangle size={14} strokeWidth={2} className={cn(cls, "text-accent-warning")} />;
    case "info":
      return <Info size={14} strokeWidth={2} className={cn(cls, "text-fg-tertiary")} />;
  }
}
