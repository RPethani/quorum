"use client";

import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter } from "@/components/ui/dialog";
import { FilePicker } from "@/components/ui/file-picker";
import { Input, Textarea } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  type ContextManifest,
  addContextDoc,
  addContextNote,
  addContextRepo,
  addContextUrl,
  getContextManifest,
  getRawFile,
  refreshUrl,
  saveRawFile,
} from "@/lib/api/conductor";
import { CheckCircle2, FolderOpen, Loader2, RefreshCw, Save } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

/**
 * One-stop dialog for everything the user can attach to a workspace
 * as collaboration context: the problem statement, local repos,
 * documents/files, free-form notes, and URLs.
 */
export function ContextDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [manifest, setManifest] = useState<ContextManifest | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      setManifest(await getContextManifest());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    void refresh();
  }, [open, refresh]);

  return (
    <Dialog open={open} onClose={onClose} title="Workspace context" size="lg">
      <Tabs defaultValue="problem">
        <TabsList>
          <TabsTrigger value="problem">Problem</TabsTrigger>
          <TabsTrigger value="repos">Repos ({manifest?.repos.length ?? 0})</TabsTrigger>
          <TabsTrigger value="docs">Docs ({manifest?.docs.length ?? 0})</TabsTrigger>
          <TabsTrigger value="notes">Notes ({manifest?.notes.length ?? 0})</TabsTrigger>
          <TabsTrigger value="urls">URLs ({manifest?.urls.length ?? 0})</TabsTrigger>
        </TabsList>

        <TabsContent value="problem">
          <ProblemStatement />
        </TabsContent>

        <TabsContent value="repos">
          <ItemList items={manifest?.repos ?? []} fields={["name", "path", "relevance"]} />
          <AddRepoForm onAdded={refresh} />
        </TabsContent>

        <TabsContent value="docs">
          <ItemList
            items={manifest?.docs ?? []}
            fields={["name", "source_path", "tokens_estimated", "needs_digest"]}
          />
          <AddDocForm onAdded={refresh} />
        </TabsContent>

        <TabsContent value="notes">
          <ItemList items={manifest?.notes ?? []} fields={["name", "added_at"]} />
          <AddNoteForm onAdded={refresh} />
        </TabsContent>

        <TabsContent value="urls">
          <UrlList items={manifest?.urls ?? []} onRefreshed={refresh} />
          <AddUrlForm onAdded={refresh} />
        </TabsContent>
      </Tabs>

      {error ? <p className="mt-3 text-sm text-accent-danger">{error}</p> : null}
    </Dialog>
  );
}

// ---------------------------------------------------------------------- //
// Problem statement (read + edit)
// ---------------------------------------------------------------------- //

