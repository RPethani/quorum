"use client";

import { X } from "lucide-react";
import { useEffect } from "react";
import { Tooltip } from "./tooltip";

/**
 * Minimal modal primitive — fixed-overlay + centered card. We avoid the
 * radix-ui dependency in favour of a tiny hand-rolled component since
 * the workspace's modals are click-outside / Escape / X-button to close
 * and don't need focus-trap or portal behaviour beyond what `<dialog>`
 * would have given us. Render-prop style: pass `open` + `onClose`.
 */
export function Dialog({
  open,
  onClose,
  title,
  description,
  size = "md",
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  size?: "sm" | "md" | "lg" | "xl";
  children: React.ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;

  const widthClass = {
    sm: "max-w-md",
    md: "max-w-xl",
    lg: "max-w-3xl",
    xl: "max-w-5xl",
  }[size];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={onClose}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onClose();
      }}
      role="presentation"
    >
      <dialog
        open
        className={`relative w-full ${widthClass} max-h-[90vh] overflow-y-auto rounded-lg border border-border-default bg-elevated text-fg-primary shadow-2xl`}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => e.stopPropagation()}
        aria-modal="true"
        aria-label={title}
      >
        <div className="flex items-start justify-between gap-4 border-b border-border-default px-6 py-4">
          <div className="min-w-0">
            <h2 className="text-base font-semibold tracking-tight">{title}</h2>
            {description ? <p className="mt-1 text-sm text-fg-secondary">{description}</p> : null}
          </div>
          <Tooltip label="Close" side="bottom" align="end">
            <button
              type="button"
              onClick={onClose}
              className="rounded p-1 text-fg-tertiary hover:bg-recessed hover:text-fg-primary transition-colors"
              aria-label="Close"
            >
              <X size={16} />
            </button>
          </Tooltip>
        </div>
        <div className="px-6 py-5">{children}</div>
      </dialog>
    </div>
  );
}

export function DialogFooter({ children }: { children: React.ReactNode }) {
  return (
    <div className="-mx-6 -mb-5 mt-6 flex items-center justify-end gap-2 border-t border-border-default bg-recessed px-6 py-3">
      {children}
    </div>
  );
}
