import {
  ArrowRight,
  BookOpen,
  Circle,
  CircleAlert,
  CircleCheck,
  CircleDot,
  CircleX,
  Clock,
  Copy,
  Download,
  FileText,
  KeyRound,
  MessageSquare,
  Pause,
  Play,
  RotateCw,
  Settings2,
  Users,
} from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CostChip } from "@/components/design-system/cost-chip";
import { HandleAvatar } from "@/components/design-system/handle-avatar";
import { ThemeToggle } from "@/components/design-system/theme-toggle";
import { MoveCard } from "@/components/deliberation/move-card";

/**
 * Design-system showcase route (/design-system). Every atom and component
 * variant the design system currently ships, rendered side-by-side so
 * light and dark modes can be flipped via the toggle in the header. This
 * is the verification surface for Phase 2. Not gated in v1 — the UI
 * only runs on a local dev server, which is the only place this surface
 * exists at all.
 *
 * Components NOT yet shipped are listed at the bottom under "Deferred"
 * with the phase that introduces them; they are pre-declared in
 * DESIGN_SYSTEM.md §7 so later phases have a target.
 */
export default function DesignSystemShowcase() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <Header />
      <Section title="Neutral scale" subtitle="Both modes use the same scale; mode flips foreground.">
        <NeutralSwatches />
      </Section>

      <Section title="Accents" subtitle="Five only. Each has a job; never decoration.">
        <AccentSwatches />
      </Section>

      <Section title="Typography" subtitle="Inter for UI, JetBrains Mono for machine text.">
        <TypeRamp />
      </Section>

      <Section title="Buttons" subtitle="Variants × sizes.">
        <Buttons />
      </Section>

      <Section title="Cards" subtitle="default, elevated, recessed.">
        <Cards />
      </Section>

      <Section title="Inputs" subtitle="Same focus treatment across input, textarea.">
        <Inputs />
      </Section>

      <Section title="Badges" subtitle="Weak background, strong text. One per accent + neutral.">
        <Badges />
      </Section>

      <Section title="Tabs" subtitle="Underline style, not pill.">
        <TabsDemo />
      </Section>

      <Section title="Separators" subtitle="1px, default border color.">
        <Separators />
      </Section>

      <Section title="Custom — CostChip" subtitle="Mono numerals; warning above 80% of ceiling.">
        <CostChips />
      </Section>

      <Section title="Custom — HandleAvatar" subtitle="Deterministic color from a fixed 8-color palette.">
        <Avatars />
      </Section>

      <Section title="Custom — MoveCard (skeleton)" subtitle="Phase 2 visual contract; Phase 7 fills it in.">
        <MoveCards />
      </Section>

      <Section title="Iconography" subtitle="Lucide, stroke-width 1.5. Standard mappings.">
        <Icons />
      </Section>

      <Section title="Deferred components" subtitle="Pre-declared in DESIGN_SYSTEM.md §7; built later.">
        <Deferred />
      </Section>
    </div>
  );
}

function Header() {
  return (
    <header className="mb-10 flex items-start justify-between gap-6">
      <div>
        <p className="text-xs font-medium uppercase tracking-wider text-fg-tertiary">
          Quorum
        </p>
        <h1 className="text-2xl font-bold tracking-tight">Design system — v0.1</h1>
        <p className="mt-1 text-sm text-fg-secondary">
          Verification surface for tokens and primitives. Toggle theme to inspect both modes.
        </p>
        <Link
          href="/"
          className="mt-3 inline-flex items-center gap-1 text-xs text-fg-tertiary hover:text-fg-primary"
        >
          ← Back home
        </Link>
      </div>
      <ThemeToggle />
    </header>
  );
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-12">
      <div className="mb-4">
        <h2 className="text-lg font-semibold">{title}</h2>
        {subtitle ? <p className="text-sm text-fg-secondary">{subtitle}</p> : null}
      </div>
      <div className="rounded-md border border-border-default bg-elevated p-5">{children}</div>
    </section>
  );
}

