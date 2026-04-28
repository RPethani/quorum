"use client";

import { ThemeToggle } from "@/components/design-system/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import {
  type DeliberationDetail,
  type PlanResponse,
  type StepResponse,
  type WorkspaceStateResponse,
  getDeliberation,
  getPlan,
  getState,
  step,
} from "@/lib/api/conductor";
import { Loader2, Play, RotateCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

/**
 * Phase-5 vertical-slice page. Intentionally crude per the bootstrap:
 * a Markdown viewer for deliberation #0001, a `Step` button that calls
 * `POST /api/step`, and a refresh control. The whole point is to
 * validate the protocol with a real CLI agent before the real UI ships
 * in Phase 7.
 *
 * Pre-requisite: the conductor's HTTP server (`quorum serve`) must be
 * running on port 8500. Override with `?api=http://host:port` in the URL.
 */
export default function DevVerticalSlicePage() {
  const [state, setState] = useState<WorkspaceStateResponse | null>(null);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [delib, setDelib] = useState<DeliberationDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [stepping, setStepping] = useState(false);
  const [lastStep, setLastStep] = useState<StepResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, p] = await Promise.all([getState(), getPlan()]);
      setState(s);
      setPlan(p);
      try {
        const d = await getDeliberation("0001");
        setDelib(d);
      } catch {
        setDelib(null);
      }
    } catch (e: unknown) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleStep = useCallback(async () => {
    setStepping(true);
    setError(null);
    try {
      const result = await step();
      setLastStep(result);
      await refresh();
    } catch (e: unknown) {
      setError(errorMessage(e));
    } finally {
      setStepping(false);
    }
  }, [refresh]);

  const nextItem = plan?.items[0];

  return (
    <main className="mx-auto max-w-4xl px-6 py-8">
      <header className="mb-6 flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-fg-tertiary">
            Quorum dev
          </p>
          <h1 className="text-2xl font-bold tracking-tight">Vertical slice</h1>
          <p className="mt-1 text-sm text-fg-secondary">
            Phase-5 plumbing. Drive a single agent invocation against the active workspace and read
            what came back.
          </p>
        </div>
        <ThemeToggle />
      </header>

      {error ? (
        <Card className="mb-4 border-accent-danger">
          <CardContent className="text-sm text-accent-danger">
            <strong>API error.</strong> {error}
            <p className="mt-2 text-fg-secondary">
              Make sure the conductor's HTTP server is running:&nbsp;
              <code className="font-mono">quorum serve --path /your/workspace</code>.
            </p>
          </CardContent>
        </Card>
      ) : null}

      <section className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Workspace</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="state">
              <Badge variant={badgeForState(state?.state)}>{state?.state ?? "—"}</Badge>
            </Row>
            <Row label="mode">
              <span className="font-mono">{state?.mode ?? "—"}</span>
            </Row>
            <Row label="deliberations">
              <span className="font-mono">{state?.counts.deliberations ?? 0}</span>
            </Row>
            <Row label="cost">
              <span className="font-mono">
                ${state?.cost.spent_usd?.toFixed(2) ?? "—"} / $
                {state?.cost.ceiling_usd?.toFixed(2) ?? "—"}
                {state ? ` (${Math.round((state.cost.fraction ?? 0) * 100)}%)` : null}
              </span>
            </Row>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Next action</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {nextItem ? (
              <>
                <Row label="role">
                  <span className="font-mono">
                    {nextItem.role} → {nextItem.move_type}
                  </span>
                </Row>
                <Row label="handle">
                  <span className="font-mono">{nextItem.handle}</span>
                  {nextItem.is_manual ? (
                    <Badge variant="warning" className="ml-2">
                      manual
                    </Badge>
                  ) : null}
                </Row>
                <Row label="layer">
                  <span className="font-mono">{nextItem.layer}</span>
                </Row>
                <Row label="reason">
                  <span className="font-mono">{nextItem.reason}</span>
                </Row>
              </>
            ) : (
              <p className="text-fg-secondary">No runnable items.</p>
            )}
            {plan?.blocked && plan.blocked.length > 0 ? (
              <p className="text-xs text-accent-warning">
                {plan.blocked.length} blocked item(s) — check participants and routing-defaults.
              </p>
            ) : null}
          </CardContent>
        </Card>
      </section>

      <section className="mb-6 flex items-center gap-2">
        <Button
          variant="primary"
          onClick={handleStep}
          disabled={stepping || !nextItem || nextItem.is_manual}
        >
          {stepping ? <Loader2 className="animate-spin" size={14} /> : <Play size={14} />}
          Step
        </Button>
        <Button variant="outline" onClick={refresh} disabled={loading}>
          <RotateCw size={14} className={loading ? "animate-spin" : ""} />
          Refresh
        </Button>
      </section>

      {lastStep ? (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Last step</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            <pre className="whitespace-pre-wrap font-mono text-xs">
              {JSON.stringify(lastStep, null, 2)}
            </pre>
          </CardContent>
        </Card>
      ) : null}

      <Separator />

      <section className="mt-6">
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="text-lg font-semibold">
            Deliberation #{delib?.id ?? "—"}{" "}
            <span className="ml-2 text-sm font-normal text-fg-secondary">{delib?.title}</span>
          </h2>
          {delib ? <Badge variant={badgeForState(delib.status)}>{delib.status}</Badge> : null}
        </div>
        {delib ? (
          <pre className="overflow-x-auto rounded-md border border-border-default bg-recessed p-4 font-mono text-xs leading-relaxed">
            {delib.markdown}
          </pre>
        ) : (
          <p className="text-sm text-fg-secondary">
            No deliberation file yet. Press <strong>Step</strong> to bootstrap.
          </p>
        )}
      </section>
    </main>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-28 shrink-0 font-mono text-xs uppercase tracking-wider text-fg-tertiary">
        {label}
      </span>
      <div className="flex flex-wrap items-center">{children}</div>
    </div>
  );
}

function badgeForState(state?: string): "neutral" | "primary" | "success" | "warning" | "danger" {
  if (!state) return "neutral";
  if (state === "DECIDED" || state === "COMPLETED") return "success";
  if (state.startsWith("BLOCKED") || state === "PAUSED") return "warning";
  if (state === "ARCHIVED" || state === "ABANDONED") return "danger";
  if (state === "ACTIVE" || state === "OPEN" || state === "IN_REVIEW") return "primary";
  return "neutral";
}

function errorMessage(e: unknown): string {
  if (e instanceof Error) return e.message;
  return String(e);
}
