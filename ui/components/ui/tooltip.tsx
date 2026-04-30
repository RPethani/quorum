"use client";

import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

/**
 * Lightweight CSS-only tooltip. Wraps any trigger element and renders
 * a small label above (or below) it on hover/focus.
 *
 * Why not the native `title` attribute? Browsers delay the native
 * tooltip ~700–1500ms — too slow for icon-only chrome where the user
 * needs immediate confirmation of what an icon does. This component
 * renders a CSS-driven label that fades in over ~120ms with no
 * JavaScript-side delay, while the trigger keeps its `title` and
 * `aria-label` for accessibility fallback.
 *
 * No portal — the tooltip is positioned relative to the trigger.
 * Make sure the trigger isn't inside an `overflow: hidden` parent
 * that would clip a tooltip rendered above it. (Most chrome rows
 * are fine; if you hit clipping, position with `side="bottom"` or
 * raise the parent's `overflow` setting.)
 */
export function Tooltip({
  label,
  side = "bottom",
  align = "center",
  className,
  children,
}: {
  label: string;
  side?: "top" | "bottom";
  align?: "start" | "center" | "end";
  className?: string;
  children: ReactNode;
}) {
  const sideClass = side === "top" ? "bottom-full mb-1.5" : "top-full mt-1.5";
  const alignClass = {
    start: "left-0",
    center: "left-1/2 -translate-x-1/2",
    end: "right-0",
  }[align];
  return (
    <span className="group relative inline-flex">
      {children}
      <span
        role="tooltip"
        className={cn(
          "pointer-events-none absolute z-50 whitespace-nowrap",
          "rounded-md border border-border-default bg-elevated px-2 py-1",
          "text-[11px] font-medium text-fg-primary shadow-md",
          "opacity-0 transition-opacity duration-100",
          "group-hover:opacity-100 group-focus-within:opacity-100",
          sideClass,
          alignClass,
          className,
        )}
      >
        {label}
      </span>
    </span>
  );
}
