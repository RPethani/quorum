"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { type AppendMovePayload, appendMove } from "@/lib/api/conductor";
import { Loader2, Send, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

type MoveType =
  | "ANSWER"
  | "DECISION"
  | "INTERJECTION"
  | "OVERRIDE"
  | "REOPEN"
  | "DROP"
  | "STEER"
  | "CLARIFY"
  | "QUESTION";

const SECTIONS: Record<MoveType, string[]> = {
  ANSWER: ["Answer", "Reasoning", "What this enables", "Caveats"],
  DECISION: [
    "Decision",
    "Summary line",
    "Rationale",
    "Path not taken",
    "Spawns ADR?",
    "Spawns task?",
  ],
  INTERJECTION: ["What's new", "Where it applies", "Force level", "Why I'm raising this now"],
  OVERRIDE: ["Decision", "Rationale", "What's being preserved", "Spawns ADR?", "Cascade"],
  REOPEN: ["Targets", "Why I'm reopening", "What changed since the prior DECISION", "Scope"],
  DROP: ["Targets", "Reason", "Disposition of partial work"],
  STEER: ["Direction", "Targets", "Reason", "Duration"],
  CLARIFY: ["Targets", "What I'm asking about", "Why", "Preferred explainer"],
  QUESTION: [
    "Question",
    "Stakes",
    "Why I'm asking",
    "What I'd recommend if forced",
    "Information you have that I don't",
  ],
};

const HUMAN_MOVE_TYPES: MoveType[] = [
  "ANSWER",
  "DECISION",
  "INTERJECTION",
  "OVERRIDE",
  "REOPEN",
  "DROP",
  "STEER",
  "CLARIFY",
  "QUESTION",
];

export function ComposeMoveForm({
  deliberationId,
  defaultMoveType = "DECISION",
  defaultAuthor = "@human-rohan",
  onClose,
  onAppended,
}: {
  deliberationId: string;
  defaultMoveType?: MoveType;
  defaultAuthor?: string;
  onClose: () => void;
  onAppended: (result: { move_type: string; inboxes_notified: string[] }) => void;
}) {
  const [moveType, setMoveType] = useState<MoveType>(defaultMoveType);
  const [author, setAuthor] = useState<string>(defaultAuthor);
  const [targets, setTargets] = useState<string>("");
  const [sectionValues, setSectionValues] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset section values when move type changes.
  useEffect(() => {
    const next: Record<string, string> = {};
    for (const name of SECTIONS[moveType]) next[name] = "";
    setSectionValues(next);
  }, [moveType]);

  const sections = useMemo(() => SECTIONS[moveType], [moveType]);

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      const payload: AppendMovePayload = {
        deliberation_id: deliberationId,
        move_type: moveType,
        author,
        targets: targets.trim() || null,
        sections: sectionValues,
      };
      const res = await appendMove(payload);
      onAppended({ move_type: res.move_type, inboxes_notified: res.inboxes_notified });
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/30 p-6 overflow-y-auto">
      <Card className="w-full max-w-2xl my-12">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>
              Compose move <Badge variant="primary">#{deliberationId}</Badge>
            </CardTitle>
            <button
              type="button"
              aria-label="Close"
              onClick={onClose}
              className="text-fg-tertiary hover:text-fg-primary"
            >
              <X size={16} />
            </button>
          </div>
          <p className="text-sm text-fg-secondary">
            Pick the move type, fill the required sections, submit. The conductor renders the
            canonical block and appends under the deliberation's lock. Empty sections are filled
            with "none" automatically.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label
                htmlFor="move-type"
                className="mb-1 block text-xs font-medium uppercase tracking-wider text-fg-tertiary"
              >
                Move type
              </label>
              <select
                id="move-type"
                value={moveType}
                onChange={(e) => setMoveType(e.target.value as MoveType)}
                className="h-9 w-full rounded-sm border border-border-default bg-elevated px-3 text-sm"
              >
                {HUMAN_MOVE_TYPES.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label
                htmlFor="author"
                className="mb-1 block text-xs font-medium uppercase tracking-wider text-fg-tertiary"
              >
                Author handle
              </label>
              <Input id="author" value={author} onChange={(e) => setAuthor(e.target.value)} />
            </div>
          </div>
          <div>
            <label
              htmlFor="targets"
              className="mb-1 block text-xs font-medium uppercase tracking-wider text-fg-tertiary"
            >
              Targets (optional, e.g. PROPOSAL@claude-opus#0014)
            </label>
            <Input id="targets" value={targets} onChange={(e) => setTargets(e.target.value)} />
          </div>

          {sections.map((name) => (
            <div key={name}>
              <label
                htmlFor={`s-${name}`}
                className="mb-1 block text-xs font-medium uppercase tracking-wider text-fg-tertiary"
              >
                {name}
              </label>
              <Textarea
                id={`s-${name}`}
                value={sectionValues[name] ?? ""}
                onChange={(e) => setSectionValues((prev) => ({ ...prev, [name]: e.target.value }))}
                placeholder={placeholderFor(name)}
                className="min-h-[5rem]"
              />
            </div>
          ))}

          {error ? <p className="text-xs text-accent-danger">{error}</p> : null}

          <div className="flex items-center justify-end gap-2 pt-2">
            <Button variant="outline" onClick={onClose} disabled={submitting}>
              Cancel
            </Button>
            <Button variant="primary" onClick={submit} disabled={submitting}>
              {submitting ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              Submit move
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function placeholderFor(name: string): string | undefined {
  switch (name) {
    case "Summary line":
      return "One sentence, ≤120 chars, plain English. e.g. 'v1 ships trial-only (14d), free-tier revisited at month 6.'";
    case "Stakes":
      return "trivial | tactical | strategic | irreversible";
    case "Spawns ADR?":
    case "Spawns task?":
      return "yes | no";
    case "Force level":
      return "advisory | strong | overriding";
    default:
      return undefined;
  }
}