function NeutralSwatches() {
  const steps = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950] as const;
  return (
    <div className="grid grid-cols-11 gap-2">
      {steps.map((s) => (
        <div key={s} className="flex flex-col gap-1">
          <div
            className="h-12 rounded-sm border border-border-default"
            style={{ backgroundColor: `var(--color-neutral-${s})` }}
          />
          <span className="text-xs font-mono text-fg-tertiary">{s}</span>
        </div>
      ))}
    </div>
  );
}

function AccentSwatches() {
  const accents = ["primary", "success", "warning", "danger", "muted"] as const;
  return (
    <div className="grid grid-cols-5 gap-3">
      {accents.map((a) => (
        <div key={a} className="space-y-2">
          <div
            className="h-12 rounded-sm border border-border-default"
            style={{ backgroundColor: `var(--color-accent-${a})` }}
          />
          <div
            className="h-6 rounded-sm border border-border-default"
            style={{ backgroundColor: `var(--color-accent-${a}-weak)` }}
          />
          <span className="text-xs font-mono text-fg-secondary">{a}</span>
        </div>
      ))}
    </div>
  );
}

function TypeRamp() {
  const samples = [
    { token: "text-3xl", cls: "text-3xl font-bold", text: "Workspace name" },
    { token: "text-2xl", cls: "text-2xl font-bold", text: "Page / deliberation title" },
    { token: "text-xl", cls: "text-xl font-semibold", text: "Page subheading" },
    { token: "text-lg", cls: "text-lg font-semibold", text: "Section title / card heading" },
    { token: "text-md", cls: "text-md font-medium", text: "Medium-emphasis label / button text" },
    { token: "text-base", cls: "text-base", text: "Reading content (deliberation prose)" },
    { token: "text-sm", cls: "text-sm", text: "Body, table cells, most UI" },
    { token: "text-xs", cls: "text-xs", text: "Metadata, timestamps, tertiary labels" },
  ];
  return (
    <div className="space-y-3">
      {samples.map((s) => (
        <div key={s.token} className="flex items-baseline gap-4">
          <span className="w-24 shrink-0 font-mono text-xs text-fg-tertiary">{s.token}</span>
          <span className={s.cls}>{s.text}</span>
        </div>
      ))}
      <Separator />
      <div className="flex items-center gap-4">
        <span className="w-24 shrink-0 font-mono text-xs text-fg-tertiary">font-mono</span>
        <span className="font-mono text-sm">@claude-opus#0014 · 14:32:18.421Z</span>
      </div>
      <div className="flex items-center gap-4">
        <span className="w-24 shrink-0 font-mono text-xs text-fg-tertiary">tabular</span>
        <span className="font-mono text-sm">$0.18 / $50.00 · tokens 12,481</span>
      </div>
    </div>
  );
}

function Buttons() {
  return (
    <div className="space-y-4">
      <Row label="variants">
        <Button variant="default">Default</Button>
        <Button variant="primary">Primary</Button>
        <Button variant="outline">Outline</Button>
        <Button variant="ghost">Ghost</Button>
        <Button variant="destructive">Destructive</Button>
      </Row>
      <Row label="sizes">
        <Button size="sm">Small</Button>
        <Button size="md">Medium</Button>
        <Button size="lg">Large</Button>
        <Button size="icon" aria-label="Refresh">
          <RotateCw size={16} strokeWidth={1.5} />
        </Button>
      </Row>
      <Row label="states">
        <Button>Idle</Button>
        <Button disabled>Disabled</Button>
        <Button variant="primary">
          <Play size={14} strokeWidth={1.5} /> With icon
        </Button>
      </Row>
    </div>
  );
}

function Cards() {
  return (
    <div className="grid grid-cols-3 gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Default</CardTitle>
          <CardDescription>1px border, no shadow.</CardDescription>
        </CardHeader>
        <CardContent>
          The workhorse surface. Borders carry the separation; whitespace does the rest.
        </CardContent>
      </Card>
      <Card variant="elevated">
        <CardHeader>
          <CardTitle>Elevated</CardTitle>
          <CardDescription>shadow-sm + 1px border.</CardDescription>
        </CardHeader>
        <CardContent>For things that should feel slightly above the canvas — popovers, focused cards.</CardContent>
      </Card>
      <Card variant="recessed">
        <CardHeader>
          <CardTitle>Recessed</CardTitle>
          <CardDescription>Recessed bg, no border.</CardDescription>
        </CardHeader>
        <CardContent>Sub-panes, sidebars, anywhere the surface should sink rather than rise.</CardContent>
      </Card>
    </div>
  );
}

