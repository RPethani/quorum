"use client";

import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

/**
 * Every flow node is wrapped in a fixed-width column so the React
 * Flow bounding boxes are identical and their centers line up at the
 * same x. With consistent centers, edges between consecutive nodes
 * stay perfectly vertical (per the layout in
 * `system-flow-diagram.tsx`).
 *
 * Content is centered inside the frame; long children (like the doc
 * gallery's horizontal strip) scroll within their natural bounds.
 */
export const COLUMN_WIDTH = 640;

export function NodeFrame({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      style={{ width: COLUMN_WIDTH }}
      className={cn("flex items-center justify-center", className)}
    >
      {children}
    </div>
  );
}
