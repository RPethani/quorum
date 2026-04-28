"use client";

import { cn } from "@/lib/utils";
import { createContext, useContext, useId, useState } from "react";
import type { HTMLAttributes, ReactNode } from "react";

type TabsContext = {
  value: string;
  setValue: (v: string) => void;
  groupId: string;
};

const Ctx = createContext<TabsContext | null>(null);

function useTabs() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("Tabs subcomponents must be used inside <Tabs>.");
  return ctx;
}

export function Tabs({
  defaultValue,
  children,
  className,
}: {
  defaultValue: string;
  children: ReactNode;
  className?: string;
}) {
  const [value, setValue] = useState(defaultValue);
  const groupId = useId();
  return (
    <Ctx.Provider value={{ value, setValue, groupId }}>
      <div className={className}>{children}</div>
    </Ctx.Provider>
  );
}

export function TabsList({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      role="tablist"
      className={cn("flex items-center gap-2 border-b border-border-default", className)}
      {...props}
    />
  );
}

export function TabsTrigger({
  value,
  children,
  className,
}: {
  value: string;
  children: ReactNode;
  className?: string;
}) {
  const { value: active, setValue, groupId } = useTabs();
  const isActive = active === value;
  return (
    <button
      type="button"
      role="tab"
      id={`${groupId}-tab-${value}`}
      aria-selected={isActive}
      aria-controls={`${groupId}-panel-${value}`}
      onClick={() => setValue(value)}
      className={cn(
        "relative inline-flex h-9 items-center px-3 text-sm font-medium transition-colors duration-100",
        "-mb-px border-b-2",
        isActive
          ? "border-accent-primary text-fg-primary"
          : "border-transparent text-fg-secondary hover:text-fg-primary",
        className,
      )}
    >
      {children}
    </button>
  );
}

export function TabsContent({
  value,
  children,
  className,
}: {
  value: string;
  children: ReactNode;
  className?: string;
}) {
  const { value: active, groupId } = useTabs();
  if (active !== value) return null;
  return (
    <div
      role="tabpanel"
      id={`${groupId}-panel-${value}`}
      aria-labelledby={`${groupId}-tab-${value}`}
      className={cn("pt-4", className)}
    >
      {children}
    </div>
  );
}
