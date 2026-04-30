"use client";

import type { DeliberationListItem, EventRecord } from "@/lib/api/conductor";
import { formatLocalTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import {
  type Vendor,
  detectVendorFromHandle,
  displayNameForHandle,
  vendorColor,
} from "@/lib/vendor";
import { MessageSquare } from "lucide-react";
import { useLayoutEffect, useMemo, useRef, useState } from "react";

/**
 * Plain-English activity feed with hand-rolled fixed-height virtual
 * scrolling.
 *
 * Each item is a single-line row of fixed height (`ROW_HEIGHT`). At
 * any scroll position we render only the rows currently in view plus
 * a small over-scan buffer; the rest of the list is represented by a
 * tall spacer div so the scrollbar reflects the full length. This
 * scales to thousands of events without breaking a sweat and keeps
 * the chrome footprint stable (no layout shift as items stream in).
 *
 * Items are sized at `ROW_HEIGHT` and use `truncate` so a long
 * deliberation title doesn't wrap and break the virtualization
 * assumption. The full string is available via tooltip / hover (or
 * the Raw view, which renders the same events without truncation).
 */
const ROW_HEIGHT = 44;
const OVERSCAN = 4;

type FeedRow = {
  key: string;
  /** The participant's display name (rendered in vendor colour). */
  subject: string;
  /** The vendor whose colour the subject is rendered in. */
  vendor: Vendor;
  /** The rest of the sentence, after the subject. */
  rest: string;
  timestamp: string;
};

export function VirtualFeed({
  events,
  deliberations,
  className,
}: {
  events: EventRecord[];
  deliberations: DeliberationListItem[];
  className?: string;
}) {
  const titleFor = useMemo(() => {
    const byId: Record<string, string> = {};
    for (const d of deliberations) byId[d.id] = d.title || `question ${d.id}`;
    return (id: string | undefined) => (id ? (byId[id] ?? `question ${id}`) : "this question");
  }, [deliberations]);

  // Newest-first, dropping events that have no plain-English phrasing.
  const rows = useMemo<FeedRow[]>(() => {
    const out: FeedRow[] = [];
    for (let i = events.length - 1; i >= 0; i--) {
      const e = events[i];
      if (!e) continue;
      const phrased = phrase(e, titleFor);
      if (phrased === null) continue;
      out.push({
        key: `${e.ts ?? "?"}-${i}-${e.type}`,
        subject: phrased.subject,
        vendor: phrased.vendor,
        rest: phrased.rest,
        timestamp: formatLocalTime(e.ts as string | undefined),
      });
    }
    return out;
  }, [events, titleFor]);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  // Default to 600 so the very first paint renders enough rows to
  // fill a typical viewport even before measurement lands. The real
  // value replaces it synchronously in the layout effect below.
  const [viewportHeight, setViewportHeight] = useState(600);

  // useLayoutEffect runs after DOM commit but BEFORE paint, so the
  // viewport measurement lands on the same frame the rows render
  // instead of one frame later (which was leaving the viewport at 0
  // for that frame and only painting the over-scan slice).
  useLayoutEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const measure = () => {
      const h = el.clientHeight;
      if (h > 0) setViewportHeight(h);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  if (rows.length === 0) {
    return (
      <div className={cn("flex flex-col items-center justify-center text-center py-12", className)}>
        <MessageSquare size={32} className="text-fg-tertiary mb-2" strokeWidth={1.5} />
        <p className="text-sm text-fg-tertiary">
          Nothing happening yet — agents will start when you finish setup.
        </p>
      </div>
    );
  }

  const startIndex = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
  const visibleCount = Math.ceil(viewportHeight / ROW_HEIGHT) + OVERSCAN * 2;
  const endIndex = Math.min(rows.length, startIndex + visibleCount);
  const visibleRows = rows.slice(startIndex, endIndex);
  const topSpacer = startIndex * ROW_HEIGHT;
  const bottomSpacer = (rows.length - endIndex) * ROW_HEIGHT;

  return (
    <div
      ref={containerRef}
      onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}
      className={cn("h-full overflow-y-auto", className)}
    >
      {topSpacer > 0 ? <div style={{ height: topSpacer }} aria-hidden="true" /> : null}
      {visibleRows.map((r) => (
        <div
          key={r.key}
          style={{ height: ROW_HEIGHT }}
          className="flex items-center justify-between gap-3 border-b border-border-default px-4 text-sm"
        >
          <span className="min-w-0 flex-1 truncate" title={`${r.subject} ${r.rest}`}>
            <span style={{ color: vendorColor(r.vendor) }} className="font-medium">
              {r.subject}
            </span>
            <span className="text-fg-primary"> {r.rest}</span>
          </span>
          <span className="shrink-0 font-mono text-[11px] text-fg-tertiary tabular-nums">
            {r.timestamp}
          </span>
        </div>
      ))}
      {bottomSpacer > 0 ? <div style={{ height: bottomSpacer }} aria-hidden="true" /> : null}
    </div>
  );
}

// ---------------------------------------------------------------------- //
// Phrasing
// ---------------------------------------------------------------------- //

type Phrasing = { subject: string; vendor: Vendor; rest: string };

function phrase(e: EventRecord, titleFor: (id: string | undefined) => string): Phrasing | null {
  const rawHandle = (e.handle as string | undefined) ?? "";
  const moveType = (e.move_type as string | undefined) ?? "";
  const delibId = (e.deliberation_id as string | undefined) ?? undefined;
  const what = titleFor(delibId);
  const subject = rawHandle ? displayNameForHandle(rawHandle) : "Someone";
  const vendor = rawHandle ? detectVendorFromHandle(rawHandle) : "unknown";
  const wrap = (rest: string): Phrasing => ({ subject, vendor, rest });

  switch (e.type) {
    case "move_appended": {
      const verb = phraseForMove(moveType);
      if (!verb) return wrap(`updated "${what}"`);
      return wrap(`${verb} on "${what}"`);
    }
    case "agent_completed":
      return null; // covered by the move_appended that follows
    case "agent_started":
      return wrap(`is working on "${what}"`);
    case "agent_failed":
      return wrap(
        `couldn't finish on "${what}" — ${(e.reason as string | undefined) ?? "agent error"}`,
      );
    case "validation_failed":
      return wrap(`sent something Quorum couldn't accept on "${what}"`);
    case "routing_decision":
      return null;
    case "manifest_ratified":
      return { subject: "Plan", vendor: "unknown", rest: "locked in." };
    default:
      return null;
  }
}

function phraseForMove(moveType: string): string | null {
  switch (moveType) {
    case "PROPOSAL":
      return "shared an initial take";
    case "CRITIQUE":
      return "pushed back";
    case "SYNTHESIS":
      return "reconciled the discussion";
    case "DECISION":
      return "decided";
    case "OVERRIDE":
      return "made a final call";
    case "DROP":
      return "dropped this thread";
    case "QUESTION":
      return "asked a question";
    case "ANSWER":
      return "answered";
    case "INTERJECTION":
      return "added a quick note";
    case "REOPEN":
      return "reopened the discussion";
    case "STEER":
      return "redirected the discussion";
    case "CLARIFY":
      return "clarified";
    default:
      return null;
  }
}
