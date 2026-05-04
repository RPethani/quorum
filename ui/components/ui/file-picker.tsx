"use client";

import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter } from "@/components/ui/dialog";
import { Tooltip } from "@/components/ui/tooltip";
import { type FsListing, listFs } from "@/lib/api/canvas";
import { ChevronUp, FileText, Folder, Loader2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

/**
 * Modal file/directory picker that walks the host filesystem via the
 * conductor's `/api/fs/list`. Used by the Context dialog so users
 * don't have to paste absolute paths by hand.
 *
 * `mode="dirs"` shows folders only; the footer "Pick this directory"
 * button picks the currently-open folder. `mode="files"` shows folders
 * + files; clicking a folder navigates, clicking a file picks it.
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
        setListing(await listFs(path, mode));
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
          <Tooltip label="Up one directory">
            <Button
              variant="outline"
              size="sm"
              onClick={() => listing?.parent && void navigate(listing.parent)}
              disabled={!listing?.parent || loading}
              aria-label="Up one directory"
            >
              <ChevronUp size={14} /> Up
            </Button>
          </Tooltip>
          <code className="truncate font-mono text-xs text-fg-secondary">
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
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm transition-colors hover:bg-elevated"
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
            >
              Pick this directory
            </Button>
          ) : null}
        </DialogFooter>
      </div>
    </Dialog>
  );
}
