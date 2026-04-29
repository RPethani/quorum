"use client";

import { ThemeToggle } from "@/components/design-system/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { type WizardPayload, applyWizard } from "@/lib/api/conductor";
import { ArrowRight, Loader2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

type WorkKind =
  | "saas-product"
  | "architecture-decision"
  | "research-direction"
  | "coding-plan"
  | "strategic-decision";

type Involvement = "tightly" | "flexible" | "hands-off";

type Substitution = "strict" | "substitute" | "substitute_aggressively";

type Ceiling = 25 | 50 | 200 | 0;

const WORK_KIND_OPTIONS: { value: WorkKind; label: string; blurb: string }[] = [
  {
    value: "saas-product",
    label: "Build a product",
    blurb: "Refine a SaaS / product idea into shippable specs.",
  },
  {
    value: "architecture-decision",
    label: "Make an architecture decision",
    blurb: "Decide a technical question with reasoned tradeoffs and a migration plan.",
  },
  {
    value: "research-direction",
    label: "Synthesize research",
    blurb: "Turn a research area into questions, prior-art map, methodology.",
  },
  {
    value: "coding-plan",
    label: "Plan implementation",
    blurb: "Break work into sequenced tasks with a dependency graph.",
  },
  {
    value: "strategic-decision",
    label: "Make a strategic call",
    blurb: "Compare options for a high-stakes decision with a rollback plan.",
  },
];

const INVOLVEMENT_OPTIONS: {
  value: Involvement;
  label: string;
  blurb: string;
  mode: WizardPayload["mode"];
}[] = [
  {
    value: "tightly",
    label: "Tightly involved",
    blurb: "Review every decision.",
    mode: "interactive",
  },
  {
    value: "flexible",
    label: "Available but flexible",
    blurb: "Let agents handle small things; ping me on the big ones.",
    mode: "interactive",
  },
  {
    value: "hands-off",
    label: "Hands off",
    blurb: "Let agents drive entirely.",
    mode: "autonomous",
  },
];

const SUBSTITUTION_OPTIONS: { value: Substitution; label: string; blurb: string }[] = [
  {
    value: "strict",
    label: "Wait until it's back",
    blurb: "Don't substitute when a model is unavailable.",
  },
  {
    value: "substitute",
    label: "Substitute with similar quality",
    blurb: "Best v1 default for most workspaces.",
  },
  {
    value: "substitute_aggressively",
    label: "Substitute with anything available",
    blurb: "Maximum throughput, lowest quality floor.",
  },
];

const CEILING_OPTIONS: { value: Ceiling; label: string }[] = [
  { value: 25, label: "$25 — small experiments" },
  { value: 50, label: "$50 — substantial single-feature brainstorm (default)" },
  { value: 200, label: "$200 — large multi-repo work" },
  { value: 0, label: "No ceiling (advanced)" },
];

export default function SetupPage() {
  const [step, setStep] = useState(0);
  const [work, setWork] = useState<WorkKind | null>(null);
  const [involvement, setInvolvement] = useState<Involvement | null>(null);
  const [substitution, setSubstitution] = useState<Substitution>("substitute");
  const [ceiling, setCeiling] = useState<Ceiling>(50);
  const [problemStatement, setProblemStatement] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const totalSteps = 5;

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      const involvementOpt = INVOLVEMENT_OPTIONS.find((o) => o.value === involvement);
      const payload: WizardPayload = {
        manifest_template: work,
        unavailability_policy: substitution,
        cost_ceiling_usd: ceiling > 0 ? ceiling : 999_999,
        ...(involvementOpt ? { mode: involvementOpt.mode } : {}),
        ...(problemStatement.trim() ? { problem_statement: problemStatement.trim() } : {}),
      };
      const res = await applyWizard(payload);
      setSubmitted(res.applied);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-canvas text-fg-primary">
      <header className="flex items-center justify-between border-b border-border-default px-6 py-3">
        <div className="flex items-center gap-3">
          <Link href="/" className="font-semibold tracking-tight">
            Quorum
          </Link>
          <Badge variant="primary">setup</Badge>
        </div>
        <ThemeToggle />
      </header>

      <main className="mx-auto max-w-2xl px-6 py-10">
        <p className="text-xs font-medium uppercase tracking-wider text-fg-tertiary">
          Step {step + 1} of {totalSteps}
        </p>
        <div className="mt-2 h-1 w-full rounded-full bg-recessed">
          <div
            className="h-full rounded-full bg-accent-primary transition-all duration-300"
            style={{ width: `${((step + 1) / totalSteps) * 100}%` }}
          />
        </div>

        {submitted ? (
          <Card className="mt-8">
            <CardHeader>
              <CardTitle>Setup complete</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <p>Applied: {submitted.join(", ") || "no changes"}.</p>
              <p className="text-fg-secondary">
                You can revisit any of these later via the settings panels.
              </p>
              <div className="flex gap-2">
                <Link
                  href="/workspace"
                  className="inline-flex h-9 items-center rounded-md bg-accent-primary px-4 text-sm font-medium text-white hover:opacity-90 transition-opacity"
                >
                  Open workspace
                </Link>
                <Link
                  href="/"
                  className="inline-flex h-9 items-center rounded-md border border-border-default px-4 text-sm font-medium hover:bg-recessed transition-colors"
                >
                  Home
                </Link>
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="mt-8">
            {step === 0 ? (
              <QuestionCard
                title="What kind of work is this?"
                blurb="Drives the manifest template the bootstrapper proposes."
              >
                <ChoiceGroup
                  options={WORK_KIND_OPTIONS.map((o) => ({
                    value: o.value,
                    label: o.label,
                    blurb: o.blurb,
                  }))}
                  value={work}
                  onChange={(v) => setWork(v as WorkKind)}
                />
              </QuestionCard>
            ) : null}
            {step === 1 ? (
              <QuestionCard
                title="How involved do you want to be?"
                blurb="Drives interactive vs autonomous mode."
              >
                <ChoiceGroup
                  options={INVOLVEMENT_OPTIONS.map((o) => ({
                    value: o.value,
                    label: o.label,
                    blurb: o.blurb,
                  }))}
                  value={involvement}
                  onChange={(v) => setInvolvement(v as Involvement)}
                />
              </QuestionCard>
            ) : null}
            {step === 2 ? (
              <QuestionCard
                title="If your top-choice model is unavailable, what should happen?"
                blurb="Drives the substitution policy when a routed handle is down or rate-limited."
              >
                <ChoiceGroup
                  options={SUBSTITUTION_OPTIONS.map((o) => ({
                    value: o.value,
                    label: o.label,
                    blurb: o.blurb,
                  }))}
                  value={substitution}
                  onChange={(v) => setSubstitution(v as Substitution)}
                />
              </QuestionCard>
            ) : null}
            {step === 3 ? (
              <QuestionCard
                title="Set a cost ceiling for this workspace?"
                blurb="The conductor pauses the workspace when accumulated spend reaches the ceiling. You can change this anytime."
              >
                <ChoiceGroup
                  options={CEILING_OPTIONS.map((o) => ({ value: String(o.value), label: o.label }))}
                  value={String(ceiling)}
                  onChange={(v) => setCeiling(Number(v) as Ceiling)}
                />
              </QuestionCard>
            ) : null}
            {step === 4 ? (
              <QuestionCard
                title="Anything you want to specify upfront?"
                blurb="This becomes your problem-statement.md. You can edit it later."
              >
                <Textarea
                  placeholder={`# Problem Statement\n\n## What I'm trying to figure out\n…`}
                  className="min-h-[14rem] font-mono text-xs leading-relaxed"
                  value={problemStatement}
                  onChange={(e) => setProblemStatement(e.target.value)}
                />
                <Input
                  className="mt-3"
                  placeholder="Optional one-line title (free text)"
                  disabled
                />
              </QuestionCard>
            ) : null}

            {error ? (
              <p className="mt-4 text-sm text-accent-danger">Error applying changes: {error}</p>
            ) : null}

            <div className="mt-6 flex items-center justify-between">
              <Button
                variant="outline"
                onClick={() => setStep((s) => Math.max(0, s - 1))}
                disabled={step === 0 || submitting}
              >
                Back
              </Button>
              {step < totalSteps - 1 ? (
                <Button
                  variant="primary"
                  onClick={() => setStep((s) => Math.min(totalSteps - 1, s + 1))}
                >
                  Next <ArrowRight size={14} />
                </Button>
              ) : (
                <Button variant="primary" onClick={submit} disabled={submitting}>
                  {submitting ? <Loader2 size={14} className="animate-spin" /> : null}
                  Apply
                </Button>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function QuestionCard({
  title,
  blurb,
  children,
}: {
  title: string;
  blurb?: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {blurb ? <p className="text-sm text-fg-secondary">{blurb}</p> : null}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function ChoiceGroup<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string; blurb?: string }[];
  value: T | null;
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      {options.map((o) => (
        <button
          type="button"
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`text-left rounded-md border px-4 py-3 transition-colors duration-100 ${
            value === o.value
              ? "border-accent-primary bg-accent-primary-weak"
              : "border-border-default hover:bg-recessed"
          }`}
        >
          <div className="text-sm font-medium">{o.label}</div>
          {o.blurb ? <div className="text-xs text-fg-secondary mt-0.5">{o.blurb}</div> : null}
        </button>
      ))}
    </div>
  );
}
