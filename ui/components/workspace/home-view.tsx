"use client";

import {
  type Ask,
  type DeliberationListItem,
  type EventRecord,
  getOpenAsks,
} from "@/lib/api/conductor";
import { useCallback, useEffect, useState } from "react";
import { AskCard } from "./ask-card";
import { VirtualFeed } from "./virtual-feed";

/**
 * The default landing view, designed to fit a fixed-height column.
 *
 *   top    — status pill + open Ask cards (unscrolled chrome)
 *   bottom — activity feed inside a fixed-height scroll viewport with
 *            virtual scrolling, so 1000+ events stay smooth and the
 *            user can scroll back to the start.
 *
 * The parent renders this in a half-screen column; the feed fills
 * whatever vertical space is left after the chrome.
 */
export function HomeView({
  events,
  deliberations,
  reloadKey,
}: {
  events: EventRecord[];
  deliberations: DeliberationListItem[];
  /** Bumping this triggers a re-fetch of asks / plan. */
  reloadKey: number;
}) {
  const [asks, setAsks] = useState<Ask[]>([]);
  const [loaded, setLoaded] = useState(false);

  const reload = useCallback(async () => {
    void reloadKey; // referenced so identity rebuilds on bump
    try {
      setAsks(await getOpenAsks());
    } finally {
      setLoaded(true);
    }
  }, [reloadKey]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    const id = setInterval(() => void reload(), 5_000);
    return () => clearInterval(id);
  }, [reload]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      {asks.length > 0 ? (
        <div className="space-y-4 px-6 pt-6 pb-4">
          {asks.map((ask) => (
            <AskCard key={ask.id} ask={ask} onAnswered={reload} />
          ))}
        </div>
      ) : null}

      <div
        className={`flex flex-1 min-h-0 flex-col${
          asks.length > 0 ? " border-t border-border-default" : ""
        }`}
      >
        <div className="flex items-baseline justify-between px-6 py-2">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-fg-tertiary">
            What's been happening
          </h2>
          <span className="text-[11px] text-fg-tertiary tabular-nums">{events.length} events</span>
        </div>
        <div className="flex-1 min-h-0">
          {loaded ? (
            <VirtualFeed events={events} deliberations={deliberations} />
          ) : (
            <p className="px-6 py-6 text-sm text-fg-tertiary">Loading…</p>
          )}
        </div>
      </div>
    </div>
  );
}
