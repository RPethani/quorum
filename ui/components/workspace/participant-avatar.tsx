"use client";

import { cn } from "@/lib/utils";
import {
  type ParticipantLike,
  type Vendor,
  detectVendor,
  displayName,
  vendorColor,
} from "@/lib/vendor";

/**
 * A round avatar for one participant — vendor logo (Anthropic /
 * Google / OpenAI), human icon for the human, or a coloured initials
 * disc for unknown vendors. The coloured ring carries health status
 * when available.
 *
 * Vendor detection, colour, and display-name come from `lib/vendor.ts`
 * — same source as the activity-feed tinting, so a participant always
 * looks the same wherever their name appears.
 */
export function ParticipantAvatar({
  participant,
  size = 24,
}: {
  participant: ParticipantLike & {
    live_health?: { on_path: boolean | null; note: string; transport: string } | null;
  };
  size?: number;
}) {
  const vendor = detectVendor(participant);
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center rounded-full ring-2 bg-elevated transition-colors",
        ringClass(participant),
      )}
      style={{ width: size, height: size }}
      role="img"
      aria-label={tooltipFor(participant)}
    >
      <Glyph vendor={vendor} participant={participant} size={size - 8} />
    </span>
  );
}

export function tooltipFor(p: ParticipantLike): string {
  const name = displayName(p);
  const status = statusLabel(p);
  return status ? `${name} — ${status}` : name;
}

function statusLabel(
  p: ParticipantLike & {
    live_health?: { on_path: boolean | null; note: string; transport: string } | null;
  },
): string {
  if (p.transport === "manual") return "you";
  const live = p.live_health;
  if (!live) return "status unknown";
  if (live.on_path === true) return "ready";
  if (live.on_path === false) return live.note || "not reachable";
  return "status unknown";
}

function ringClass(
  p: ParticipantLike & {
    live_health?: { on_path: boolean | null; note: string; transport: string } | null;
  },
): string {
  if (p.transport === "manual") return "ring-accent-primary/40";
  const live = p.live_health;
  if (!live) return "ring-border-default";
  if (live.on_path === true) return "ring-accent-success/60";
  if (live.on_path === false) return "ring-accent-danger/60";
  return "ring-border-default";
}

function Glyph({
  vendor,
  participant,
  size,
}: {
  vendor: Vendor;
  participant: ParticipantLike;
  size: number;
}) {
  switch (vendor) {
    case "anthropic":
      return <AnthropicGlyph size={size} />;
    case "google":
      return <GoogleGlyph size={size} />;
    case "openai":
      return <OpenAIGlyph size={size} />;
    case "human":
      return <HumanGlyph size={size} />;
    default:
      return <InitialsGlyph participant={participant} size={size} />;
  }
}

// ---------------------------------------------------------------------- //
// Brand glyphs — inlined SVGs.
// ---------------------------------------------------------------------- //

function AnthropicGlyph({ size }: { size: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      style={{ color: vendorColor("anthropic") }}
    >
      <path d="M16.13 3.5h-3.21l5.84 17h3.21l-5.84-17Zm-8.26 0L2 20.5h3.27l1.21-3.45h6.04l1.2 3.45H17L11.13 3.5H7.87Zm-.36 10.65 2-5.7 2 5.7H7.51Z" />
    </svg>
  );
}

function GoogleGlyph({ size }: { size: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      style={{ color: vendorColor("google") }}
    >
      <path d="M12 2c.5 4.5 3.5 7.5 8 8-4.5.5-7.5 3.5-8 8-.5-4.5-3.5-7.5-8-8 4.5-.5 7.5-3.5 8-8Z" />
    </svg>
  );
}

function OpenAIGlyph({ size }: { size: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      style={{ color: vendorColor("openai") }}
    >
      <path d="M21.55 10.05a5.4 5.4 0 0 0-.46-4.42 5.46 5.46 0 0 0-5.88-2.62 5.46 5.46 0 0 0-9.27 1.97 5.46 5.46 0 0 0-3.65 2.65 5.46 5.46 0 0 0 .67 6.4 5.4 5.4 0 0 0 .46 4.43 5.46 5.46 0 0 0 5.88 2.62 5.45 5.45 0 0 0 4.11 1.83 5.46 5.46 0 0 0 5.16-3.79 5.46 5.46 0 0 0 3.65-2.65 5.45 5.45 0 0 0-.67-6.42Zm-8.13 11.36a4.05 4.05 0 0 1-2.6-.94l.13-.07 4.32-2.5a.7.7 0 0 0 .35-.61V11.2l1.83 1.06v5.05a4.06 4.06 0 0 1-4.03 4.1Zm-8.7-3.71a4.05 4.05 0 0 1-.48-2.71l.13.08 4.32 2.5a.7.7 0 0 0 .7 0l5.27-3.04v2.11a.07.07 0 0 1-.03.06l-4.37 2.52a4.06 4.06 0 0 1-5.54-1.52Zm-1.13-9.4a4.05 4.05 0 0 1 2.12-1.78v5.14a.7.7 0 0 0 .35.6l5.25 3.03-1.83 1.06-4.37-2.53a4.06 4.06 0 0 1-1.52-5.52Zm15 3.49-5.27-3.05 1.83-1.05 4.37 2.52a4.06 4.06 0 0 1-.62 7.32V12.5a.7.7 0 0 0-.31-.6Zm1.82-2.74-.13-.08-4.32-2.5a.7.7 0 0 0-.7 0l-5.27 3.05V8.4a.07.07 0 0 1 .03-.06l4.37-2.52a4.06 4.06 0 0 1 6.02 4.21Zm-11.42 3.78-1.83-1.06v-5.04a4.06 4.06 0 0 1 6.65-3.13l-.13.07-4.32 2.5a.7.7 0 0 0-.35.6Zm.99-2.14L12 9.65l2.34 1.34v2.7L12 15.04l-2.34-1.35Z" />
    </svg>
  );
}

function HumanGlyph({ size }: { size: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="text-accent-primary"
    >
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

function InitialsGlyph({
  participant,
  size,
}: {
  participant: ParticipantLike;
  size: number;
}) {
  const name = displayName(participant);
  const initial = name.charAt(0).toUpperCase() || "?";
  return (
    <span
      style={{ width: size, height: size, fontSize: size * 0.6 }}
      className="inline-flex items-center justify-center rounded-full bg-recessed font-semibold text-fg-secondary"
    >
      {initial}
    </span>
  );
}
