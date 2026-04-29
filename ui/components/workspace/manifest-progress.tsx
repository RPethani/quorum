import { Badge } from "@/components/ui/badge";
import type { ManifestProgress } from "@/lib/api/conductor";
import { cn } from "@/lib/utils";
import { CircleCheck, CircleDot } from "lucide-react";

export function ManifestProgressBar({
  progress,
  className,
}: {
  progress: ManifestProgress | null;
  className?: string;
}) {
  if (!progress) {
    return <p className={cn("text-sm text-fg-tertiary", className)}>No manifest progress yet.</p>;
  }
  const total = Math.max(progress.total_artifacts, 1);
  const pct = (progress.artifacts_complete / total) * 100;
  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">Outcome manifest</span>
        <Badge
          variant={
            progress.status === "LOCKED"
              ? "success"
              : progress.status === "READY"
                ? "primary"
                : "neutral"
          }
        >
          {progress.status}
        </Badge>
      </div>
      <div className="h-1.5 w-full rounded-full bg-recessed">
        <div
          className="h-full rounded-full bg-accent-success transition-all duration-300"
          style={{ width: `${Math.round(pct)}%` }}
        />
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs text-fg-secondary">
        <div className="flex items-center gap-1.5">
          <CircleCheck size={12} className="text-accent-success" />
          {progress.artifacts_complete} complete
        </div>
        <div className="flex items-center gap-1.5">
          <CircleDot size={12} className="text-accent-primary" />
          {progress.artifacts_in_production} in production
        </div>
        <div className="flex items-center gap-1.5">
          <span className="font-mono">{progress.artifacts_pending}</span>
          pending
        </div>
        <div className="flex items-center gap-1.5">
          <span className="font-mono">{progress.total_artifacts}</span>
          total
        </div>
      </div>
      {progress.closing_ceremony_eligible ? (
        <p className="text-xs text-accent-success">Eligible for closing ceremony.</p>
      ) : null}
    </div>
  );
}
