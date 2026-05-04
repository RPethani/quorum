"use client";

import { Tooltip } from "@/components/ui/tooltip";
import {
  type CanvasArtifactDetail,
  type CanvasArtifactSummary,
  deleteCanvasArtifact,
} from "@/lib/api/canvas";
import { cn } from "@/lib/utils";
import { FileText, X } from "lucide-react";
import { useMemo } from "react";

/**
 * Right pane of the canvas — one live artifact at a time, with a tab
 * strip to switch when there are several. Read-only (D7 — humans
 * never edit artifacts directly; AI is the writer).
 */
export function ArtifactPane({
  artifacts,
  active,
  prevBody,
  activeFilename,
  onSelect,
  onAfterDelete,
}: {
  artifacts: CanvasArtifactSummary[];
  active: CanvasArtifactDetail | null;
  prevBody: string | null;
  activeFilename: string | null;
  onSelect: (filename: string | null) => void;
  onAfterDelete?: () => void;
}) {
  // Auto-select the first artifact if none is active and at least one exists.
  const effectiveActive = activeFilename ?? (artifacts.length > 0 ? artifacts[0].filename : null);

  if (artifacts.length === 0) {
    return <ArtifactEmpty />;
  }

  return (
    <div className="flex h-full flex-col">
      <ArtifactTabs
        artifacts={artifacts}
        activeFilename={effectiveActive}
        onSelect={onSelect}
        onAfterDelete={onAfterDelete}
      />
      <div className="flex-1 overflow-y-auto">
        {active ? (
          <ArtifactBody detail={active} prevBody={prevBody} />
        ) : (
          <div className="flex h-full items-center justify-center px-6 text-center text-sm text-fg-tertiary">
            Select an artifact tab to view it.
          </div>
        )}
      </div>
    </div>
  );
}

function ArtifactTabs({
  artifacts,
  activeFilename,
  onSelect,
  onAfterDelete,
}: {
  artifacts: CanvasArtifactSummary[];
  activeFilename: string | null;
  onSelect: (filename: string | null) => void;
  onAfterDelete?: () => void;
}) {
  async function handleDelete(filename: string) {
    try {
      await deleteCanvasArtifact(filename);
      if (activeFilename === filename) onSelect(null);
      onAfterDelete?.();
    } catch {
      // best-effort; SSE refresh will sync on next tick
    }
  }

  return (
    <div className="flex items-center gap-1 overflow-x-auto border-b border-border-default bg-elevated px-2 py-1.5">
      {artifacts.map((a) => {
        const active = a.filename === activeFilename;
        return (
          <Tooltip
            key={a.filename}
            label={`${a.filename} — ${_humanSize(a.size)}`}
            triggerClassName="!inline-flex"
          >
            <div
              className={cn(
                "group inline-flex shrink-0 items-center gap-1 rounded-md border px-2 py-1 text-[11px]",
                active
                  ? "border-accent-primary/50 bg-accent-primary-weak text-accent-primary"
                  : "border-border-default bg-canvas text-fg-secondary hover:bg-recessed",
              )}
            >
              <button
                type="button"
                onClick={() => onSelect(a.filename)}
                className="inline-flex items-center gap-1 font-mono"
              >
                <FileText size={11} strokeWidth={1.5} />
                <span className="max-w-[160px] truncate">{a.filename}</span>
              </button>
              <button
                type="button"
                aria-label={`Delete ${a.filename}`}
                onClick={() => void handleDelete(a.filename)}
                className="rounded-sm p-0.5 text-fg-tertiary opacity-0 transition-opacity hover:bg-recessed hover:text-fg-primary group-hover:opacity-100"
              >
                <X size={11} strokeWidth={2.5} />
              </button>
            </div>
          </Tooltip>
        );
      })}
    </div>
  );
}

function ArtifactBody({
  detail,
  prevBody,
}: {
  detail: CanvasArtifactDetail;
  prevBody: string | null;
}) {
  // We render the markdown body verbatim in a styled <pre> for MVP.
  // A full markdown pretty-renderer (`react-markdown`) will land in
  // a polish pass — for now plain text is the most predictable view.
  const showDiff = prevBody !== null && prevBody !== detail.body;
  return (
    <div className="px-4 py-3">
      <header className="mb-3 flex items-baseline justify-between gap-2">
        <h3 className="font-mono text-xs text-fg-secondary">{detail.filename}</h3>
        <span className="text-[10px] text-fg-tertiary tabular-nums">
          {_humanSize(detail.size)} · {_relTime(detail.modified_at)}
        </span>
      </header>

      {showDiff ? (
        <DiffView before={prevBody ?? ""} after={detail.body} />
      ) : (
        <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-fg-primary">
          {detail.body}
        </pre>
      )}
    </div>
  );
}

/**
 * Tiny line-level diff renderer. We add `react-diff-viewer-continued`
 * in a polish pass; for MVP this is a 30-line greedy LCS-like
 * implementation that's good enough for "spot the change."
 */
function DiffView({ before, after }: { before: string; after: string }) {
  const lines = useMemo(() => _diffLines(before, after), [before, after]);
  return (
    <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">
      {lines.map((l, i) => (
        <div
          key={`${l.kind}:${i}:${l.text.slice(0, 40)}`}
          className={cn(
            "px-1",
            l.kind === "add" && "bg-accent-success-weak/40 text-fg-primary",
            l.kind === "remove" && "bg-accent-danger-weak/40 text-fg-secondary line-through",
            l.kind === "same" && "text-fg-primary",
          )}
        >
          <span className="mr-1 select-none text-fg-tertiary">
            {l.kind === "add" ? "+" : l.kind === "remove" ? "−" : " "}
          </span>
          {l.text || " "}
        </div>
      ))}
    </pre>
  );
}

type DiffLine = { kind: "add" | "remove" | "same"; text: string };

function _diffLines(before: string, after: string): DiffLine[] {
  const a = before.split("\n");
  const b = after.split("\n");
  // Quick LCS via dp table — fine for files of a few hundred lines.
  const m = a.length;
  const n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const out: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < m && j < n) {
    if (a[i] === b[j]) {
      out.push({ kind: "same", text: a[i] });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ kind: "remove", text: a[i] });
      i++;
    } else {
      out.push({ kind: "add", text: b[j] });
      j++;
    }
  }
  while (i < m) out.push({ kind: "remove", text: a[i++] });
  while (j < n) out.push({ kind: "add", text: b[j++] });
  return out;
}

function ArtifactEmpty() {
  return (
    <div className="flex h-full items-center justify-center px-6 text-center">
      <p className="max-w-xs text-sm text-fg-tertiary">
        Artifacts will appear here when an AI starts maintaining one. Ask any participant to "track
        this in a doc as we go" and they will create one for you.
      </p>
    </div>
  );
}

function _humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function _relTime(iso: string): string {
  try {
    const t = new Date(iso).getTime();
    const delta = (Date.now() - t) / 1000;
    if (delta < 60) return "just now";
    if (delta < 3600) return `${Math.round(delta / 60)}m ago`;
    if (delta < 86400) return `${Math.round(delta / 3600)}h ago`;
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}
