"use client";

import { Badge } from "@/components/ui/badge";
import type { DeliberationListItem } from "@/lib/api/conductor";
import { cn } from "@/lib/utils";

export function DeliberationsList({
  items,
  selectedId,
  onSelect,
  className,
}: {
  items: DeliberationListItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  className?: string;
}) {
  if (!items.length) {
    return (
      <p className={cn("text-sm text-fg-tertiary px-4 py-6", className)}>
        No deliberations yet. Run <code className="font-mono">quorum step</code> or let the loop
        bootstrap the manifest.
      </p>
    );
  }
  return (
    <ul className={cn("flex flex-col", className)}>
      {items.map((d) => (
        <li key={d.id}>
          <button
            type="button"
            onClick={() => onSelect(d.id)}
            className={cn(
              "w-full text-left px-4 py-3 border-b border-border-default transition-colors duration-100",
              selectedId === d.id
                ? "bg-accent-primary-weak text-fg-primary"
                : "hover:bg-recessed text-fg-primary",
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-xs text-fg-tertiary">#{d.id}</span>
              <div className="flex items-center gap-1.5">
                {d.human_pending > 0 ? (
                  <Badge variant="warning">{d.human_pending} for you</Badge>
                ) : null}
                <Badge variant={badgeForState(d.status)}>{d.status}</Badge>
              </div>
            </div>
            <p className="mt-1 text-sm font-medium leading-snug">{d.title || "(untitled)"}</p>
            {d.tags.length ? (
              <p className="mt-1 text-xs text-fg-tertiary">
                {d.tags.map((t) => `#${t}`).join(" ")}
              </p>
            ) : null}
          </button>
        </li>
      ))}
    </ul>
  );
}

function badgeForState(state: string): "neutral" | "primary" | "success" | "warning" | "danger" {
  if (state === "DECIDED" || state === "COMPLETED") return "success";
  if (state.startsWith("BLOCKED") || state === "PAUSED") return "warning";
  if (state === "ARCHIVED" || state === "ABANDONED") return "danger";
  if (state === "ACTIVE" || state === "OPEN" || state === "IN_REVIEW") return "primary";
  return "neutral";
}
