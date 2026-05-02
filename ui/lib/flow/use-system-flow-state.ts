"use client";

import {
  type Ask,
  type DeliberationListItem,
  type EventRecord,
  type ManifestResponse,
  type ParticipantRow,
  type PlanResponse,
  type WorkspaceStateResponse,
  getAsks,
  getDeliberations,
  getEvents,
  getManifest,
  getParticipants,
  getPlan,
  getState,
} from "@/lib/api/conductor";
import { useCallback, useEffect, useState } from "react";
import { type DeriveInput, deriveSystemFlowState } from "./derive";
import type { SystemFlowState } from "./types";

/**
 * Fetches every input the diagram derives from and keeps it fresh.
 *
 * Cadence is event-driven where possible (the workspace page already
 * subscribes to the SSE stream and bumps a `reloadKey`) plus a 5s
 * fallback poll. Mounting a second copy of this hook is fine; the
 * fetches are cached briefly by the browser and the API is local.
 */
export function useSystemFlowState(reloadKey: number): SystemFlowState | null {
  const [snapshot, setSnapshot] = useState<SystemFlowState | null>(null);

  const reload = useCallback(async () => {
    void reloadKey; // referenced so the callback rebuilds on bump
    try {
      const [state, manifest, deliberations, participants, asks, plan, events] = await Promise.all([
        getState().catch(() => null as WorkspaceStateResponse | null),
        getManifest().catch(() => null as ManifestResponse | null),
        getDeliberations().catch(() => [] as DeliberationListItem[]),
        getParticipants().catch(() => [] as ParticipantRow[]),
        getAsks().catch(() => [] as Ask[]),
        getPlan().catch(() => null as PlanResponse | null),
        getEvents(0)
          .then((r) => r.events)
          .catch(() => [] as EventRecord[]),
      ]);
      const input: DeriveInput = {
        state,
        manifest,
        deliberations,
        participants,
        asks,
        plan,
        events,
      };
      setSnapshot(deriveSystemFlowState(input));
    } catch {
      // ignore
    }
  }, [reloadKey]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    const id = setInterval(() => void reload(), 5_000);
    return () => clearInterval(id);
  }, [reload]);

  return snapshot;
}
