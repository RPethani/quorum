"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Tooltip } from "@/components/ui/tooltip";
import {
  type CanvasContextEntry,
  addCanvasDoc,
  addCanvasNote,
  addCanvasRepo,
  digestCanvasContext,
  listCanvasContext,
  refreshCanvasContext,
  removeCanvasContext,
  updateCanvasState,
} from "@/lib/api/canvas";
import { cn } from "@/lib/utils";
import { FileText, FolderGit2, Loader2, RefreshCw, StickyNote, Trash2, Wand2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

type AddKind = "repo" | "doc" | "note";

/**
 * Context dialog — see, add, remove the repos / docs / notes that
 * agents read from `context/index.md`. Repos are symlinked, docs are
 * copied, notes are inline. Repos can be summarised by the configured
 * digester participant ("Digest" button).
 */
export function ContextDialog({
  open,
  onClose,
  digesterHandle,
}: {
  open: boolean;
  onClose: () => void;
  /** Current `digester_handle` from state.yaml. Empty = none configured. */
  digesterHandle: string;
}) {
  const [entries, setEntries] = useState<CanvasContextEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const [addKind, setAddKind] = useState<AddKind>("repo");
  const [addPath, setAddPath] = useState("");
  const [addName, setAddName] = useState("");
  const [addBody, setAddBody] = useState("");
  const [addSubmitting, setAddSubmitting] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listCanvasContext();
      setEntries(res.entries);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    setAddKind("repo");
    setAddPath("");
    setAddName("");
    setAddBody("");
    void reload();
  }, [open, reload]);

  async function submitAdd() {
    setAddSubmitting(true);
    setError(null);
    try {
      if (addKind === "repo") {
        await addCanvasRepo(addPath.trim(), addName.trim() || undefined);
      } else if (addKind === "doc") {
        await addCanvasDoc(addPath.trim(), addName.trim() || undefined);
      } else {
        await addCanvasNote(addName.trim(), addBody);
      }
      setAddPath("");
      setAddName("");
      setAddBody("");
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setAddSubmitting(false);
    }
  }

  async function remove(id: string) {
    setBusyId(id);
    setError(null);
    try {
      await removeCanvasContext(id);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  }

  async function digest(id: string) {
    setBusyId(id);
    setError(null);
    try {
      await digestCanvasContext(id);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  }

  async function refresh(id: string) {
    setBusyId(id);
    setError(null);
    try {
      await refreshCanvasContext(id);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  }

  const repos = entries.filter((e) => e.kind === "repo");
  const docs = entries.filter((e) => e.kind === "doc");
  const notes = entries.filter((e) => e.kind === "note");

  const addValid =
    addKind === "note"
      ? addName.trim().length > 0 && addBody.trim().length > 0
      : addPath.trim().length > 0;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Context"
      description="Repos, documents, and notes agents can read alongside the chat. Lives at `context/` in the workspace."
      size="lg"
    >
      <div className="flex flex-col gap-5">
        <AddSection
          kind={addKind}
          onKindChange={setAddKind}
          path={addPath}
          onPathChange={setAddPath}
          name={addName}
          onNameChange={setAddName}
          body={addBody}
          onBodyChange={setAddBody}
          submitting={addSubmitting}
          valid={addValid}
          onSubmit={submitAdd}
        />

        {!digesterHandle && repos.length > 0 ? (
          <p className="rounded-md border border-accent-warning/40 bg-accent-warning-weak px-3 py-2 text-[12px] text-accent-warning">
            No digester configured — repos won't be summarised until you pick one in Settings →
            Default agents → Digester.
          </p>
        ) : null}

        {error ? (
          <p className="rounded-md border border-accent-danger/40 bg-accent-danger-weak px-3 py-2 text-sm text-accent-danger">
            {error}
          </p>
        ) : null}

        {loading && entries.length === 0 ? (
          <p className="text-sm text-fg-tertiary">Loading…</p>
        ) : entries.length === 0 ? (
          <p className="text-sm text-fg-tertiary">
            No context yet. Add a repo path, a document, or a free-form note above.
          </p>
        ) : (
          <div className="flex flex-col gap-4">
            {repos.length > 0 ? (
              <Group title="Repos" Icon={FolderGit2}>
                {repos.map((e) => (
                  <RepoRow
                    key={e.id}
                    entry={e}
                    busy={busyId === e.id}
                    canDigest={digesterHandle.length > 0}
                    onDigest={() => digest(e.id)}
                    onRefresh={() => refresh(e.id)}
                    onRemove={() => remove(e.id)}
                  />
                ))}
              </Group>
            ) : null}
            {docs.length > 0 ? (
              <Group title="Docs" Icon={FileText}>
                {docs.map((e) => (
                  <DocRow
                    key={e.id}
                    entry={e}
                    busy={busyId === e.id}
                    onRemove={() => remove(e.id)}
                  />
                ))}
              </Group>
            ) : null}
            {notes.length > 0 ? (
              <Group title="Notes" Icon={StickyNote}>
                {notes.map((e) => (
                  <NoteRow
                    key={e.id}
                    entry={e}
                    busy={busyId === e.id}
                    onRemove={() => remove(e.id)}
                  />
                ))}
              </Group>
            ) : null}
          </div>
        )}
      </div>
    </Dialog>
  );
}

// ---------------------------------------------------------------------- //
// Add section
// ---------------------------------------------------------------------- //

function AddSection({
  kind,
  onKindChange,
  path,
  onPathChange,
  name,
  onNameChange,
  body,
  onBodyChange,
  submitting,
  valid,
  onSubmit,
}: {
  kind: AddKind;
  onKindChange: (k: AddKind) => void;
  path: string;
  onPathChange: (s: string) => void;
  name: string;
  onNameChange: (s: string) => void;
  body: string;
  onBodyChange: (s: string) => void;
  submitting: boolean;
  valid: boolean;
  onSubmit: () => void;
}) {
  const tabs: { value: AddKind; label: string }[] = [
    { value: "repo", label: "Repo" },
    { value: "doc", label: "Document" },
    { value: "note", label: "Note" },
  ];

  return (
    <section className="rounded-md border border-border-default bg-canvas p-3">
      <div className="mb-3 flex items-center gap-1 rounded-md border border-border-default bg-elevated p-0.5">
        {tabs.map((t) => {
          const active = t.value === kind;
          return (
            <button
              key={t.value}
              type="button"
              aria-pressed={active}
              onClick={() => onKindChange(t.value)}
              className={cn(
                "flex-1 rounded-sm px-2 py-1 text-[12px] font-medium transition-colors",
                active
                  ? "bg-accent-primary-weak text-accent-primary"
                  : "text-fg-secondary hover:text-fg-primary",
              )}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {kind !== "note" ? (
        <div className="space-y-2">
          <Field
            label="Absolute path"
            hint={
              kind === "repo"
                ? "Path to a directory. Quorum symlinks it under context/repos/."
                : "Path to a file. Quorum copies it under context/docs/."
            }
          >
            <Input
              value={path}
              onChange={(e) => onPathChange(e.target.value)}
              placeholder={kind === "repo" ? "/Users/you/code/v2-app" : "/Users/you/Notes/spec.md"}
              className="font-mono text-[12px]"
            />
          </Field>
          <Field label="Display name" hint="Optional. Defaults to the basename.">
            <Input
              value={name}
              onChange={(e) => onNameChange(e.target.value)}
              placeholder="v2-app"
            />
          </Field>
        </div>
      ) : (
        <div className="space-y-2">
          <Field label="Note name">
            <Input
              value={name}
              onChange={(e) => onNameChange(e.target.value)}
              placeholder="rate-limit-tradeoffs"
            />
          </Field>
          <Field label="Body">
            <textarea
              value={body}
              onChange={(e) => onBodyChange(e.target.value)}
              rows={4}
              className="block w-full resize-y rounded-md border border-border-default bg-elevated px-3 py-2 text-sm text-fg-primary placeholder:text-fg-tertiary focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
              placeholder="Free-form notes the agents should know about…"
            />
          </Field>
        </div>
      )}

      <div className="mt-3 flex items-center justify-end">
        <Button onClick={onSubmit} disabled={!valid || submitting} variant="primary">
          {submitting ? <Loader2 size={14} className="animate-spin" /> : null}
          Add
        </Button>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------- //
// Per-kind rows
// ---------------------------------------------------------------------- //

function Group({
  title,
  Icon,
  children,
}: {
  title: string;
  Icon: React.ComponentType<{ size?: number; strokeWidth?: number; className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h4 className="mb-1.5 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-fg-tertiary">
        <Icon size={12} strokeWidth={2} />
        {title}
      </h4>
      <ul className="flex flex-col gap-1.5">{children}</ul>
    </section>
  );
}

function RepoRow({
  entry,
  busy,
  canDigest,
  onDigest,
  onRefresh,
  onRemove,
}: {
  entry: CanvasContextEntry;
  busy: boolean;
  canDigest: boolean;
  onDigest: () => void;
  onRefresh: () => void;
  onRemove: () => void;
}) {
  return (
    <li className="rounded-md border border-border-default bg-canvas px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-medium text-fg-primary">{entry.name}</span>
            <StatusBadge entry={entry} />
            {entry.stale ? (
              <Badge variant="warning" className="text-[10px]">
                stale
              </Badge>
            ) : null}
          </div>
          <p className="truncate font-mono text-[11px] text-fg-tertiary">{entry.source}</p>
          {entry.digest_summary ? (
            <p className="mt-0.5 text-[12px] text-fg-secondary">{entry.digest_summary}</p>
          ) : null}
          {entry.digest_error ? (
            <p className="mt-0.5 text-[12px] text-accent-danger">{entry.digest_error}</p>
          ) : null}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <Tooltip
            label={canDigest ? "Run digester" : "Configure a digester in Settings first"}
            side="bottom"
            align="end"
          >
            <button
              type="button"
              aria-label="Run digester"
              onClick={onDigest}
              disabled={busy || !canDigest}
              className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-border-default text-fg-secondary hover:bg-recessed hover:text-fg-primary disabled:opacity-40"
            >
              {busy ? (
                <Loader2 size={13} className="animate-spin" />
              ) : (
                <Wand2 size={13} strokeWidth={2} />
              )}
            </button>
          </Tooltip>
          <Tooltip label="Mark as pending" side="bottom" align="end">
            <button
              type="button"
              aria-label="Mark as pending"
              onClick={onRefresh}
              disabled={busy}
              className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-border-default text-fg-secondary hover:bg-recessed hover:text-fg-primary disabled:opacity-40"
            >
              <RefreshCw size={13} strokeWidth={2} />
            </button>
          </Tooltip>
          <RemoveBtn busy={busy} onRemove={onRemove} />
        </div>
      </div>
    </li>
  );
}

function DocRow({
  entry,
  busy,
  onRemove,
}: {
  entry: CanvasContextEntry;
  busy: boolean;
  onRemove: () => void;
}) {
  return (
    <li className="flex items-center justify-between gap-2 rounded-md border border-border-default bg-canvas px-3 py-2">
      <div className="min-w-0">
        <span className="block truncate text-sm font-medium text-fg-primary">{entry.name}</span>
        <span className="block truncate font-mono text-[11px] text-fg-tertiary">
          {entry.source}
        </span>
      </div>
      <RemoveBtn busy={busy} onRemove={onRemove} />
    </li>
  );
}

function NoteRow({
  entry,
  busy,
  onRemove,
}: {
  entry: CanvasContextEntry;
  busy: boolean;
  onRemove: () => void;
}) {
  return (
    <li className="rounded-md border border-border-default bg-canvas px-3 py-2">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-fg-primary">{entry.name}</span>
          <p className="mt-0.5 line-clamp-2 text-[12px] text-fg-secondary">{entry.body}</p>
        </div>
        <RemoveBtn busy={busy} onRemove={onRemove} />
      </div>
    </li>
  );
}

function RemoveBtn({ busy, onRemove }: { busy: boolean; onRemove: () => void }) {
  return (
    <Tooltip label="Remove" side="bottom" align="end">
      <button
        type="button"
        aria-label="Remove"
        onClick={onRemove}
        disabled={busy}
        className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-border-default text-fg-secondary hover:bg-accent-danger-weak hover:text-accent-danger disabled:opacity-40"
      >
        <Trash2 size={13} strokeWidth={2} />
      </button>
    </Tooltip>
  );
}

function StatusBadge({ entry }: { entry: CanvasContextEntry }) {
  const s = entry.digest_status;
  if (!s || s === "pending") return <Badge variant="neutral">pending</Badge>;
  if (s === "running") return <Badge variant="primary">running</Badge>;
  if (s === "ready") return <Badge variant="success">ready</Badge>;
  if (s === "failed") return <Badge variant="danger">failed</Badge>;
  return <Badge variant="neutral">{s}</Badge>;
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <fieldset className="block border-0 p-0">
      <legend className="mb-1 block text-xs font-medium uppercase tracking-wider text-fg-tertiary">
        {label}
      </legend>
      {children}
      {hint ? <p className="mt-1 text-xs text-fg-tertiary">{hint}</p> : null}
    </fieldset>
  );
}

// Re-exported helper used by the Settings dialog so the digester
// handle round-trips through the same updateCanvasState() that owns
// state.yaml writes.
export { updateCanvasState };
