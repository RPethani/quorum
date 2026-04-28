import Link from "next/link";
import { ThemeToggle } from "@/components/design-system/theme-toggle";

export default function HomePage() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Quorum</h1>
          <p className="mt-2 text-sm text-fg-secondary">
            Where premium AI subscriptions deliberate together.
          </p>
        </div>
        <ThemeToggle />
      </div>

      <p className="mt-8 text-sm text-fg-secondary">
        Quorum is under construction. The product UI ships in later phases. For now, this app
        hosts the design-system showcase — the verification surface for the foundational tokens
        and primitives.
      </p>

      <div className="mt-6">
        <Link
          href="/_design-system"
          className="inline-flex h-9 items-center rounded-md border border-border-default bg-elevated px-4 text-sm font-medium hover:bg-recessed transition-colors duration-100"
        >
          Open the design-system showcase →
        </Link>
      </div>
    </main>
  );
}
