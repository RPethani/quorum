"use client";

import { Markdown } from "@/components/ui/markdown";
import { Tooltip } from "@/components/ui/tooltip";
import {
  type CanvasArtifactDetail,
  type CanvasArtifactSummary,
  deleteCanvasArtifact,
} from "@/lib/api/canvas";
import { type ArtifactViewMode, SETTINGS, useSetting } from "@/lib/settings/store";
import { cn } from "@/lib/utils";
import { Check, Code2, Eye, FileText, X } from "lucide-react";
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
  onDismissDiff,
}: {
  artifacts: CanvasArtifactSummary[];
  active: CanvasArtifactDetail | null;
  prevBody: string | null;
  activeFilename: string | null;
  onSelect: (filename: string | null) => void;
  onAfterDelete?: () => void;
  onDismissDiff?: () => void;
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
      {/* Inset the artifact body in a card. The card itself is the
          scroll container — `min-h-0` on the flex parent lets `flex-1`
          actually constrain the height so overflow has somewhere to
          go (without it the card would expand to fit the body and
          nothing would scroll). */}
      <div className="flex min-h-0 flex-1 p-3">
        <div className="flex h-full w-full flex-col overflow-hidden rounded-md border border-border-default bg-canvas shadow-sm">
          {active ? (
            <ArtifactBody detail={active} prevBody={prevBody} onDismissDiff={onDismissDiff} />
          ) : (
            <div className="flex h-full items-center justify-center px-6 text-center text-sm text-fg-tertiary">
              Select an artifact tab to view it.
            </div>
          )}
        </div>
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
    <div className="flex flex-nowrap items-stretch overflow-x-auto overflow-y-hidden whitespace-nowrap border-b border-border-default bg-elevated [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {artifacts.map((a) => {
        const active = a.filename === activeFilename;
        return (
          <Tooltip
            key={a.filename}
            label={`${a.filename} — ${_humanSize(a.size)}`}
            triggerClassName="!inline-flex"
            floating
          >
            <div
              className={cn(
                // IDE-style tab: tabs butt up against each other, share a
                // baseline; active one bleeds into the body surface so it
                // reads as "in front", inactive ones sit on the elevated
                // strip with a subtle right divider.
                "group relative inline-flex shrink-0 items-center gap-1.5 border-r border-border-default px-3 py-1.5 text-[11px] transition-colors",
                active
                  ? "-mb-px border-b border-b-canvas bg-canvas text-fg-primary"
                  : "bg-elevated text-fg-secondary hover:bg-recessed hover:text-fg-primary",
              )}
            >
              {active ? (
                <span
                  aria-hidden="true"
                  className="absolute inset-x-0 top-0 h-0.5 bg-accent-primary"
                />
              ) : null}
              <button
                type="button"
                onClick={() => onSelect(a.filename)}
                className="inline-flex items-center gap-1.5 font-mono"
              >
                <FileText
                  size={12}
                  strokeWidth={1.5}
                  className={cn(active ? "text-accent-primary" : "text-fg-tertiary")}
                />
                <span className="max-w-[180px] truncate">{a.filename}</span>
              </button>
              <Tooltip label={`Delete ${a.filename}`} side="bottom" floating>
                <button
                  type="button"
                  aria-label={`Delete ${a.filename}`}
                  onClick={() => void handleDelete(a.filename)}
                  className={cn(
                    "rounded-sm p-0.5 text-fg-tertiary transition-opacity hover:bg-recessed hover:text-fg-primary",
                    active ? "opacity-60 hover:opacity-100" : "opacity-0 group-hover:opacity-100",
                  )}
                >
                  <X size={11} strokeWidth={2.5} />
                </button>
              </Tooltip>
            </div>
          </Tooltip>
        );
      })}
      {/* Filler so the bottom border continues across empty space after
          the last tab. */}
      <div className="min-w-2 flex-1" aria-hidden="true" />
    </div>
  );
}

function ArtifactBody({
  detail,
  prevBody,
  onDismissDiff,
}: {
  detail: CanvasArtifactDetail;
  prevBody: string | null;
  onDismissDiff?: () => void;
}) {
  const [viewMode, setViewMode] = useSetting<ArtifactViewMode>(
    SETTINGS.artifactView.key,
    SETTINGS.artifactView.default,
  );
  const showDiff = prevBody !== null && prevBody !== detail.body;
  const isMarkdown = /\.(md|markdown)$/i.test(detail.filename);

  return (
    <>
      <header className="flex shrink-0 items-center justify-between gap-2 border-b border-border-default px-4 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <h3 className="truncate font-mono text-xs text-fg-secondary">{detail.filename}</h3>
          {showDiff ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-accent-primary-weak px-1.5 py-0.5 text-[10px] font-medium text-accent-primary">
              just updated
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          {showDiff && onDismissDiff ? (
            <button
              type="button"
              onClick={onDismissDiff}
              className="inline-flex items-center gap-1 rounded-md border border-border-default bg-elevated px-2 py-0.5 text-[11px] font-medium text-fg-secondary hover:bg-recessed hover:text-fg-primary"
            >
              <Check size={11} strokeWidth={2.5} />
              Got it
            </button>
          ) : null}
          {isMarkdown && !showDiff ? <ViewToggle value={viewMode} onChange={setViewMode} /> : null}
          <span className="text-[10px] text-fg-tertiary tabular-nums">
            {_humanSize(detail.size)} · {_relTime(detail.modified_at)}
          </span>
        </div>
      </header>
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {showDiff ? (
          <DiffView before={prevBody ?? ""} after={detail.body} />
        ) : isMarkdown && viewMode === "pretty" ? (
          <Markdown body={detail.body} />
        ) : (
          <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-fg-primary">
            {detail.body}
          </pre>
        )}
      </div>
    </>
  );
}

function ViewToggle({
  value,
  onChange,
}: {
  value: ArtifactViewMode;
  onChange: (next: ArtifactViewMode) => void;
}) {
  const opts: { value: ArtifactViewMode; label: string; Icon: typeof Eye }[] = [
    { value: "pretty", label: "Pretty", Icon: Eye },
    { value: "raw", label: "Raw", Icon: Code2 },
  ];
  return (
    <div className="inline-flex items-center rounded-md border border-border-default bg-elevated p-0.5">
      {opts.map(({ value: v, label, Icon }) => {
        const active = v === value;
        return (
          <Tooltip key={v} label={label} side="bottom" align="center">
            <button
              type="button"
              aria-pressed={active}
              aria-label={label}
              onClick={() => onChange(v)}
              className={cn(
                "inline-flex h-5 w-5 items-center justify-center rounded-sm transition-colors",
                active
                  ? "bg-accent-primary-weak text-accent-primary"
                  : "text-fg-tertiary hover:text-fg-primary",
              )}
            >
              <Icon size={11} strokeWidth={2} />
            </button>
          </Tooltip>
        );
      })}
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
    <div className="flex h-full items-center justify-center p-6">
      <div className="w-full max-w-xs rounded-md border border-dashed border-border-default bg-canvas/50 px-4 py-6 text-center">
        <p className="text-sm text-fg-tertiary">
          Artifacts will appear here when an AI starts maintaining one. Ask any participant to
          "track this in a doc as we go" and they will create one for you.
        </p>
      </div>
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
