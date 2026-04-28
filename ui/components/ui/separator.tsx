import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

export type SeparatorProps = HTMLAttributes<HTMLHRElement> & {
  orientation?: "horizontal" | "vertical";
};

export function Separator({ className, orientation = "horizontal", ...props }: SeparatorProps) {
  return (
    // <hr> is the semantically correct horizontal separator; for vertical
    // orientation the styling makes it functionally a vertical rule.
    <hr
      aria-orientation={orientation}
      className={cn(
        "border-0 bg-border-default",
        orientation === "horizontal" ? "h-px w-full my-3" : "w-px h-full mx-3",
        className,
      )}
      {...props}
    />
  );
}
