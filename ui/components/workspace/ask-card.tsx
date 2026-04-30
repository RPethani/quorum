"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { type Ask, type AskOption, answerAsk } from "@/lib/api/conductor";
import { ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { useState } from "react";

/**
 * The user-facing surface for a single open Ask.
 *
 * Renders one of four shapes (confirm | pick_one | pick_any | write)
 * and POSTs the answer to /api/asks/{id}/answer when submitted. Closes
 * itself by calling `onAnswered` so the parent can refresh the open
 * list.
 */
export function AskCard({
  ask,
  onAnswered,
}: {
  ask: Ask;
  onAnswered: () => void;
}) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (answer: Record<string, unknown>) => {
    setSubmitting(true);
    setError(null);
    try {
      await answerAsk(ask.id, { answer });
      onAnswered();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card variant="elevated" className="overflow-hidden">
      <CardHeader className="bg-accent-primary-weak">
        <div className="flex items-center gap-2">
          <Badge variant="warning">Your turn</Badge>
          <span className="text-xs text-fg-tertiary">{prettyShape(ask.shape)}</span>
        </div>
        <CardTitle className="leading-snug">{ask.question}</CardTitle>
        {ask.why ? <p className="text-sm text-fg-secondary">{ask.why}</p> : null}
      </CardHeader>
      <Separator />
      <CardContent className="p-5">
        {ask.shape === "confirm" ? (
          <ConfirmShape disabled={submitting} onSubmit={submit} />
        ) : ask.shape === "pick_one" ? (
          <PickOneShape ask={ask} disabled={submitting} onSubmit={submit} />
        ) : ask.shape === "pick_any" ? (
          <PickAnyShape ask={ask} disabled={submitting} onSubmit={submit} />
        ) : (
          <WriteShape ask={ask} disabled={submitting} onSubmit={submit} />
        )}
        {error ? (
          <p className="mt-3 rounded border border-accent-danger/40 bg-accent-danger-weak px-3 py-2 text-sm text-accent-danger">
            {error}
          </p>
        ) : null}
        {submitting ? (
          <p className="mt-3 flex items-center gap-2 text-sm text-fg-tertiary">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Submitting…
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------- //
// Shape: confirm
// ---------------------------------------------------------------------- //

function ConfirmShape({
  disabled,
  onSubmit,
}: {
  disabled: boolean;
  onSubmit: (answer: Record<string, unknown>) => Promise<void> | void;
}) {
  const [note, setNote] = useState("");
  return (
    <div className="space-y-3">
      <label className="text-sm">
        <span className="mb-1 block text-fg-secondary">
          Optional note (the reasoning becomes part of the audit trail)
        </span>
        <textarea
          className="w-full min-h-[80px] rounded-md border border-border-default bg-canvas px-3 py-2 text-sm font-mono"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          disabled={disabled}
        />
      </label>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="primary"
          disabled={disabled}
          onClick={() => onSubmit({ value: "yes", note })}
        >
          Yes
        </Button>
        <Button
          variant="outline"
          disabled={disabled}
          onClick={() => onSubmit({ value: "no", note })}
        >
          No
        </Button>
        <Button
          variant="ghost"
          disabled={disabled}
          onClick={() => onSubmit({ value: "more_info", note })}
        >
          I need more info
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------- //
// Shape: pick_one
// ---------------------------------------------------------------------- //

function PickOneShape({
  ask,
  disabled,
  onSubmit,
}: {
  ask: Ask;
  disabled: boolean;
  onSubmit: (answer: Record<string, unknown>) => Promise<void> | void;
}) {
  const options = ask.options ?? [];
  const [pick, setPick] = useState<string>(options[0]?.value ?? "__custom__");
  const [customText, setCustomText] = useState("");
  const [note, setNote] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  const isCustom = pick === "__custom__";

  return (
    <div className="space-y-4">
      <ul className="space-y-2">
        {options.map((opt) => (
          <li key={opt.value}>
            <OptionRow
              opt={opt}
              checked={pick === opt.value}
              expanded={expanded === opt.value}
              onSelect={() => setPick(opt.value)}
              onToggleExpand={() => setExpanded((prev) => (prev === opt.value ? null : opt.value))}
            />
          </li>
        ))}
        <li>
          <label className="flex cursor-pointer items-start gap-3 rounded-md border border-border-default p-3 hover:bg-recessed">
            <input
              type="radio"
              name={`ask-${ask.id}`}
              checked={isCustom}
              onChange={() => setPick("__custom__")}
              className="mt-1"
              disabled={disabled}
            />
            <div className="flex-1">
              <div className="text-sm font-medium">None of the above — write your own</div>
              {isCustom ? (
                <textarea
                  className="mt-2 w-full min-h-[100px] rounded-md border border-border-default bg-canvas px-3 py-2 text-sm font-mono"
                  value={customText}
                  onChange={(e) => setCustomText(e.target.value)}
                  placeholder="Describe the decision in your own words…"
                  disabled={disabled}
                />
              ) : null}
            </div>
          </label>
        </li>
      </ul>
      {!isCustom ? (
        <label className="block text-sm">
          <span className="mb-1 block text-fg-secondary">
            Optional note (why you picked this — appears in the audit trail)
          </span>
          <textarea
            className="w-full min-h-[60px] rounded-md border border-border-default bg-canvas px-3 py-2 text-sm font-mono"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            disabled={disabled}
          />
        </label>
      ) : null}
      <div>
        <Button
          variant="primary"
          disabled={disabled || (isCustom ? customText.trim().length === 0 : false)}
          onClick={() =>
            onSubmit(isCustom ? { value: "__custom__", text: customText } : { value: pick, note })
          }
        >
          Submit decision
        </Button>
      </div>
    </div>
  );
}

function OptionRow({
  opt,
  checked,
  expanded,
  onSelect,
  onToggleExpand,
}: {
  opt: AskOption;
  checked: boolean;
  expanded: boolean;
  onSelect: () => void;
  onToggleExpand: () => void;
}) {
  return (
    <div
      className={`rounded-md border p-3 ${
        checked
          ? "border-accent-primary bg-accent-primary-weak"
          : "border-border-default hover:bg-recessed"
      }`}
    >
      <label className="flex cursor-pointer items-start gap-3">
        <input type="radio" checked={checked} onChange={onSelect} className="mt-1" />
        <div className="flex-1">
          <div className="text-sm font-medium">{opt.label}</div>
          {opt.summary ? <p className="mt-1 text-sm text-fg-secondary">{opt.summary}</p> : null}
        </div>
      </label>
      {opt.expand ? (
        <div className="mt-2 pl-6">
          <button
            type="button"
            onClick={onToggleExpand}
            className="flex items-center gap-1 text-xs text-fg-tertiary hover:text-fg-primary"
          >
            {expanded ? (
              <>
                <ChevronUp className="h-3 w-3" /> Hide full body
              </>
            ) : (
              <>
                <ChevronDown className="h-3 w-3" /> Show full body
              </>
            )}
          </button>
          {expanded ? (
            <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded-md border border-border-default bg-recessed p-3 font-mono text-xs leading-relaxed">
              {opt.expand}
            </pre>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------- //
// Shape: pick_any
// ---------------------------------------------------------------------- //

function PickAnyShape({
  ask,
  disabled,
  onSubmit,
}: {
  ask: Ask;
  disabled: boolean;
  onSubmit: (answer: Record<string, unknown>) => Promise<void> | void;
}) {
  const options = ask.options ?? [];
  const [picks, setPicks] = useState<Set<string>>(new Set());
  const [note, setNote] = useState("");

  const min = ask.min_select ?? 0;
  const max = ask.max_select ?? options.length;

  const valid = picks.size >= min && picks.size <= max && picks.size > 0;

  return (
    <div className="space-y-4">
      <p className="text-xs text-fg-tertiary">
        Pick {min === max ? `exactly ${min}` : `${min}–${max}`}.
      </p>
      <ul className="space-y-2">
        {options.map((opt) => {
          const checked = picks.has(opt.value);
          return (
            <li key={opt.value}>
              <label
                className={`flex cursor-pointer items-start gap-3 rounded-md border p-3 ${
                  checked
                    ? "border-accent-primary bg-accent-primary-weak"
                    : "border-border-default hover:bg-recessed"
                }`}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={(e) => {
                    setPicks((prev) => {
                      const next = new Set(prev);
                      if (e.target.checked) next.add(opt.value);
                      else next.delete(opt.value);
                      return next;
                    });
                  }}
                  className="mt-1"
                  disabled={disabled}
                />
                <div className="flex-1">
                  <div className="text-sm font-medium">{opt.label}</div>
                  {opt.summary ? (
                    <p className="mt-1 text-sm text-fg-secondary">{opt.summary}</p>
                  ) : null}
                </div>
              </label>
            </li>
          );
        })}
      </ul>
      <label className="block text-sm">
        <span className="mb-1 block text-fg-secondary">Optional note</span>
        <textarea
          className="w-full min-h-[60px] rounded-md border border-border-default bg-canvas px-3 py-2 text-sm font-mono"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          disabled={disabled}
        />
      </label>
      <div>
        <Button
          variant="primary"
          disabled={disabled || !valid}
          onClick={() => onSubmit({ values: Array.from(picks), note })}
        >
          Submit
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------- //
// Shape: write
// ---------------------------------------------------------------------- //

function WriteShape({
  ask,
  disabled,
  onSubmit,
}: {
  ask: Ask;
  disabled: boolean;
  onSubmit: (answer: Record<string, unknown>) => Promise<void> | void;
}) {
  const [text, setText] = useState(ask.default_value ?? "");
  return (
    <div className="space-y-3">
      <textarea
        className="w-full min-h-[180px] rounded-md border border-border-default bg-canvas px-3 py-2 text-sm font-mono"
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={disabled}
        placeholder="Type your reply…"
      />
      <div>
        <Button
          variant="primary"
          disabled={disabled || text.trim().length === 0}
          onClick={() => onSubmit({ text })}
        >
          Submit
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------- //
// Helpers
// ---------------------------------------------------------------------- //

function prettyShape(shape: Ask["shape"]): string {
  switch (shape) {
    case "confirm":
      return "Yes / No";
    case "pick_one":
      return "Pick one";
    case "pick_any":
      return "Pick any";
    case "write":
      return "Write a reply";
  }
}