function ProblemStatement() {
  const [content, setContent] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    void getRawFile("problem-statement.md")
      .then((r) => {
        if (alive) {
          setContent(r.content);
          setLoading(false);
        }
      })
      .catch(() => setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  async function save() {
    setSaving(true);
    try {
      await saveRawFile("problem-statement.md", content);
      setSavedAt(new Date().toLocaleTimeString());
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p className="px-1 py-6 text-sm text-fg-tertiary">Loading problem statement…</p>;
  }
  return (
    <div className="space-y-3 pt-2">
      <p className="text-xs text-fg-tertiary">
        This is the seed text the bootstrapper reads to draft the outcome manifest. Edit anytime —
        agents on subsequent moves will see the new version.
      </p>
      <Textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        className="min-h-[20rem] font-mono text-xs leading-relaxed"
        placeholder="# Problem Statement&#10;&#10;## What I'm trying to figure out&#10;…"
      />
      <DialogFooter>
        {savedAt ? (
          <span className="text-xs text-fg-tertiary mr-auto">Saved at {savedAt}</span>
        ) : null}
        <Button variant="primary" onClick={save} disabled={saving}>
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
          Save
        </Button>
      </DialogFooter>
    </div>
  );
}

// ---------------------------------------------------------------------- //
// Generic items list — table-ish summary
// ---------------------------------------------------------------------- //

function ItemList({
  items,
  fields,
}: {
  items: Array<Record<string, unknown>>;
  fields: string[];
}) {
  if (!items.length) {
    return (
      <p className="px-1 py-6 text-sm text-fg-tertiary">
        Nothing here yet. Add the first one below.
      </p>
    );
  }
  return (
    <ul className="divide-y divide-border-default rounded-md border border-border-default bg-recessed">
      {items.map((it, i) => (
        <li key={`${i}-${String(it.name)}`} className="px-3 py-2 text-sm">
          <div className="font-medium">{String(it.name ?? "(unnamed)")}</div>
          <div className="mt-0.5 grid grid-cols-1 gap-x-4 gap-y-0.5 text-xs text-fg-tertiary md:grid-cols-3">
            {fields
              .filter((f) => f !== "name" && it[f] != null && it[f] !== "")
              .map((f) => (
                <span key={f} className="truncate">
                  <span className="font-mono">{f}</span>: {String(it[f])}
                </span>
              ))}
          </div>
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------- //
// URL list — adds per-row refresh button + fetch state
// ---------------------------------------------------------------------- //

function UrlList({
  items,
  onRefreshed,
}: {
  items: Array<Record<string, unknown>>;
  onRefreshed: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (!items.length) {
    return (
      <p className="px-1 py-6 text-sm text-fg-tertiary">
        No URLs registered yet. Add one below — the conductor fetches and converts to Markdown
        automatically.
      </p>
    );
  }
  return (
    <div className="space-y-2">
      {error ? <p className="text-sm text-accent-danger">{error}</p> : null}
      <ul className="divide-y divide-border-default rounded-md border border-border-default bg-recessed">
        {items.map((u, i) => {
          const name = String(u.name ?? "");
          const cached = !!u.cached_path;
          return (
            <li key={`${i}-${name}`} className="flex items-start justify-between gap-3 px-3 py-2">
              <div className="min-w-0 flex-1">
                <div className="font-medium truncate">{String(u.title || u.name || u.url)}</div>
                <div className="mt-0.5 text-xs text-fg-tertiary truncate">
                  <a
                    href={String(u.url)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-mono hover:underline"
                  >
                    {String(u.url)}
                  </a>
                </div>
                <div className="mt-0.5 text-xs">
                  {cached ? (
                    <span className="text-accent-success">
                      cached · fetched {String(u.fetched_at ?? "?")}
                    </span>
                  ) : (
                    <span className="text-accent-warning">no cache yet</span>
                  )}
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                disabled={busy === name}
                onClick={async () => {
                  setBusy(name);
                  setError(null);
                  try {
                    await refreshUrl(name);
                    onRefreshed();
                  } catch (e) {
                    setError(e instanceof Error ? e.message : String(e));
                  } finally {
                    setBusy(null);
                  }
                }}
              >
                {busy === name ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : (
                  <RefreshCw size={12} />
                )}
                Refresh
              </Button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------- //
// Add forms — minimal, one per tab
// ---------------------------------------------------------------------- //

function AddRepoForm({ onAdded }: { onAdded: () => void }) {
  const [path, setPath] = useState("");
  const [name, setName] = useState("");
  const [relevance, setRelevance] = useState("medium");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [lastAdded, setLastAdded] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  return (
    <AddBox>
      <Field label="Repo path" hint="Browse to pick a folder, or paste an absolute path.">
        <div className="flex items-center gap-2">
          <Input
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder="/Users/me/code/myrepo"
            className="font-mono"
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setPickerOpen(true)}
            title="Pick a folder"
          >
            <FolderOpen size={14} />
            Browse
          </Button>
        </div>
      </Field>
      <Field label="Name" hint="Optional. Defaults to the directory name.">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="myrepo" />
      </Field>
      <Field label="Relevance" hint="Drives which model digests it later.">
        <select
          value={relevance}
          onChange={(e) => setRelevance(e.target.value)}
          className="h-9 w-full rounded-sm border border-border-default bg-elevated px-3 text-sm"
        >
          <option value="high">high</option>
          <option value="medium">medium</option>
          <option value="low">low</option>
        </select>
      </Field>
      {err ? <p className="text-sm text-accent-danger">{err}</p> : null}
      <FormStatus lastAdded={lastAdded} kind="repo" />
      <DialogFooter>
        <Button
          variant="primary"
          disabled={!path.trim() || busy}
          onClick={async () => {
            setBusy(true);
            setErr(null);
            try {
              const res = await addContextRepo({
                path: path.trim(),
                name: name.trim(),
                relevance,
              });
              setLastAdded(res.name);
              setPath("");
              setName("");
              onAdded();
            } catch (e) {
              setErr(e instanceof Error ? e.message : String(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? <Loader2 size={14} className="animate-spin" /> : null}
          Add repo
        </Button>
      </DialogFooter>
      <FilePicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        mode="dirs"
        title="Pick a repository folder"
        onPick={(p) => {
          setPath(p);
          setPickerOpen(false);
        }}
      />
    </AddBox>
  );
}

function AddDocForm({ onAdded }: { onAdded: () => void }) {
  const [path, setPath] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [lastAdded, setLastAdded] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  return (
    <AddBox>
      <Field
        label="File path"
        hint="Browse to pick a file, or paste an absolute path. The file is copied into context/docs/raw/."
      >
        <div className="flex items-center gap-2">
          <Input
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder="/Users/me/specs/feature.md"
            className="font-mono"
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setPickerOpen(true)}
            title="Pick a file"
          >
            <FolderOpen size={14} />
            Browse
          </Button>
        </div>
      </Field>
      <Field label="Name" hint="Optional. Defaults to the file stem.">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="feature" />
      </Field>
      {err ? <p className="text-sm text-accent-danger">{err}</p> : null}
      <FormStatus lastAdded={lastAdded} kind="doc" />
      <DialogFooter>
        <Button
          variant="primary"
          disabled={!path.trim() || busy}
          onClick={async () => {
            setBusy(true);
            setErr(null);
            try {
              const res = await addContextDoc({ path: path.trim(), name: name.trim() });
              setLastAdded(res.name);
              setPath("");
              setName("");
              onAdded();
            } catch (e) {
              setErr(e instanceof Error ? e.message : String(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? <Loader2 size={14} className="animate-spin" /> : null}
          Add doc
        </Button>
      </DialogFooter>
      <FilePicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        mode="files"
        title="Pick a document"
        onPick={(p) => {
          setPath(p);
          setPickerOpen(false);
        }}
      />
    </AddBox>
  );
}

function AddNoteForm({ onAdded }: { onAdded: () => void }) {
  const [name, setName] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [lastAdded, setLastAdded] = useState<string | null>(null);
  return (
    <AddBox>
      <Field label="Slug" hint="Short kebab-case name; used as filename.">
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="design-constraints"
          className="font-mono"
        />
      </Field>
      <Field label="Note body">
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="min-h-[8rem] font-mono text-xs leading-relaxed"
          placeholder="# Design constraints&#10;&#10;- Must run locally without paid services."
        />
      </Field>
      {err ? <p className="text-sm text-accent-danger">{err}</p> : null}
      <FormStatus lastAdded={lastAdded} kind="note" />
      <DialogFooter>
        <Button
          variant="primary"
          disabled={!name.trim() || !text.trim() || busy}
          onClick={async () => {
            setBusy(true);
            setErr(null);
            try {
              const res = await addContextNote({ name: name.trim(), text });
              setLastAdded(res.name);
              setName("");
              setText("");
              onAdded();
            } catch (e) {
              setErr(e instanceof Error ? e.message : String(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? <Loader2 size={14} className="animate-spin" /> : null}
          Add note
        </Button>
      </DialogFooter>
    </AddBox>
  );
}

function AddUrlForm({ onAdded }: { onAdded: () => void }) {
  const [href, setHref] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [lastAdded, setLastAdded] = useState<string | null>(null);
  return (
    <AddBox>
      <Field label="URL" hint="External link the agents can read about.">
        <Input
          value={href}
          onChange={(e) => setHref(e.target.value)}
          placeholder="https://docs.example.com/foo"
          className="font-mono"
        />
      </Field>
      <Field label="Name" hint="Optional human-readable label.">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="foo docs" />
      </Field>
      <Field label="Role" hint="Optional one-liner about what this URL is for.">
        <Input
          value={role}
          onChange={(e) => setRole(e.target.value)}
          placeholder="API reference for the foo service"
        />
      </Field>
      {err ? <p className="text-sm text-accent-danger">{err}</p> : null}
      <FormStatus lastAdded={lastAdded} kind="url" />
      <DialogFooter>
        <Button
          variant="primary"
          disabled={!href.trim() || busy}
          onClick={async () => {
            setBusy(true);
            setErr(null);
            try {
              const res = await addContextUrl({
                url: href.trim(),
                name: name.trim(),
                role: role.trim(),
              });
              setLastAdded(res.name);
              setHref("");
              setName("");
              setRole("");
              onAdded();
            } catch (e) {
              setErr(e instanceof Error ? e.message : String(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? <Loader2 size={14} className="animate-spin" /> : null}
          Add URL
        </Button>
      </DialogFooter>
    </AddBox>
  );
}

// ---------------------------------------------------------------------- //
// Shared form chrome
// ---------------------------------------------------------------------- //

function AddBox({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-4 rounded-md border border-border-default bg-recessed/50 p-4 space-y-3">
      <p className="text-xs font-semibold uppercase tracking-wider text-fg-tertiary">Add new</p>
      {children}
    </div>
  );
}

function FormStatus({ lastAdded, kind }: { lastAdded: string | null; kind: string }) {
  if (!lastAdded) return null;
  return (
    <div className="flex items-center gap-2 rounded-md border border-accent-success/40 bg-accent-success-weak px-3 py-1.5 text-xs text-accent-success">
      <CheckCircle2 size={12} />
      <span>
        Added {kind} <span className="font-mono">{lastAdded}</span>. The form is cleared — add
        another, or close the dialog.
      </span>
    </div>
  );
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
