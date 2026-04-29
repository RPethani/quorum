"use client";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { type PermissionRequestRow, decidePermission, getPermissions } from "@/lib/api/conductor";
import { Check, Loader2, RefreshCw, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

/**
 * Inbox of agent-issued permission requests.
 *
 * The conductor's data plane is in place (per ADR-003 the live
 * stdin/stdout broker is deferred); this dialog just renders pending
 * requests and lets the user approve / deny them. Decisions emit
 * `permission_decided` audit events.
 */
export function PermissionsDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [rows, setRows] = useState<PermissionRequestRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      setRows(await getPermissions());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    void refresh();
  }, [open, refresh]);

  const pending = rows.filter((r) => r.status === "pending");
  const decided = rows.filter((r) => r.status !== "pending");

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Permissions"
      description="Agent-issued permission requests. Approving writes a decision the conductor reads on the agent's next attempt."
      size="lg"
    >
      <div className="space-y-4">
        {error ? <p className="text-sm text-accent-danger">{error}</p> : null}

        <div className="flex items-center justify-between">
          <p className="text-xs text-fg-tertiary">
            {pending.length === 0 ? "No pending requests." : `${pending.length} pending.`}
          </p>
          <Button variant="outline" size="sm" onClick={() => void refresh()}>
            <RefreshCw size={12} /> Refresh
          </Button>
        </div>

        {pending.length > 0 ? (
          <Section title="Pending">
            {pending.map((r) => (
              <RequestRow
                key={r.id}
                row={r}
                busy={busy === r.id}
                onDecide={async (approve) => {
                  setBusy(r.id);
                  try {
                    await decidePermission(r.id, approve);
                    await refresh();
                  } catch (e) {
                    setError(e instanceof Error ? e.message : String(e));
                  } finally {
                    setBusy(null);
                  }
                }}
              />
            ))}
          </Section>
        ) : null}

        {decided.length > 0 ? (
          <Section title="Recent decisions">
            {decided.slice(0, 10).map((r) => (
              <RequestRow key={r.id} row={r} />
            ))}
          </Section>
        ) : null}

        <p className="text-xs text-fg-tertiary">
          v1 doesn't proxy live stdin/stdout — see ADR-003. The data plane is ready for the broker
          once it ships.
        </p>
      </div>
    </Dialog>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-fg-tertiary">
        {title}
      </p>
      <ul className="divide-y divide-border-default rounded-md border border-border-default bg-recessed">
        {children}
      </ul>
    </div>
  );
}

function RequestRow({
  row,
  busy,
  onDecide,
}: {
  row: PermissionRequestRow;
  busy?: boolean;
  onDecide?: (approve: boolean) => void;
}) {
  const stakeTone =
    row.stakes === "irreversible"
      ? "bg-accent-danger-weak text-accent-danger border-accent-danger/40"
      : row.stakes === "strategic"
        ? "bg-accent-warning-weak text-accent-warning border-accent-warning/40"
        : "bg-recessed text-fg-tertiary border-border-default";
  const statusTone =
    row.status === "pending"
      ? "bg-accent-warning-weak text-accent-warning border-accent-warning/40"
      : row.status === "denied"
        ? "bg-accent-danger-weak text-accent-danger border-accent-danger/40"
        : "bg-accent-success-weak text-accent-success border-accent-success/40";
  return (
    <li className="px-3 py-2 text-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs">{row.handle}</span>
            <span
              className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wider ${stakeTone}`}
            >
              {row.stakes}
            </span>
            <span
              className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wider ${statusTone}`}
            >
              {row.status}
            </span>
          </div>
          <p className="mt-1 text-xs">
            <code className="font-mono text-fg-secondary">{row.tool}</code> on{" "}
            <span className="text-fg-secondary">#{row.deliberation_id}</span>
          </p>
          <p className="mt-0.5 text-xs text-fg-tertiary">{row.operation}</p>
          {row.rationale ? (
            <p className="mt-1 text-xs text-fg-secondary italic">{row.rationale}</p>
          ) : null}
          {row.decided_by ? (
            <p className="mt-1 text-[11px] text-fg-tertiary">
              {row.decided_at} · by {row.decided_by}
              {row.decision_reason ? ` — ${row.decision_reason}` : ""}
            </p>
          ) : null}
        </div>
        {onDecide ? (
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              disabled={busy}
              onClick={() => onDecide(false)}
              title="Deny"
            >
              {busy ? <Loader2 size={12} className="animate-spin" /> : <X size={12} />}
              Deny
            </Button>
            <Button
              variant="primary"
              size="sm"
              disabled={busy}
              onClick={() => onDecide(true)}
              title="Approve"
            >
              {busy ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
              Approve
            </Button>
          </div>
        ) : null}
      </div>
    </li>
  );
}