function Inputs() {
  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="space-y-2">
        <label className="text-xs font-medium uppercase tracking-wider text-fg-tertiary">
          Input
        </label>
        <Input placeholder="Type something…" />
        <Input placeholder="Disabled" disabled />
      </div>
      <div className="space-y-2">
        <label className="text-xs font-medium uppercase tracking-wider text-fg-tertiary">
          Textarea
        </label>
        <Textarea placeholder="Multi-line input…" />
      </div>
    </div>
  );
}

function Badges() {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Badge variant="neutral">Neutral</Badge>
      <Badge variant="primary">Primary</Badge>
      <Badge variant="success">DECIDED</Badge>
      <Badge variant="warning">BLOCKED</Badge>
      <Badge variant="danger">FAILED</Badge>
      <Badge variant="muted">EXPLANATION</Badge>
    </div>
  );
}

function TabsDemo() {
  return (
    <Tabs defaultValue="overview">
      <TabsList>
        <TabsTrigger value="overview">Overview</TabsTrigger>
        <TabsTrigger value="participants">Participants</TabsTrigger>
        <TabsTrigger value="settings">Settings</TabsTrigger>
      </TabsList>
      <TabsContent value="overview">
        <p className="text-sm text-fg-secondary">
          Active tab gets a 2px bottom border in accent-primary. Inactive tabs use 1px in the
          default border color.
        </p>
      </TabsContent>
      <TabsContent value="participants">
        <p className="text-sm text-fg-secondary">Participant list lives here in real flows.</p>
      </TabsContent>
      <TabsContent value="settings">
        <p className="text-sm text-fg-secondary">Settings panels are introduced in Phase 9.</p>
      </TabsContent>
    </Tabs>
  );
}

function Separators() {
  return (
    <div>
      <p className="text-sm">Line above</p>
      <Separator />
      <p className="text-sm">Line below — horizontal separator with my-3.</p>
      <div className="mt-6 flex items-center text-sm">
        <span>Left</span>
        <Separator orientation="vertical" className="h-5" />
        <span>Middle</span>
        <Separator orientation="vertical" className="h-5" />
        <span>Right</span>
      </div>
    </div>
  );
}

function CostChips() {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <CostChip spent={0.18} ceiling={50} />
      <CostChip spent={32.4} ceiling={50} />
      <CostChip spent={43.9} ceiling={50} />
      <CostChip spent={49.5} ceiling={50} />
    </div>
  );
}

function Avatars() {
  const handles = [
    "@claude-opus",
    "@claude-sonnet",
    "@gemini-pro",
    "@gemini-flash",
    "@codex-gpt5",
    "@human-rohan",
    "@explainer",
    "@chatgpt-web",
  ];
  return (
    <div className="space-y-3">
      <Row label="md">
        {handles.map((h) => (
          <HandleAvatar key={h} handle={h} />
        ))}
      </Row>
      <Row label="sizes">
        <HandleAvatar handle="@claude-opus" size="sm" />
        <HandleAvatar handle="@claude-opus" size="md" />
        <HandleAvatar handle="@claude-opus" size="lg" />
      </Row>
    </div>
  );
}

