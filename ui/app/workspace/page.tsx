"use client";

import { ArtifactPane } from "@/components/canvas/artifact-pane";
import { ChatPane } from "@/components/canvas/chat-pane";
import { EditableTitle } from "@/components/canvas/editable-title";
import { ParticipantsDialog } from "@/components/canvas/participants-dialog";
import { ParticipantsStack } from "@/components/canvas/participants-stack";
import { ThemeToggle } from "@/components/design-system/theme-toggle";
import { AddAgentDialog } from "@/components/dialogs/add-agent-dialog";
import { ContextDialog } from "@/components/dialogs/context-dialog";
import { SettingsDialog } from "@/components/dialogs/settings-dialog";
import { Tooltip } from "@/components/ui/tooltip";
import type { ParticipantRow } from "@/lib/api/conductor";
import { getParticipants } from "@/lib/api/conductor";
import { useCanvasArtifacts, useCanvasMessages, useCanvasState } from "@/lib/canvas/use-canvas";
import { FolderGit2, Plus, Settings } from "lucide-react";
import Image from "next/image";
import { useCallback, useEffect, useState } from "react";

/**
 * Canvas — the new brainstorming surface (per `docs-specs/canvas-redesign.md`).
 *
 * Two-pane layout (D1): chat on the left at ~60%, one live artifact on
 * the right at ~40%. Both panes are full-height; the header sits above,
 * a thin status bar below.
 */
export default function CanvasPage() {
  const { state, reload: reloadState } = useCanvasState();
  const { messages } = useCanvasMessages();
  const [activeFilename, setActiveFilename] = useState<string | null>(null);
  const {
    artifacts,
    active,
    prevActive,
    reload: reloadArtifacts,
  } = useCanvasArtifacts(activeFilename);
  const [participants, setParticipants] = useState<ParticipantRow[]>([]);
  const [addAgentOpen, setAddAgentOpen] = useState(false);
  const [participantsDialogOpen, setParticipantsDialogOpen] = useState(false);
  const [settingsDialogOpen, setSettingsDialogOpen] = useState(false);
  const [contextDialogOpen, setContextDialogOpen] = useState(false);

  const reloadParticipants = useCallback(async () => {
    try {
      setParticipants(await getParticipants());
    } catch {
      // ignore — the empty state handles missing participants
    }
  }, []);

  useEffect(() => {
    void reloadParticipants();
  }, [reloadParticipants]);

  // Keep activeFilename pointing at a real artifact.
  useEffect(() => {
    if (artifacts.length === 0) {
      if (activeFilename !== null) setActiveFilename(null);
      return;
    }
    if (activeFilename && !artifacts.some((a) => a.filename === activeFilename)) {
      setActiveFilename(artifacts[0].filename);
    }
  }, [artifacts, activeFilename]);

  return (
    <div className="flex h-screen flex-col bg-recessed">
      <Header
        title={state?.title ?? "Untitled brainstorm"}
        participants={participants}
        onOpenParticipants={() => setParticipantsDialogOpen(true)}
        onAddParticipant={() => setAddAgentOpen(true)}
        onOpenSettings={() => setSettingsDialogOpen(true)}
        onOpenContext={() => setContextDialogOpen(true)}
        onTitleChanged={() => void reloadState()}
      />
      <main className="flex flex-1 min-h-0">
        {/* Chat pane — the primary work surface, on the brightest background. */}
        <section className="flex w-[60%] min-w-0 flex-col bg-canvas border-r-2 border-border-default">
          <ChatPane messages={messages} participants={participants} onAfterSend={reloadArtifacts} />
        </section>
        {/* Artifact pane — secondary surface, subtly recessed so it reads as a side panel. */}
        <section className="flex w-[40%] min-w-0 flex-col bg-recessed">
          <ArtifactPane
            artifacts={artifacts}
            active={active}
            prevBody={prevActive}
            activeFilename={activeFilename ?? artifacts[0]?.filename ?? null}
            onSelect={setActiveFilename}
            onAfterDelete={reloadArtifacts}
          />
        </section>
      </main>
      <StatusBar cost={state?.cost ?? null} participantCount={participants.length} />
      <ParticipantsDialog
        open={participantsDialogOpen}
        onClose={() => setParticipantsDialogOpen(false)}
        participants={participants}
        onAdd={() => {
          setParticipantsDialogOpen(false);
          setAddAgentOpen(true);
        }}
      />
      <SettingsDialog
        open={settingsDialogOpen}
        onClose={() => setSettingsDialogOpen(false)}
        digesterHandle={state?.digester_handle ?? ""}
        participants={participants}
        onDigesterChanged={() => void reloadState()}
      />
      <ContextDialog
        open={contextDialogOpen}
        onClose={() => setContextDialogOpen(false)}
        digesterHandle={state?.digester_handle ?? ""}
      />
      <AddAgentDialog
        open={addAgentOpen}
        onClose={() => setAddAgentOpen(false)}
        onAdded={() => {
          setAddAgentOpen(false);
          void reloadParticipants();
        }}
      />
    </div>
  );
}

