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
      {participants.map((p) => (
        <li key={p.handle} className="flex items-center gap-3">
          <HandleAvatar handle={p.handle} size="sm" />
          <div className="flex flex-1 flex-col min-w-0">
            <span className="text-sm font-medium truncate">{p.display_name || p.handle}</span>
            <span className="font-mono text-xs text-fg-tertiary truncate">
              {p.handle} · {p.transport}
            </span>
          </div>
          <Badge variant={badgeForHealth(p.health)}>{p.health}</Badge>
        </li>
      ))}
    </ul>
  );
}

function badgeForHealth(h: string): "neutral" | "success" | "warning" | "danger" {
  switch (h.toLowerCase()) {
    case "green":
      return "success";
    case "yellow":
      return "warning";
    case "red":
      return "danger";
    default:
      return "neutral";
  }
}
