"use client";

import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { type WizardPayload, applyWizard, getParticipants } from "@/lib/api/conductor";
import { ArrowRight, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

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

export function SetupDialog({
  open,
  onClose,
  onApplied,
}: {
  open: boolean;
  onClose: () => void;
  onApplied?: () => void;
}) {
  const [step, setStep] = useState(0);
  const [humanHandle, setHumanHandle] = useState<string>("");
  const [originalHandle, setOriginalHandle] = useState<string>("");
  const [work, setWork] = useState<WorkKind | null>(null);
  const [involvement, setInvolvement] = useState<Involvement | null>(null);
  const [substitution, setSubstitution] = useState<Substitution>("substitute");
  const [ceiling, setCeiling] = useState<Ceiling>(50);
  const [problemStatement, setProblemStatement] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const totalSteps = 6;

  useEffect(() => {
    if (!open) return;
    void (async () => {
      try {
        const ps = await getParticipants();
        const manual = ps.find((p) => p.transport === "manual");
        if (manual) {
          setHumanHandle(manual.handle);
          setOriginalHandle(manual.handle);
        }
      } catch {
        // conductor not running — error surfaces on Apply.
      }
    })();
  }, [open]);

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
        ...(humanHandle.trim() && humanHandle.trim() !== originalHandle
          ? { human_handle: humanHandle.trim() }
          : {}),
      };
      const res = await applyWizard(payload);
      setSubmitted(res.applied);
      onApplied?.();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    setStep(0);
    setSubmitted(null);
    setError(null);
  }

  return (
    <Dialog
      open={open}
      onClose={() => {
        onClose();
        // Reset for next open so we don't show "Setup complete" stale.
        setTimeout(reset, 200);
      }}
      title="Setup"
      description="Tell us about you, the work, and your involvement style."
      size="md"
    >
      <p className="text-xs font-medium uppercase tracking-wider text-fg-tertiary">
        Step {step + 1} of {totalSteps}
      </p>
      <div className="mt-2 mb-6 h-1 w-full rounded-full bg-recessed">
        <div
          className="h-full rounded-full bg-accent-primary transition-all duration-300"
          style={{ width: `${((step + 1) / totalSteps) * 100}%` }}
        />
      </div>

      {submitted ? (
        <div className="space-y-3 text-sm">
          <p className="font-medium">Setup complete.</p>
          <p className="text-fg-secondary">
            Applied: {submitted.join(", ") || "no changes"}. You can revisit any of these from
            Settings later.
          </p>
          <DialogFooter>
            <Button variant="primary" onClick={onClose}>
              Done
            </Button>
          </DialogFooter>
        </div>
      ) : (
        <>
          {step === 0 ? (
            <QuestionBlock
              title="What should we call you?"
              blurb="Your handle on every move you author. Conductor detects this from $USER or git config; override here if you want something different."
            >
              <Input
                value={humanHandle}
                onChange={(e) => setHumanHandle(e.target.value)}
                placeholder="@human-jane"
                className="font-mono"
              />
              <p className="mt-2 text-xs text-fg-tertiary">
                Handles start with <code className="font-mono">@</code>. Lowercase letters, digits,
                and hyphens.
              </p>
            </QuestionBlock>
          ) : null}
          {step === 1 ? (
            <QuestionBlock
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
            </QuestionBlock>
          ) : null}
          {step === 2 ? (
            <QuestionBlock
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
            </QuestionBlock>
          ) : null}
          {step === 3 ? (
            <QuestionBlock
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
            </QuestionBlock>
          ) : null}
          {step === 4 ? (
            <QuestionBlock
              title="Set a cost ceiling for this workspace?"
              blurb="The conductor pauses the workspace when accumulated spend reaches the ceiling. You can change this anytime."
            >
              <ChoiceGroup
                options={CEILING_OPTIONS.map((o) => ({
                  value: String(o.value),
                  label: o.label,
                }))}
                value={String(ceiling)}
                onChange={(v) => setCeiling(Number(v) as Ceiling)}
              />
            </QuestionBlock>
          ) : null}
          {step === 5 ? (
            <QuestionBlock
              title="Anything you want to specify upfront?"
              blurb="This becomes your problem-statement.md. You can edit it later."
            >
              <Textarea
                placeholder={`# Problem Statement\n\n## What I'm trying to figure out\n…`}
                className="min-h-[14rem] font-mono text-xs leading-relaxed"
                value={problemStatement}
                onChange={(e) => setProblemStatement(e.target.value)}
              />
            </QuestionBlock>
          ) : null}

          {error ? (
            <p className="mt-4 text-sm text-accent-danger">Error applying changes: {error}</p>
          ) : null}

          <DialogFooter>
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
          </DialogFooter>
        </>
      )}
    </Dialog>
  );
}

function QuestionBlock({
  title,
  blurb,
  children,
}: {
  title: string;
  blurb?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h3 className="text-sm font-semibold">{title}</h3>
      {blurb ? <p className="mt-1 text-sm text-fg-secondary">{blurb}</p> : null}
      <div className="mt-4">{children}</div>
    </div>
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
