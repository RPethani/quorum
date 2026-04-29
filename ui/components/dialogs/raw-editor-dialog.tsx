"use client";

import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/input";
import { type RawFileEntry, getRawFile, getRawListing, saveRawFile } from "@/lib/api/conductor";
import { FileText, Loader2, Save } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

/**
 * Raw editor (design-doc §9.8 Tier 3) — view + edit any file on the
 * server-side whitelist (config.yaml, state.yaml, problem-statement,
 * outcome-manifest, registers/*, context/index.md, etc.).
 *
 * The whitelist is owned by the conductor; this UI just presents what
 * the GET /api/raw listing returns. Saving validates only at the
 * filesystem level — there's no schema check here. Use this when
 * something has gone wrong in a way the dialogs can't fix.
 */
export function RawEditorDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [files, setFiles] = useState<RawFileEntry[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState<string>("");
  const [originalContent, setOriginalContent] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [missing, setMissing] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setListError(null);
    try {
      const listing = await getRawListing();
      setFiles(listing.files);
    } catch {
      setListError("Couldn't load the file list. Check that the conductor is reachable.");
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    void refresh();
  }, [open, refresh]);

  const loadFile = useCallback(async (entry: RawFileEntry) => {
    setSelected(entry.path);
    setSavedAt(null);
    setFileError(null);
    if (!entry.exists) {
      // File on the whitelist but not yet on disk — let the user
      // start with an empty buffer; saving will create it.
      setContent("");
      setOriginalContent("");
      setMissing(true);
      return;
    }
    setMissing(false);
    setLoading(true);
    try {
      const f = await getRawFile(entry.path);
      setContent(f.content);
      setOriginalContent(f.content);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setContent("");
      setOriginalContent("");
      setFileError(_friendlyLoadError(msg));
    } finally {
      setLoading(false);
    }
  }, []);

  async function save() {
    if (!selected) return;
    setSaving(true);
    setFileError(null);
    try {
      await saveRawFile(selected, content);
      setOriginalContent(content);
      setSavedAt(new Date().toLocaleTimeString());
      setMissing(false);
      void refresh();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setFileError(_friendlySaveError(msg));
    } finally {
      setSaving(false);
    }
  }

  const dirty = content !== originalContent;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Raw editor"
      description="Edit any whitelisted workspace file directly. Tier 3 escape hatch — use when the dialogs can't express what you need."
      size="xl"
    >
      <div className="grid grid-cols-[220px_1fr] gap-4 min-h-[28rem]">
        <aside className="border-r border-border-default pr-4">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-fg-tertiary">
            Whitelisted files
          </p>
          <ul className="space-y-0.5">
            {files.map((f) => (
              <li key={f.path}>
                <button
                  type="button"
                  onClick={() => void loadFile(f)}
                  className={`flex w-full items-start gap-1.5 rounded-sm px-2 py-1 text-left text-xs transition-colors ${
                    selected === f.path
                      ? "bg-accent-primary-weak text-accent-primary"
                      : "text-fg-secondary hover:bg-recessed hover:text-fg-primary"
                  }`}
                  title={f.path}
                >
                  <FileText size={12} className="mt-0.5 shrink-0" strokeWidth={1.5} />
                  <span className="font-mono truncate">{f.path}</span>
                  {!f.exists ? (
                    <span className="ml-auto shrink-0 text-[10px] uppercase text-fg-tertiary">
                      empty
                    </span>
                  ) : null}
                </button>
              </li>
            ))}
            {files.length === 0 && !listError ? (
              <li className="text-xs text-fg-tertiary">Loading…</li>
            ) : null}
          </ul>
          {listError ? <p className="mt-3 text-xs text-accent-danger">{listError}</p> : null}
        </aside>

        <main className="flex flex-col">
          {selected ? (
            <>
              <div className="mb-2 flex items-center justify-between">
                <code className="font-mono text-xs text-fg-secondary">{selected}</code>
                {savedAt ? (
                  <span className="text-[11px] text-accent-success">Saved at {savedAt}</span>
                ) : missing ? (
                  <span className="text-[11px] text-fg-tertiary">
                    new file — saving will create it
                  </span>
                ) : dirty ? (
                  <span className="text-[11px] text-accent-warning">unsaved changes</span>
                ) : null}
              </div>
              {fileError ? (
                <div className="rounded-md border border-accent-danger/40 bg-accent-danger-weak px-3 py-2 text-sm text-accent-danger">
                  {fileError}
                </div>
              ) : (
                <Textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  className="h-full min-h-[24rem] font-mono text-xs leading-relaxed"
                  disabled={loading}
                  placeholder={
                    missing
                      ? "This file doesn't exist yet. Type to create it, then click Save."
                      : undefined
                  }
                />
              )}
            </>
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-fg-tertiary">
              Pick a file from the left to edit.
            </div>
          )}
        </main>
      </div>

      <DialogFooter>
        <Button variant="outline" onClick={onClose} disabled={saving}>
          Close
        </Button>
        <Button
          variant="primary"
          onClick={save}
          disabled={!selected || saving || !!fileError || (!dirty && !missing)}
        >
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
          Save
        </Button>
      </DialogFooter>
    </Dialog>
  );
}

function _friendlyLoadError(raw: string): string {
  if (/404/.test(raw)) {
    // Shouldn't reach here normally — listing carries `exists`. But
    // guard for race conditions (file deleted between list and load).
    return "That file doesn't exist on disk yet. Saving will create it.";
  }
  if (/403/.test(raw)) {
    return "Conductor refused to read this file. It isn't on the editable whitelist.";
  }
  if (/Could not reach the conductor/i.test(raw)) {
    return "Couldn't reach the conductor. Check that `quorum serve` is running.";
  }
  if (/500/.test(raw)) {
    return "The conductor hit an error reading this file. Check the server logs.";
  }
  return "Couldn't read this file.";
}

function _friendlySaveError(raw: string): string {
  if (/403/.test(raw)) {
    return "Conductor refused this write. The file isn't on the editable whitelist.";
  }
  if (/Could not reach the conductor/i.test(raw)) {
    return "Couldn't reach the conductor. Your changes weren't saved.";
  }
  return "Couldn't save the file.";
}
