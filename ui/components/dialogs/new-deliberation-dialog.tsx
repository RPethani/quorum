"use client";

import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { createDeliberation } from "@/lib/api/conductor";
import { Loader2, Plus } from "lucide-react";
import { useEffect, useState } from "react";

/**
 * Spawn a fresh deliberation. After the seed manifest deliberation is
 * decided, this is how the user kicks off real work — pick an artifact
 * from the manifest, give it a title and a one-paragraph question, hit
 * Create. The conductor's planner then routes a PROPOSAL to whichever
 * agent fits the proposer role.
 */
export function NewDeliberationDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated?: (id: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [question, setQuestion] = useState("");
  const [tags, setTags] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setTitle("");
    setQuestion("");
    setTags("");
    setError(null);
    setSubmitting(false);
  }, [open]);

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      const tagList = tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      const res = await createDeliberation({
        title: title.trim(),
        question: question.trim(),
        ...(tagList.length ? { tags: tagList } : {}),
      });
      onCreated?.(res.id);
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  const valid = title.trim().length > 0 && question.trim().length > 0;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Start a new deliberation"
      description="Frame one question for the agents to work through. They'll author a PROPOSAL, then critiques, then a synthesis. You decide."
      size="md"
    >
      <div className="space-y-4">
        <fieldset className="block border-0 p-0">
          <legend className="mb-1 block text-xs font-medium uppercase tracking-wider text-fg-tertiary">
            Title
          </legend>
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Pick the v2 direction"
          />
          <p className="mt-1 text-xs text-fg-tertiary">
            Short, descriptive. Becomes the deliberation's display name.
          </p>
        </fieldset>

        <fieldset className="block border-0 p-0">
          <legend className="mb-1 block text-xs font-medium uppercase tracking-wider text-fg-tertiary">
            Question
          </legend>
          <Textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            className="min-h-[8rem]"
            placeholder={
              "What single question should the agents resolve?\n\n" +
              "e.g. Which of the five v2 directions should we ship by month 3, given the five non-negotiable constraints listed in the problem statement?"
            }
          />
          <p className="mt-1 text-xs text-fg-tertiary">
            Frame it as a decision the deliberation must reach. The agents start from here.
          </p>
        </fieldset>

        <fieldset className="block border-0 p-0">
          <legend className="mb-1 block text-xs font-medium uppercase tracking-wider text-fg-tertiary">
            Tags
          </legend>
          <Input
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="strategy, v2 (comma-separated)"
            className="font-mono"
          />
          <p className="mt-1 text-xs text-fg-tertiary">Optional.</p>
        </fieldset>

        {error ? <p className="text-sm text-accent-danger">{error}</p> : null}
      </div>

      <DialogFooter>
        <Button variant="outline" onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button variant="primary" onClick={submit} disabled={!valid || submitting}>
          {submitting ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
          Create deliberation
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
