"use client";

import { ThemeToggle } from "@/components/design-system/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { type PermissionRequestRow, decidePermission, getPermissions } from "@/lib/api/conductor";
import { Check, KeyRound, Lock, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

/**
 * Phase-11 permissions page. Shows pending and decided permission
 * requests; approve / deny actions on pending rows. The live broker
 * (stdin/stdout pipe proxying) is deferred per ADR-003; the data plane
 * + UI here are ready for whenever it lands.
 */
export default function PermissionsPage() {
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
    void refresh();
    const handle = setInterval(refresh, 5000);
    return () => clearInterval(handle);
  }, [refresh]);

  async function decide(id: string, approve: boolean) {
    setBusy(id);
    try {
      await decidePermission(id, approve);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  const pending = rows.filter((r) => r.status === "pending");
  const decided = rows.filter((r) => r.status !== "pending");

  return (
    <div className="min-h-screen bg-canvas text-fg-primary">
      <header className="flex items-center justify-between border-b border-border-default bg-elevated px-6 py-3">
        <div className="flex items-center gap-3">
          <Link
            href="/workspace"
            className="font-semibold tracking-tight hover:text-accent-primary transition-colors"
          >
            Quorum
          </Link>
          <span className="text-fg-tertiary">/</span>
          <span className="font-medium">Permissions</span>
          <KeyRound size={14} className="text-fg-tertiary" strokeWidth={1.5} />
        </div>
        <ThemeToggle />
      </header>

      <main className="mx-auto max-w-3xl space-y-6 px-6 py-8">
        {error ? (
          <Card className="border-accent-danger">
            <CardContent className="text-sm text-accent-danger">{error}</CardContent>
          </Card>
        ) : null}

        <Card>
          <CardHeader>
            <CardTitle>
              Pending requests <Badge variant="warning">{pending.length}</Badge>
            </CardTitle>
            <p className="text-sm text-fg-secondary">
              Agents that asked the user for permission to run a tool, restricted by{" "}
              <code className="font-mono">--allowedTools</code> at the CLI level. Approving here
              writes a decision file the conductor will read on the agent's next attempt.
              <br />
              <em>
                v1: live stdin/stdout pipe proxying is deferred (ADR-003); the broker plumbing on
                this page is ready for when it lands.
              </em>
            </p>
          </CardHeader>
          <CardContent>
            {pending.length === 0 ? (
              <p className="py-6 text-center text-sm text-fg-tertiary">No pending requests.</p>
            ) : (
              <ul className="divide-y divide-border-default">
                {pending.map((r) => (
                  <li key={r.id} className="flex items-start justify-between gap-3 py-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 text-sm font-medium">
                        <span className="font-mono">{r.handle}</span>
                        <Badge variant={badgeForStakes(r.stakes)}>{r.stakes}</Badge>
                        <span className="text-fg-tertiary text-xs">
                          on #{r.deliberation_id || "—"}
                        </span>
                      </div>
                      <p className="mt-1 text-sm">
                        <strong>{r.tool}</strong>{" "}
                        <code className="font-mono text-xs">{r.operation}</code>
                      </p>
                      <p className="mt-1 text-xs text-fg-secondary">{r.rationale}</p>
                      <p className="mt-0.5 font-mono text-[10px] text-fg-tertiary">
                        {r.requested_at}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => decide(r.id, true)}
                        disabled={busy === r.id}
                      >
                        <Check size={12} /> Approve
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => decide(r.id, false)}
                        disabled={busy === r.id}
                      >
                        <X size={12} /> Deny
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>
              Decided <Badge variant="neutral">{decided.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {decided.length === 0 ? (
              <p className="py-6 text-center text-sm text-fg-tertiary">No history yet.</p>
            ) : (
              <ul className="divide-y divide-border-default">
                {decided.slice(0, 50).map((r) => (
                  <li key={r.id} className="py-2 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono">{r.handle}</span>
                      <Badge variant={badgeForStatus(r.status)}>{r.status}</Badge>
                    </div>
                    <p className="text-fg-secondary">
                      {r.tool} <code className="font-mono">{r.operation}</code>
                    </p>
                    {r.decision_reason ? (
                      <p className="text-fg-tertiary">{r.decision_reason}</p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center gap-2 py-3 text-xs text-fg-tertiary">
            <Lock size={12} strokeWidth={1.5} />
            Auto-approval policy is configured in <code className="font-mono">config.yaml</code>'s{" "}
            <code className="font-mono">broker.auto_approve_stakes_below</code>. v1 default:
            disabled.
          </CardContent>
        </Card>
      </main>
    </div>
  );
}

function badgeForStakes(s: string): "neutral" | "primary" | "warning" | "danger" {
  switch (s) {
    case "trivial":
      return "neutral";
    case "tactical":
      return "primary";
    case "strategic":
      return "warning";
    case "irreversible":
      return "danger";
    default:
      return "neutral";
  }
}

function badgeForStatus(s: string): "neutral" | "primary" | "success" | "warning" | "danger" {
  switch (s) {
    case "approved":
    case "auto_approved":
      return "success";
    case "denied":
      return "danger";
    case "expired":
      return "warning";
    default:
      return "neutral";
  }
}
