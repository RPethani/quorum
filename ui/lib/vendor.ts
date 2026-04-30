/**
 * Vendor detection + per-vendor brand colour and display-name mapping.
 *
 * Single source of truth for "which logo/colour/name does this
 * participant get?" — used by `<ParticipantAvatar>` for the avatar
 * stack and by every activity-feed renderer for tinting participant
 * names. Adding a new vendor means editing this one file.
 *
 * Colours are deliberate brand-adjacent mid-tones picked to read in
 * both light and dark modes without competing with the design
 * system's semantic accents.
 */

export type Vendor = "anthropic" | "google" | "openai" | "human" | "unknown";

export type ParticipantLike = {
  handle: string;
  display_name?: string | null;
  cli_command?: string | null;
  model?: string | null;
  transport?: string | null;
};

const VENDOR_COLOR: Record<Vendor, string> = {
  anthropic: "#cc785c", // clay — Anthropic's signature warm tone
  google: "#1a73e8", // Google blue
  openai: "#10a37f", // OpenAI teal/green
  human: "var(--color-accent-primary)", // workspace accent for the human
  unknown: "var(--color-fg-secondary)",
};

const HANDLE_TO_DISPLAY: Record<string, string> = {
  "@claude-opus": "Claude (Opus)",
  "@claude": "Claude",
  "@gemini": "Gemini",
  "@gemini-pro": "Gemini",
  "@gemini-flash": "Gemini",
  "@codex": "Codex",
  "@codex-gpt5": "Codex",
  "@rakesh": "You",
  "@human": "You",
  "@human-rohan": "You",
};

export function detectVendor(p: ParticipantLike): Vendor {
  if (p.transport === "manual") return "human";
  const blob = `${p.handle ?? ""} ${p.cli_command ?? ""} ${p.model ?? ""}`.toLowerCase();
  if (/\bclaude\b|opus|sonnet|haiku|anthropic/.test(blob)) return "anthropic";
  if (/\bgemini\b|google/.test(blob)) return "google";
  if (/\bcodex\b|openai|gpt|chatgpt/.test(blob)) return "openai";
  return "unknown";
}

/**
 * Best-guess vendor from a bare handle string. Less precise than
 * `detectVendor` because we don't have transport/model context, but
 * good enough for activity-feed tinting where only the handle is
 * present in the event record.
 */
export function detectVendorFromHandle(handle: string): Vendor {
  return detectVendor({ handle });
}

export function vendorColor(vendor: Vendor): string {
  return VENDOR_COLOR[vendor];
}

export function displayName(p: ParticipantLike): string {
  if (p.display_name && p.display_name !== "(none)") return p.display_name;
  if (HANDLE_TO_DISPLAY[p.handle]) return HANDLE_TO_DISPLAY[p.handle];
  return p.handle.replace(/^@/, "");
}

export function displayNameForHandle(handle: string): string {
  return displayName({ handle });
}
