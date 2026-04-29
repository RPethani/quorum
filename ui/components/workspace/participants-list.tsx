"use client";

import { HandleAvatar } from "@/components/design-system/handle-avatar";
import { Badge } from "@/components/ui/badge";
import type { ParticipantRow } from "@/lib/api/conductor";
import { cn } from "@/lib/utils";

export function ParticipantsList({
  participants,
  className,
}: {
  participants: ParticipantRow[];
  className?: string;
}) {
  if (!participants.length) {
    return (
      <p className={cn("text-sm text-fg-tertiary px-4 py-4", className)}>
        No participants registered.
      </p>
    );
  }
  return (
    <ul className={cn("flex flex-col gap-2 px-4", className)}>
      {participants.map((p) => {
        const live = liveLabel(p);
        return (
          <li key={p.handle} className="flex items-center gap-3">
            <HandleAvatar handle={p.handle} size="sm" />
            <div className="flex flex-1 flex-col min-w-0">
              <span className="text-sm font-medium truncate">{p.display_name || p.handle}</span>
              <span className="font-mono text-xs text-fg-tertiary truncate">
                {p.handle} · {p.transport}
              </span>
              {live.note ? (
                <span className="mt-0.5 text-xs text-accent-danger truncate" title={live.note}>
                  {live.note}
                </span>
              ) : null}
            </div>
            <Badge variant={live.variant}>{live.label}</Badge>
          </li>
        );
      })}
    </ul>
  );
}

function liveLabel(p: ParticipantRow): {
  label: string;
  note: string;
  variant: "neutral" | "success" | "warning" | "danger";
} {
  const live = p.live_health;
  if (live && live.transport === "cli") {
    if (live.on_path === true) return { label: "ready", note: "", variant: "success" };
    if (live.on_path === false) {
      return {
        label: "unreachable",
        note: live.note || "CLI not on PATH",
        variant: "danger",
      };
    }
  }
  if (live && live.transport !== "cli") {
    return { label: live.transport, note: "", variant: "neutral" };
  }
  return { label: p.health || "unknown", note: "", variant: "neutral" };
}
