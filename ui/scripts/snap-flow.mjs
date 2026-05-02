#!/usr/bin/env node
import { mkdir } from "node:fs/promises";
import { dirname } from "node:path";
/**
 * Self-verification: snapshot the live system-flow diagram so I can
 * read it back and confirm the layout matches expectations without
 * pestering the user. Optionally click a stage badge first to
 * exercise the toggle.
 *
 * Usage:
 *   node scripts/snap-flow.mjs                # default snapshot
 *   node scripts/snap-flow.mjs --click=S2     # toggle a past-stage sub-flow then snapshot
 *
 * Outputs PNG to /tmp/flow-snapshot.png so the parent agent can Read it.
 */
import { chromium } from "@playwright/test";

const args = Object.fromEntries(
  process.argv.slice(2).map((a) => {
    const [k, v] = a.replace(/^--/, "").split("=");
    return [k, v ?? true];
  }),
);

const URL = args.url || "http://localhost:3000/workspace";
const OUT = args.out || "/tmp/flow-snapshot.png";
const CLICK = args.click || null; // e.g. "S2", "S5"
// When set, intercept /api/deliberations and force one artifact-deliberation
// (id != "0001") into OPEN status so we can verify the anchored S4 layout.
// Example: --mock-active=0004
const MOCK_ACTIVE = args["mock-active"] || null;

await mkdir(dirname(OUT), { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();

if (MOCK_ACTIVE) {
  // Intercept /api/deliberations and rewrite the response so the named
  // artifact deliberation appears OPEN (active). Also flip the manifest
  // to LOCKED so the stage resolver lands on S4 (working artifacts).
  await page.route(/\/api\/deliberations(\?|$)/, async (route) => {
    const res = await route.fetch();
    const body = await res.json();
    body.deliberations = (body.deliberations || []).map((d) =>
      d.id === MOCK_ACTIVE ? { ...d, status: "OPEN" } : d,
    );
    await route.fulfill({ response: res, json: body });
  });
  await page.route(/\/api\/manifest(\?|$)/, async (route) => {
    const res = await route.fetch();
    const body = await res.json();
    if (body?.progress) body.progress.status = "LOCKED";
    await route.fulfill({ response: res, json: body });
  });
}

page.on("pageerror", (e) => console.error("[pageerror]", e.message));
page.on("console", (msg) => {
  if (msg.type() === "error") console.error("[console.error]", msg.text());
});

await page.goto(URL, { waitUntil: "domcontentloaded" });
// Diagram lives in the React Flow viewport.
await page.waitForSelector(".react-flow__viewport", { timeout: 10000 });
// Give layout/fitView a beat to settle.
await page.waitForTimeout(800);

if (CLICK) {
  // The stage badges have text "Set up", "Draft the plan", "Work the artifacts", "Wrap up", "Archived".
  const labels = {
    S2: "Set up",
    S3: "Draft the plan",
    S4: "Work the artifacts",
    S5: "Wrap up",
    S6: "Archived",
  };
  const label = labels[CLICK];
  if (!label) throw new Error(`Unknown stage: ${CLICK}`);
  const badge = page.locator(`.react-flow__node-stageBadge:has-text("${label}")`);
  await badge.click();
  await page.waitForTimeout(600); // animation + fitView
}

const target = page.locator(".react-flow").first();
await target.screenshot({ path: OUT });

// Also dump node positions so I can read layout numerically.
const nodes = await page.evaluate(() => {
  return Array.from(document.querySelectorAll(".react-flow__node")).map((el) => {
    const r = el.getBoundingClientRect();
    const id = el.getAttribute("data-id");
    const type = el.className.match(/react-flow__node-(\w+)/)?.[1] ?? "?";
    return {
      id,
      type,
      x: Math.round(r.x),
      y: Math.round(r.y),
      w: Math.round(r.width),
      h: Math.round(r.height),
      cx: Math.round(r.x + r.width / 2),
      cy: Math.round(r.y + r.height / 2),
    };
  });
});

console.log(JSON.stringify({ url: URL, out: OUT, click: CLICK, nodes }, null, 2));

await browser.close();