function Header({
  title,
  participants,
  onOpenParticipants,
  onAddParticipant,
  onOpenSettings,
  onOpenContext,
  onTitleChanged,
}: {
  title: string;
  participants: ParticipantRow[];
  onOpenParticipants: () => void;
  onAddParticipant: () => void;
  onOpenSettings: () => void;
  onOpenContext: () => void;
  onTitleChanged: () => void;
}) {
  const cliCount = participants.filter((p) => p.transport === "cli").length;
  return (
    <header className="relative z-10 flex items-center justify-between border-b border-border-default bg-elevated px-4 py-2.5 shadow-[0_1px_2px_0_rgba(0,0,0,0.04)]">
      <div className="flex items-center gap-3 min-w-0">
        <Image
          src="/brand/quorum-logo-icon.jpg"
          alt="Quorum"
          width={28}
          height={28}
          priority
          className="shrink-0 rounded-md"
        />
        <span className="hidden sm:block h-5 w-px bg-border-default" aria-hidden="true" />
        <EditableTitle title={title} onChanged={onTitleChanged} />
      </div>
      <div className="flex items-center gap-3 text-[11px]">
        {cliCount === 0 ? (
          <button
            type="button"
            onClick={onAddParticipant}
            className="inline-flex items-center gap-1 rounded-full border border-accent-warning/40 bg-accent-warning-weak px-2 py-0.5 font-medium text-accent-warning hover:bg-accent-warning-weak/70"
          >
            <Plus size={10} strokeWidth={2.5} />0 participants — add one
          </button>
        ) : (
          <ParticipantsStack
            participants={participants}
            onOpen={onOpenParticipants}
            onAdd={onAddParticipant}
          />
        )}
        <ThemeToggle />
        <Tooltip label="Context" side="bottom" align="end">
          <button
            type="button"
            onClick={onOpenContext}
            aria-label="Context"
            className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-border-default text-fg-secondary hover:bg-recessed hover:text-fg-primary"
          >
            <FolderGit2 size={14} strokeWidth={2} />
          </button>
        </Tooltip>
        <Tooltip label="Settings" side="bottom" align="end">
          <button
            type="button"
            onClick={onOpenSettings}
            aria-label="Settings"
            className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-border-default text-fg-secondary hover:bg-recessed hover:text-fg-primary"
          >
            <Settings size={14} strokeWidth={2} />
          </button>
        </Tooltip>
      </div>
    </header>
  );
}

function StatusBar({
  cost,
  participantCount,
}: {
  cost: { spent: number; cap: number; enforce: boolean } | null;
  participantCount: number;
}) {
  return (
    <footer className="relative z-10 flex items-center justify-between border-t border-border-emphasis bg-sunken px-4 py-1.5 text-[11px] text-fg-tertiary">
      <span>
        cost{" "}
        <span className="tabular-nums text-fg-secondary">${cost?.spent.toFixed(2) ?? "0.00"}</span>{" "}
        / <span className="tabular-nums text-fg-secondary">${cost?.cap.toFixed(2) ?? "—"}</span>
      </span>
      <span>
        {participantCount} participant{participantCount === 1 ? "" : "s"}
      </span>
    </footer>
  );
}
