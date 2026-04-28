import { cn } from "@/lib/utils";

export type CostChipProps = {
  spent: number;
  ceiling: number;
  className?: string;
};

/**
 * Running-cost display for the workspace header. Mono numerals.
 * Turns warning-colored when >80% of the ceiling is consumed.
 */
export function CostChip({ spent, ceiling, className }: CostChipProps) {
  const pct = ceiling > 0 ? spent / ceiling : 0;
  const warn = pct > 0.8;
  return (
    <div
      className={cn(
        "inline-flex items-center gap-1 rounded-sm border border-border-default bg-elevated px-2 py-1 font-mono text-xs",
        warn ? "text-accent-warning border-accent-warning" : "text-fg-secondary",
        className,
      )}
      aria-label={`Workspace cost: $${spent.toFixed(2)} of $${ceiling.toFixed(2)}`}
    >
      <span>${spent.toFixed(2)}</span>
      <span className="text-fg-tertiary">/</span>
      <span className="text-fg-tertiary">${ceiling.toFixed(2)}</span>
    </div>
  );
}
