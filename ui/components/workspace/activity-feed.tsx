"use client";

import type { EventRecord } from "@/lib/api/conductor";
import { formatLocalTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { detectVendorFromHandle, vendorColor } from "@/lib/vendor";
import { Activity } from "lucide-react";

const _TYPE_LABEL: Record<string, string> = {
  routing_decision: "routed",
  agent_started: "started",
  agent_completed: "completed",
  agent_failed: "failed",
  validation_failed: "validation failed",
  move_appended: "appended",
};

export function ActivityFeed({
  events,
  className,
}: {
  events: EventRecord[];
  className?: string;
}) {
  if (!events.length) {
    return (
      <div className={cn("flex flex-col items-center justify-center text-center py-10", className)}>
        <Activity size={28} className="text-fg-tertiary mb-2" strokeWidth={1.5} />
        <p className="text-sm text-fg-tertiary">No activity yet.</p>
      </div>
    );
  }
  return (
    <ul className={cn("divide-y divide-border-default", className)}>
      {events
        .slice()
        .reverse()
        .map((e, i) => {
          const handle = (e.handle as string | undefined) ?? "";
          const handleColor = handle ? vendorColor(detectVendorFromHandle(handle)) : undefined;
          return (
            <li
              key={`${e.ts ?? "?"}-${i}-${e.type}`}
              className="px-4 py-2 text-xs text-fg-secondary"
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-mono text-fg-tertiary tabular-nums">
                  {formatLocalTime(e.ts as string | undefined)}
                </span>
                <span className="font-mono uppercase tracking-wide text-fg-tertiary">
                  {_TYPE_LABEL[e.type] ?? e.type}
                </span>
              </div>
              <p className="mt-0.5 truncate text-fg-primary">
                {handle ? (
                  <>
                    <span style={{ color: handleColor }} className="font-mono font-medium">
                      {handle}
                    </span>
                    <span> {summariseEventTail(e)}</span>
                  </>
                ) : (
                  summariseEvent(e)
                )}
              </p>
            </li>
          );
        })}
    </ul>
  );
}

function summariseEvent(e: EventRecord): string {
  // Fallback when no handle is present — render the original sentence.
  const handle = (e.handle as string | undefined) ?? "?";
  const role = (e.role as string | undefined) ?? "";
  const moveType = (e.move_type as string | undefined) ?? "";
  const delib = (e.deliberation_id as string | undefined) ?? "";
  switch (e.type) {
    case "routing_decision":
      return `${handle} as ${role} on #${delib} (layer ${e.layer ?? "?"})`;
    case "agent_started":
      return `${handle} → ${moveType} on #${delib}${e.attempt ? ` (attempt ${e.attempt})` : ""}`;
    case "agent_completed":
      return `${handle} ✓ ${moveType} on #${delib} (${(e.duration_s as number)?.toFixed?.(1) ?? "?"}s)`;
    case "agent_failed":
      return `${handle} ✗ ${moveType} on #${delib} — ${e.reason ?? ""}`;
    case "validation_failed":
      return `${handle} validation failed on #${delib}`;
    case "move_appended":
      return `${moveType} appended to #${delib} by ${handle}`;
    default:
      return JSON.stringify(e);
  }
}

/**
 * Same as `summariseEvent` but with the leading handle dropped — used
 * when the handle is rendered separately so we can colour it.
 */
function summariseEventTail(e: EventRecord): string {
  const role = (e.role as string | undefined) ?? "";
  const moveType = (e.move_type as string | undefined) ?? "";
  const delib = (e.deliberation_id as string | undefined) ?? "";
  switch (e.type) {
    case "routing_decision":
      return `as ${role} on #${delib} (layer ${e.layer ?? "?"})`;
    case "agent_started":
      return `→ ${moveType} on #${delib}${e.attempt ? ` (attempt ${e.attempt})` : ""}`;
    case "agent_completed":
      return `✓ ${moveType} on #${delib} (${(e.duration_s as number)?.toFixed?.(1) ?? "?"}s)`;
    case "agent_failed":
      return `✗ ${moveType} on #${delib} — ${e.reason ?? ""}`;
    case "validation_failed":
      return `validation failed on #${delib}`;
    case "move_appended":
      return `appended ${moveType} to #${delib}`;
    default:
      return JSON.stringify(e);
  }
}
