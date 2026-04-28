import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export type SeparatorProps = HTMLAttributes<HTMLDivElement> & {
  orientation?: "horizontal" | "vertical";
};

export function Separator({
  className,
  orientation = "horizontal",
  ...props
}: SeparatorProps) {
  return (
    <div
      role="separator"
      aria-orientation={orientation}
      className={cn(
        "bg-border-default",
        orientation === "horizontal" ? "h-px w-full my-3" : "w-px h-full mx-3",
        className,
      )}
      {...props}
    />
  );
}
