"use client";

import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter } from "@/components/ui/dialog";
import { type FsListing, listFs } from "@/lib/api/conductor";
import { ChevronUp, FileText, Folder, Loader2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

/**
 * Modal file/directory picker that lists the host filesystem via the
 * conductor's /api/fs/list. Handy for adding repos and documents
 * without making the user paste absolute paths by hand.
 *
 * `mode="dirs"` only shows folders and lets the user pick the
 * currently-open directory. `mode="files"` shows folders + files;
 * picking a folder navigates into it, picking a file selects it.
 */
export function FilePicker({
  open,
  onClose,
  onPick,
  mode = "dirs",
  title,
}: {
  open: boolean;
  onClose: () => void;
  onPick: (absPath: string) => void;
  mode?: "dirs" | "files";
  title?: string;
}) {
  const [listing, setListing] = useState<FsListing | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const navigate = useCallback(
    async (path: string | null) => {
      setLoading(true);
      setError(null);
      try {
        const next = await listFs(path, mode);
        setListing(next);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    [mode],
  );

  useEffect(() => {
    if (!open) return;
    void navigate(null); // start at $HOME
  }, [open, navigate]);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={title ?? (mode === "dirs" ? "Pick a directory" : "Pick a file")}
      size="md"
    >
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-sm">
          <Button
            variant="outline"
            size="sm"
            onClick={() => listing?.parent && void navigate(listing.parent)}
            disabled={!listing?.parent || loading}
            title="Up one directory"
          >
            <ChevronUp size={14} /> Up
          </Button>
          <code className="font-mono text-xs text-fg-secondary truncate">
            {listing?.path ?? "…"}
          </code>
          {loading ? <Loader2 size={14} className="ml-auto animate-spin text-fg-tertiary" /> : null}
        </div>

        {error ? <p className="text-sm text-accent-danger">{error}</p> : null}

        <ul className="max-h-[50vh] overflow-y-auto rounded-md border border-border-default bg-recessed">
          {listing?.entries.length ? (
            listing.entries.map((e) => (
              <li key={e.path}>
                <button
                  type="button"
                  onClick={() => {
                    if (e.is_dir) void navigate(e.path);
                    else onPick(e.path);
                  }}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-elevated transition-colors"
                >
                  {e.is_dir ? (
                    <Folder size={14} className="shrink-0 text-fg-tertiary" />
                  ) : (
                    <FileText size={14} className="shrink-0 text-fg-tertiary" />
                  )}
                  <span className="truncate">{e.name}</span>
                </button>
              </li>
            ))
          ) : (
            <li className="px-3 py-3 text-sm text-fg-tertiary">
              {loading ? "Loading…" : "Empty directory."}
            </li>
          )}
        </ul>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          {mode === "dirs" ? (
            <Button
              variant="primary"
              onClick={() => listing && onPick(listing.path)}
              disabled={!listing || loading}
              title="Pick the current directory"
            >
              Pick this directory
            </Button>
          ) : null}
        </DialogFooter>
      </div>
    </Dialog>
  );
}
