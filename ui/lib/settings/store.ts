"use client";

import { useEffect, useState } from "react";

/**
 * Tiny client-side settings store backed by `localStorage`.
 *
 * Why not a full state library:
 *   - These are user-preference toggles (composer behaviour, theme,
 *     per-pane state). Each one is independent, scoped to the
 *     browser, doesn't need to roundtrip through the conductor.
 *   - The whole module is ~30 lines and avoids a dep.
 *
 * Cross-component reactivity is provided by an internal pub-sub: any
 * `setSetting` notifies every `useSetting` hook so a change in the
 * Settings dialog updates the Composer immediately. The browser's
 * `storage` event also fires on changes from *other tabs*, so a
 * second tab open on the same workspace stays in sync.
 *
 * SSR-safety: the initial render returns the supplied default; an
 * effect on mount reads the real value and re-renders. This avoids
 * hydration mismatches in Next.js.
 */

const STORAGE_PREFIX = "quorum.settings.";

const listeners = new Set<() => void>();

function notify(): void {
  for (const fn of listeners) fn();
}

function readRaw(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(STORAGE_PREFIX + key);
  } catch {
    return null;
  }
}

function writeRaw(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_PREFIX + key, value);
  } catch {
    /* quota exceeded / privacy mode — silently no-op */
  }
}

export function getSetting<T extends string>(key: string, defaultValue: T): T {
  const raw = readRaw(key);
  return (raw as T | null) ?? defaultValue;
}

export function setSetting<T extends string>(key: string, value: T): void {
  writeRaw(key, value);
  notify();
}

export function useSetting<T extends string>(key: string, defaultValue: T): [T, (next: T) => void] {
  const [value, setLocal] = useState<T>(defaultValue);

  useEffect(() => {
    function refresh(): void {
      setLocal(getSetting(key, defaultValue));
    }
    refresh();
    listeners.add(refresh);
    // Keep tabs in sync — `storage` only fires on changes from *other* tabs.
    function onStorage(e: StorageEvent): void {
      if (e.key === STORAGE_PREFIX + key) refresh();
    }
    if (typeof window !== "undefined") {
      window.addEventListener("storage", onStorage);
    }
    return () => {
      listeners.delete(refresh);
      if (typeof window !== "undefined") {
        window.removeEventListener("storage", onStorage);
      }
    };
  }, [key, defaultValue]);

  return [value, (next: T) => setSetting(key, next)];
}

// ---------------------------------------------------------------------- //
// Known settings — keep names + defaults centralised so the dialog and
// the consumers don't drift on string keys.
// ---------------------------------------------------------------------- //

export type ComposerSendKey = "enter" | "button";

export const SETTINGS = {
  /**
   * What pressing Enter does in the chat composer.
   *
   * - `enter`  — Enter sends; Shift+Enter inserts a newline.
   * - `button` — Enter inserts a newline; send is button-only (D11
   *   default — keeps long lists / code blocks / paragraphs from
   *   getting clipped mid-thought).
   */
  composerSendKey: {
    key: "composerSendKey" as const,
    default: "button" as ComposerSendKey,
  },
} as const;
