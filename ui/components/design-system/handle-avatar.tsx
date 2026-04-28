import { cn } from "@/lib/utils";

// Avatar palette — independent of the 5 accents, deliberately desaturated
// so avatars never compete with semantic accent usage. Per
// DESIGN_SYSTEM.md §7: 8 colors, mid-tones that read in both light and
// dark modes. A 1px border on the dark mid-tone keeps separation.
const AVATAR_COLORS: ReadonlyArray<{ bg: string; fg: string }> = [
  { bg: "#C7D2FE", fg: "#3730A3" }, // indigo
  { bg: "#FBCFE8", fg: "#9D174D" }, // pink
  { bg: "#FDE68A", fg: "#92400E" }, // amber
  { bg: "#A7F3D0", fg: "#065F46" }, // emerald
  { bg: "#BAE6FD", fg: "#075985" }, // sky
  { bg: "#DDD6FE", fg: "#5B21B6" }, // violet
  { bg: "#FECDD3", fg: "#9F1239" }, // rose
  { bg: "#D9F99D", fg: "#3F6212" }, // lime
];

function hash(str: string): number {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = (h << 5) - h + str.charCodeAt(i);
    h |= 0;
  }
  return Math.abs(h);
}

const SIZES = {
  sm: { box: "h-6 w-6", text: "text-xs" },
  md: { box: "h-8 w-8", text: "text-sm" },
  lg: { box: "h-10 w-10", text: "text-md" },
} as const;

export type HandleAvatarProps = {
  handle: string;
  size?: keyof typeof SIZES;
  className?: string;
};

export function HandleAvatar({ handle, size = "md", className }: HandleAvatarProps) {
  const color = AVATAR_COLORS[hash(handle) % AVATAR_COLORS.length];
  const initial = handle.replace(/^@/, "").charAt(0).toUpperCase() || "?";
  const sz = SIZES[size];
  return (
    <span
      aria-label={handle}
      title={handle}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full font-mono font-medium",
        sz.box,
        sz.text,
        className,
      )}
      style={{ backgroundColor: color.bg, color: color.fg }}
    >
      {initial}
    </span>
  );
}
