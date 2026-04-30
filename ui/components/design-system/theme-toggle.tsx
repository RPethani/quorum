"use client";

import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

const OPTIONS = [
  { value: "light", label: "Light", Icon: Sun },
  { value: "system", label: "System", Icon: Monitor },
  { value: "dark", label: "Dark", Icon: Moon },
] as const;

/**
 * Three-state segmented theme toggle: light / system / dark.
 * Renders nothing until mounted to avoid hydration mismatch.
 */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return <div className="h-8 w-[5.25rem]" aria-hidden />;
  }

  return (
    <div
      aria-label="Theme"
      className="inline-flex items-center gap-0 rounded-md border border-border-default bg-elevated p-0.5"
    >
      {OPTIONS.map(({ value, label, Icon }) => {
        const active = theme === value;
        return (
          <Tooltip key={value} label={label}>
            <button
              type="button"
              aria-pressed={active}
              aria-label={label}
              onClick={() => setTheme(value)}
              className={cn(
                "inline-flex h-7 w-7 items-center justify-center rounded-sm transition-colors duration-100",
                active
                  ? "bg-accent-primary-weak text-accent-primary"
                  : "text-fg-secondary hover:text-fg-primary",
              )}
            >
              <Icon size={14} strokeWidth={1.5} />
            </button>
          </Tooltip>
        );
      })}
    </div>
  );
}