function MoveCards() {
  return (
    <div className="space-y-3">
      <MoveCard
        moveType="PROPOSAL"
        author="@claude-opus"
        timestamp="2026-04-28T14:32:18Z"
        state="complete"
      >
        <p>
          Position: pricing tiers should be free / pro $20 / team $50 with a 14-day pro trial. No
          annual discounts in v1.
        </p>
      </MoveCard>
      <MoveCard
        moveType="CRITIQUE"
        author="@gemini-pro"
        timestamp="2026-04-28T14:34:02Z"
        state="composing"
        targets="PROPOSAL@claude-opus#0014"
      >
        <p>Composing a critique…</p>
      </MoveCard>
      <MoveCard
        moveType="DECISION"
        author="@human-rohan"
        timestamp="2026-04-28T15:01:12Z"
        state="complete"
      >
        <p className="font-medium">
          Pricing tier structure: free / pro $20 / team $50; 14-day pro trial; no annual discounts in v1.
        </p>
      </MoveCard>
      <MoveCard
        moveType="EXPLANATION"
        author="@explainer"
        timestamp="2026-04-28T16:20:00Z"
        state="complete"
        targets="CLARIFY@human-rohan#0014"
      >
        <p>
          <strong>General context:</strong> tiered SaaS pricing typically uses a free tier as a top of
          funnel and price anchors at the upper tiers.
        </p>
      </MoveCard>
      <MoveCard
        moveType="ABSTAIN"
        author="@gemini-flash"
        timestamp="2026-04-28T16:42:00Z"
        state="failed"
      >
        <p>Invocation failed: rate-limit window exhausted.</p>
      </MoveCard>
    </div>
  );
}

function Icons() {
  const groups: { label: string; icons: { Icon: typeof Circle; name: string }[] }[] = [
    {
      label: "Status",
      icons: [
        { Icon: CircleCheck, name: "success" },
        { Icon: CircleAlert, name: "warning" },
        { Icon: CircleX, name: "error" },
        { Icon: Circle, name: "idle" },
        { Icon: CircleDot, name: "active" },
      ],
    },
    {
      label: "Actions",
      icons: [
        { Icon: Play, name: "start" },
        { Icon: Pause, name: "pause" },
        { Icon: RotateCw, name: "refresh" },
        { Icon: Copy, name: "copy" },
        { Icon: Download, name: "export" },
        { Icon: Settings2, name: "settings" },
      ],
    },
    {
      label: "Object types",
      icons: [
        { Icon: MessageSquare, name: "deliberation" },
        { Icon: FileText, name: "artifact" },
        { Icon: Users, name: "participants" },
        { Icon: BookOpen, name: "context" },
        { Icon: KeyRound, name: "permissions" },
        { Icon: Clock, name: "timeline" },
        { Icon: ArrowRight, name: "proceed" },
      ],
    },
  ];
  return (
    <div className="space-y-4">
      {groups.map((g) => (
        <div key={g.label}>
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-fg-tertiary">
            {g.label}
          </p>
          <div className="flex flex-wrap items-center gap-4">
            {g.icons.map(({ Icon, name }) => (
              <div
                key={name}
                className="flex flex-col items-center gap-1 text-fg-secondary"
              >
                <Icon size={20} strokeWidth={1.5} />
                <span className="font-mono text-xs text-fg-tertiary">{name}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function Deferred() {
  const items = [
    { name: "Tooltip", phase: "Phase 7" },
    { name: "Dialog / Sheet", phase: "Phase 7" },
    { name: "Popover / DropdownMenu", phase: "Phase 7" },
    { name: "DeliberationTimeline", phase: "Phase 7" },
    { name: "ManifestProgressBar", phase: "Phase 7" },
    { name: "YourTurnCallout", phase: "Phase 7" },
    { name: "MoveCard (full body rendering)", phase: "Phase 7" },
    { name: "PermissionRequestCard", phase: "Phase 11" },
  ];
  return (
    <ul className="grid grid-cols-2 gap-2 text-sm">
      {items.map((i) => (
        <li
          key={i.name}
          className="flex items-center justify-between rounded-sm border border-border-default bg-recessed px-3 py-2"
        >
          <span>{i.name}</span>
          <Badge variant="neutral">{i.phase}</Badge>
        </li>
      ))}
    </ul>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="w-20 shrink-0 font-mono text-xs uppercase tracking-wider text-fg-tertiary">
        {label}
      </span>
      <div className="flex flex-wrap items-center gap-3">{children}</div>
    </div>
  );
}
