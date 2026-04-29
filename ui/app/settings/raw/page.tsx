"use client";

import { ThemeToggle } from "@/components/design-system/theme-toggle";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { type RawListing, getRawFile, getRawListing, saveRawFile } from "@/lib/api/conductor";
import { Save } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

/**
 * Phase-10 raw config editor (design-doc §9.8 Tier 3). One whitelisted
 * file at a time. No syntax highlighting in v1 — Phase 14 polish can
 * pull in CodeMirror once the surface stabilises.
 */
export default function RawSettingsPage() {
  const [listing, setListing] = useState<RawListing | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState<string>("");
  const [original, setOriginal] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const l = await getRawListing();
        setListing(l);
        const first = l.files.find((f) => f.exists)?.path ?? l.files[0]?.path ?? null;
        setSelected(first);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    })();
  }, []);

  useEffect(() => {
    if (!selected) {
      setContent("");
      setOriginal("");
      return;
    }
    void (async () => {
      try {
        const f = await getRawFile(selected);
        setContent(f.content);
        setOriginal(f.content);
        setMessage(null);
      } catch (e) {
        setContent("");
        setOriginal("");
        setError(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [selected]);

  async function save() {
    if (!selected) return;
    setSaving(true);
    setError(null);
    try {
      await saveRawFile(selected, content);
      setOriginal(content);
      setMessage(`Saved ${selected}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  const dirty = content !== original;

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
          <Link href="/settings" className="font-medium hover:text-accent-primary">
            Settings
          </Link>
          <span className="text-fg-tertiary">/</span>
          <span className="font-medium">Raw editor</span>
        </div>
        <ThemeToggle />
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">
        <Card>
          <CardHeader>
            <CardTitle>Raw config files</CardTitle>
            <p className="text-sm text-fg-secondary">
              Direct access to the workspace's whitelisted YAML / Markdown files. Edits write
              immediately. The config-yaml editor in Settings handles common adjustments without
              touching the raw file.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-3">
              <select
                value={selected ?? ""}
                onChange={(e) => setSelected(e.target.value || null)}
                className="h-9 rounded-sm border border-border-default bg-elevated px-3 text-sm font-mono"
              >
                {listing?.files.map((f) => (
                  <option key={f.path} value={f.path}>
                    {f.path} {f.exists ? "" : "(does not exist)"}
                  </option>
                ))}
              </select>
              <Button variant="primary" onClick={save} disabled={saving || !selected || !dirty}>
                <Save size={14} /> {dirty ? "Save" : "Saved"}
              </Button>
              {message ? <span className="text-xs text-accent-success">{message}</span> : null}
              {error ? <span className="text-xs text-accent-danger">{error}</span> : null}
            </div>
            <Textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="min-h-[28rem] font-mono text-xs leading-relaxed"
              spellCheck={false}
            />
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
