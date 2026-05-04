"use client";

import { detectVendorFromHandle, vendorColor } from "@/lib/vendor";
import type { ComponentPropsWithoutRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const MENTION_RE = /(@[a-zA-Z][\w-]*)/g;
const MENTION_CLASS = "quorum-mention";

/**
 * Remark plugin: walks all text nodes (skipping code/inline-code)
 * and splits `@handle` runs into their own mdast nodes that map to
 * `<span class="quorum-mention" data-handle="@x">`. The `<span>`
 * renderer below picks them up and colours each by vendor.
 */
function remarkMentions() {
  return (tree: Mdast) => walk(tree);

  function walk(node: Mdast): void {
    if (node.type === "code" || node.type === "inlineCode") return;
    const children = (node as { children?: Mdast[] }).children;
    if (!children) return;
    const next: Mdast[] = [];
    for (const child of children) {
      if (child.type === "text" && typeof (child as MdastText).value === "string") {
        const value = (child as MdastText).value;
        const parts = splitText(value);
        if (parts.length > 1) {
          next.push(...parts);
          continue;
        }
      }
      walk(child);
      next.push(child);
    }
    (node as { children?: Mdast[] }).children = next;
  }

  function splitText(value: string): Mdast[] {
    const out: Mdast[] = [];
    let last = 0;
    MENTION_RE.lastIndex = 0;
    let m: RegExpExecArray | null;
    while (true) {
      m = MENTION_RE.exec(value);
      if (m === null) break;
      if (m.index > last) {
        out.push({ type: "text", value: value.slice(last, m.index) } as MdastText);
      }
      const handle = m[0];
      out.push({
        type: "strong",
        data: {
          hName: "span",
          hProperties: { className: MENTION_CLASS, "data-handle": handle },
        },
        children: [{ type: "text", value: handle } as MdastText],
      } as Mdast);
      last = m.index + handle.length;
    }
    if (out.length === 0) return [{ type: "text", value } as MdastText];
    if (last < value.length) {
      out.push({ type: "text", value: value.slice(last) } as MdastText);
    }
    return out;
  }
}

// Minimal mdast shapes — we only touch `text`, generic parents, and
// the synthesized `strong` node we emit. Avoids pulling in @types/mdast
// for a six-line transform.
type MdastText = { type: "text"; value: string };
type Mdast = { type: string; children?: Mdast[]; value?: string; data?: unknown };

type SpanProps = ComponentPropsWithoutRef<"span"> & { node?: unknown };

/**
 * Markdown renderer mapped to design-system tokens.
 *
 * Used in two places: the artifact pane (for AI-maintained docs) and
 * chat message bodies (for AI replies, which are usually markdown-
 * formatted). All callers share the same tag → token mapping so the
 * two surfaces read consistently.
 *
 * GFM (`remark-gfm`) is on by default — agents lean on tables, task
 * lists, strikethrough, and autolinks more often than not.
 */
export function Markdown({
  body,
  colorMentions = false,
}: {
  body: string;
  /**
   * When true, `@handle` tokens are rendered as bold, vendor-coloured
   * pills (Anthropic clay, Google blue, OpenAI teal, accent for
   * humans). Used in chat; off in artifacts so doc bodies don't get
   * unexpected styling.
   */
  colorMentions?: boolean;
}) {
  const plugins = colorMentions ? [remarkGfm, remarkMentions] : [remarkGfm];
  return (
    <div className="prose-quorum">
      <ReactMarkdown
        remarkPlugins={plugins}
        components={{
          h1: ({ node: _node, ...p }) => (
            <h1 className="mb-2 mt-1 text-base font-semibold text-fg-primary first:mt-0" {...p} />
          ),
          h2: ({ node: _node, ...p }) => (
            <h2 className="mb-1.5 mt-3 text-sm font-semibold text-fg-primary first:mt-0" {...p} />
          ),
          h3: ({ node: _node, ...p }) => (
            <h3
              className="mb-1 mt-2.5 text-[13px] font-semibold text-fg-primary first:mt-0"
              {...p}
            />
          ),
          h4: ({ node: _node, ...p }) => (
            <h4 className="mb-1 mt-2 text-xs font-semibold text-fg-primary first:mt-0" {...p} />
          ),
          p: ({ node: _node, ...p }) => (
            <p
              className="my-1.5 text-[13px] leading-relaxed text-fg-primary first:mt-0 last:mb-0"
              {...p}
            />
          ),
          ul: ({ node: _node, ...p }) => (
            <ul
              className="my-1.5 list-disc pl-5 text-[13px] leading-relaxed text-fg-primary first:mt-0 last:mb-0"
              {...p}
            />
          ),
          ol: ({ node: _node, ...p }) => (
            <ol
              className="my-1.5 list-decimal pl-5 text-[13px] leading-relaxed text-fg-primary first:mt-0 last:mb-0"
              {...p}
            />
          ),
          li: ({ node: _node, ...p }) => <li className="my-0.5" {...p} />,
          a: ({ node: _node, ...p }) => (
            <a
              className="text-accent-primary underline-offset-2 hover:underline"
              target="_blank"
              rel="noreferrer"
              {...p}
            />
          ),
          code: ({ node: _node, className, children, ...p }) => {
            const isBlock = (className ?? "").includes("language-");
            if (isBlock) {
              return (
                <code className="font-mono text-[12px] text-fg-primary" {...p}>
                  {children}
                </code>
              );
            }
            return (
              <code
                className="rounded bg-recessed px-1 py-0.5 font-mono text-[11.5px] text-fg-primary"
                {...p}
              >
                {children}
              </code>
            );
          },
          pre: ({ node: _node, ...p }) => (
            <pre
              className="my-2 overflow-x-auto rounded-md border border-border-default bg-recessed p-2 font-mono text-[12px] leading-relaxed text-fg-primary"
              {...p}
            />
          ),
          blockquote: ({ node: _node, ...p }) => (
            <blockquote
              className="my-2 border-l-2 border-border-default pl-3 text-fg-secondary"
              {...p}
            />
          ),
          hr: () => <hr className="my-3 border-border-default" />,
          table: ({ node: _node, ...p }) => (
            <div className="my-2 overflow-x-auto">
              <table className="min-w-full border-collapse text-[12px]" {...p} />
            </div>
          ),
          thead: ({ node: _node, ...p }) => <thead className="bg-recessed" {...p} />,
          th: ({ node: _node, ...p }) => (
            <th
              className="border border-border-default px-2 py-1 text-left font-semibold text-fg-primary"
              {...p}
            />
          ),
          td: ({ node: _node, ...p }) => (
            <td className="border border-border-default px-2 py-1 text-fg-primary" {...p} />
          ),
          span: ({ node: _node, className, children, ...p }: SpanProps) => {
            if (className === MENTION_CLASS) {
              const handle = String((p as { "data-handle"?: string })["data-handle"] ?? "");
              const color = vendorColor(detectVendorFromHandle(handle));
              return (
                <span
                  className="rounded px-1 py-0.5 font-semibold"
                  style={{ color, backgroundColor: `${color}1f` }}
                  {...p}
                >
                  {children}
                </span>
              );
            }
            return (
              <span className={className} {...p}>
                {children}
              </span>
            );
          },
        }}
      >
        {body}
      </ReactMarkdown>
    </div>
  );
}
