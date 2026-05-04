"use client";

import { cn } from "@/lib/utils";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

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
  triggerClassName,
  floating = false,
  children,
}: {
  label: string;
  side?: "top" | "bottom";
  align?: "start" | "center" | "end";
  /** Class names applied to the floating tooltip label. */
  className?: string;
  /**
   * Class names applied to the wrapper span around the trigger. Useful
   * when the default `inline-flex` collapses to content width and you
   * need the trigger to fill its parent (pass `!flex w-full`).
   */
  triggerClassName?: string;
  /**
   * Render the label via a `position: fixed` portal instead of an
   * absolutely-positioned descendant. Use this when the trigger sits
   * inside an `overflow: hidden|auto|scroll` ancestor (e.g. a horizontal
   * tab strip) that would otherwise clip the label.
   */
  floating?: boolean;
  children: ReactNode;
}) {
  if (floating) {
    return (
      <FloatingTooltip
        label={label}
        side={side}
        align={align}
        className={className}
        triggerClassName={triggerClassName}
      >
        {children}
      </FloatingTooltip>
    );
  }

  const sideClass = side === "top" ? "bottom-full mb-1.5" : "top-full mt-1.5";
  const alignClass = {
    start: "left-0",
    center: "left-1/2 -translate-x-1/2",
    end: "right-0",
  }[align];
  return (
    <span className={cn("group relative inline-flex", triggerClassName)}>
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

function FloatingTooltip({
  label,
  side,
  align,
  className,
  triggerClassName,
  children,
}: {
  label: string;
  side: "top" | "bottom";
  align: "start" | "center" | "end";
  className?: string;
  triggerClassName?: string;
  children: ReactNode;
}) {
  const wrapperRef = useRef<HTMLSpanElement | null>(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  function measure() {
    const el = wrapperRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const gap = 6;
    const top = side === "top" ? r.top - gap : r.bottom + gap;
    const left = align === "start" ? r.left : align === "end" ? r.right : r.left + r.width / 2;
    setPos({ top, left });
  }

  function show() {
    measure();
    setOpen(true);
  }
  function hide() {
    setOpen(false);
  }

  const transform =
    align === "start"
      ? side === "top"
        ? "translate(0, -100%)"
        : "translate(0, 0)"
      : align === "end"
        ? side === "top"
          ? "translate(-100%, -100%)"
          : "translate(-100%, 0)"
        : side === "top"
          ? "translate(-50%, -100%)"
          : "translate(-50%, 0)";

  return (
    <span
      ref={wrapperRef}
      className={cn("inline-flex", triggerClassName)}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      {mounted && open && pos
        ? createPortal(
            <span
              role="tooltip"
              style={{ position: "fixed", top: pos.top, left: pos.left, transform }}
              className={cn(
                "pointer-events-none z-[1000] whitespace-nowrap",
                "rounded-md border border-border-default bg-elevated px-2 py-1",
                "text-[11px] font-medium text-fg-primary shadow-md",
                className,
              )}
            >
              {label}
            </span>,
            document.body,
          )
        : null}
    </span>
  );
}
