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
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const listing = await getRawListing();
      setFiles(listing.files);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    void refresh();
  }, [open, refresh]);

  const loadFile = useCallback(async (path: string) => {
    setLoading(true);
    setError(null);
    setSavedAt(null);
    try {
      const f = await getRawFile(path);
      setContent(f.content);
      setOriginalContent(f.content);
      setSelected(path);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  async function save() {
    if (!selected) return;
    setSaving(true);
    setError(null);
    try {
      await saveRawFile(selected, content);
      setOriginalContent(content);
      setSavedAt(new Date().toLocaleTimeString());
      void refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
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
          {error ? <p className="mb-2 text-xs text-accent-danger">{error}</p> : null}
          <ul className="space-y-0.5">
            {files.map((f) => (
              <li key={f.path}>
                <button
                  type="button"
                  onClick={() => void loadFile(f.path)}
                  className={`flex w-full items-start gap-1.5 rounded-sm px-2 py-1 text-left text-xs transition-colors ${
                    selected === f.path
                      ? "bg-accent-primary-weak text-accent-primary"
                      : "text-fg-secondary hover:bg-recessed hover:text-fg-primary"
                  }`}
                  title={f.path}
                >
                  <FileText size={12} className="mt-0.5 shrink-0" strokeWidth={1.5} />
                  <span className="font-mono truncate">{f.path}</span>
                </button>
              </li>
            ))}
            {files.length === 0 ? <li className="text-xs text-fg-tertiary">Loading…</li> : null}
          </ul>
        </aside>

        <main className="flex flex-col">
          {selected ? (
            <>
              <div className="mb-2 flex items-center justify-between">
                <code className="font-mono text-xs text-fg-secondary">{selected}</code>
                {savedAt ? (
                  <span className="text-[11px] text-accent-success">Saved at {savedAt}</span>
                ) : dirty ? (
                  <span className="text-[11px] text-accent-warning">unsaved changes</span>
                ) : null}
              </div>
              <Textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                className="h-full min-h-[24rem] font-mono text-xs leading-relaxed"
                disabled={loading}
              />
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
        <Button variant="primary" onClick={save} disabled={!selected || !dirty || saving}>
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
          Save
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
