import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type Variant = "neutral" | "primary" | "success" | "warning" | "danger" | "muted";

export type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  variant?: Variant;
};

const variants: Record<Variant, string> = {
  neutral: "bg-recessed text-fg-secondary",
  primary: "bg-accent-primary-weak text-accent-primary",
  success: "bg-accent-success-weak text-accent-success",
  warning: "bg-accent-warning-weak text-accent-warning",
  danger: "bg-accent-danger-weak text-accent-danger",
  muted: "bg-accent-muted-weak text-accent-muted",
};

export function Badge({ className, variant = "neutral", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-3 py-0.5 text-xs font-medium",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
