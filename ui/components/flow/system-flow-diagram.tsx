"use client";

import type { StageDetail, StageId, SystemFlowState } from "@/lib/flow/types";
import { useSystemFlowState } from "@/lib/flow/use-system-flow-state";
import { type Edge, type Node, ReactFlow, ReactFlowProvider, useReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ARTIFACT_WIDTH, ArtifactCardNode } from "./artifact-card-node";
import { MoveSequenceNode } from "./move-sequence-node";
import { COLUMN_WIDTH } from "./node-frame";
import { SetupChecklistNode } from "./setup-checklist-node";
import { StageBadgeNode } from "./stage-badge-node";

/**
 * Live system-flow diagram for the Simple-mode right-half slot.
 *
 * Renders the master flow as a vertical spine of stage badges. The
 * active stage's sub-flow expands inline; finished stages collapse to
 * a "done" pill but stay clickable to re-expand. S4 specifically
 * renders artifact cards as a horizontal row anchored on the active
 * artifact (or centred when none is active).
 *
 * Drift contract: this component reads `SystemFlowState` derived in
 * `lib/flow/derive.ts`. The derivation logic mirrors
 * `system-flow-stages.md` and is the single point of update when the
 * master flow changes (per `.claude/rules/visual-flow.md`).
 */
const STAGE_ORDER: StageId[] = ["S2", "S3", "S4", "S5", "S6"];

const NODE_TYPES = {
  stageBadge: StageBadgeNode,
  setupChecklist: SetupChecklistNode,
  moveSequence: MoveSequenceNode,
  artifactCard: ArtifactCardNode,
};

export function SystemFlowDiagram({ reloadKey = 0 }: { reloadKey?: number }) {
  const flow = useSystemFlowState(reloadKey);
  if (!flow) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-fg-tertiary">Loading flow…</p>
      </div>
    );
  }
  return (
    <ReactFlowProvider>
      <DiagramInner flow={flow} />
    </ReactFlowProvider>
  );
}

function DiagramInner({ flow }: { flow: SystemFlowState }) {
  const [expandedExtras, setExpandedExtras] = useState<Set<StageId>>(new Set());
  const onToggle = useCallback((stage: StageId) => {
    setExpandedExtras((prev) => {
      const next = new Set(prev);
      if (next.has(stage)) next.delete(stage);
      else next.add(stage);
      return next;
    });
  }, []);

  // React Flow's `onNodeClick` fires reliably regardless of pan/drag.
  // We use it instead of fighting the `nopan` class dance on a custom
  // button inside the node.
  const onNodeClick = useCallback(
    (_e: unknown, node: Node) => {
      if (node.type !== "stageBadge") return;
      const stage = (node.data as { stage?: StageId }).stage;
      if (stage) onToggle(stage);
    },
    [onToggle],
  );

  const built = useMemo(
    () => buildGraph(flow, expandedExtras, onToggle),
    [flow, expandedExtras, onToggle],
  );
  const laidOut = useMemo(() => layoutGraph(built), [built]);

  // Re-fit the viewport whenever the graph shape changes (stages
  // expand/collapse). The diagram is data-driven; we don't keep any
  // local node-position state because users can't drag.
  const shapeKey = useMemo(() => laidOut.nodes.map((n) => n.id).join("|"), [laidOut.nodes]);
  const { fitView } = useReactFlow();
  useEffect(() => {
    void shapeKey;
    requestAnimationFrame(() => fitView({ padding: 0.2, duration: 200 }));
  }, [shapeKey, fitView]);

  return (
    <div className="h-full w-full">
      <ReactFlow
        nodes={laidOut.nodes}
        edges={laidOut.edges}
        nodeTypes={NODE_TYPES}
        defaultEdgeOptions={{ type: "straight" }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        onNodeClick={onNodeClick}
        panOnDrag
        zoomOnScroll
        fitView
        proOptions={{ hideAttribution: true }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------- //
// Graph construction
// ---------------------------------------------------------------------- //

type BuiltGraph = {
  nodes: Node[];
  /** Ordered list of node IDs forming the vertical spine. */
  spineOrder: string[];
  /**
   * S4 artifact row.
   * - `anchorId` set: that artifact sits on the spine.
   * - `anchorId` null: row is off-spine, centred at x=0.
   */
  artifactRow?: {
    anchorId: string | null;
    orderedIds: string[];
    activeIndex: number;
  };
};

function buildGraph(
  flow: SystemFlowState,
  expandedExtras: Set<StageId>,
  onToggle: (stage: StageId) => void,
): BuiltGraph & { edges: Edge[] } {
  const nodes: Node[] = [];
  const spineOrder: string[] = [];
  let artifactRow: BuiltGraph["artifactRow"];

  for (const stage of STAGE_ORDER) {
    const isCurrent = stage === flow.currentStage;
    const isPastDone = flow.stageStates[stage] === "done";
    const isExpanded = isCurrent || expandedExtras.has(stage);
    const badgeId = `stage:${stage}`;
    nodes.push({
      id: badgeId,
      type: "stageBadge",
      position: { x: 0, y: 0 },
      data: {
        stage,
        state: flow.stageStates[stage],
        expanded: isExpanded,
        onToggle,
      },
    });
    spineOrder.push(badgeId);

    if (!isExpanded) continue;

    const tone: "live" | "done" = isCurrent ? "live" : isPastDone ? "done" : "live";
    const detail: StageDetail = flow.details[stage];

    if (detail.kind === "S2") {
      const id = `${stage}:setup`;
      nodes.push({
        id,
        type: "setupChecklist",
        position: { x: 0, y: 0 },
        data: { checks: detail.checks, startReady: detail.startReady, tone },
      });
      spineOrder.push(id);
    } else if (detail.kind === "S3") {
      const id = `${stage}:sequence`;
      nodes.push({
        id,
        type: "moveSequence",
        position: { x: 0, y: 0 },
        data: { sequence: detail.sequence, title: "Drafting the plan", tone },
      });
      spineOrder.push(id);
    } else if (detail.kind === "S4") {
      const sequence = detail.activeSequences[0]?.sequence ?? {
        steps: {
          propose: "pending" as const,
          critique: "pending" as const,
          synthesise: "pending" as const,
          decide: "pending" as const,
        },
        activeHandle: null,
        substituted: false,
        statusNote: detail.wrapUpReady ? "All artifacts complete." : "No artifact in progress.",
      };
      const seqId = `${stage}:sequence`;
      nodes.push({
        id: seqId,
        type: "moveSequence",
        position: { x: 0, y: 0 },
        data: {
          sequence,
          title: detail.activeSequences[0]?.artifact.title ?? "Working the artifacts",
          tone,
        },
      });
      spineOrder.push(seqId);

      const activeFilename = detail.activeSequences[0]?.artifact.filename ?? null;
      const orderedIds: string[] = [];
      let activeIndex = -1;
      detail.artifacts.forEach((a, i) => {
        const id = `${stage}:artifact:${a.filename}`;
        const isActive = a.filename === activeFilename;
        if (isActive) activeIndex = i;
        nodes.push({
          id,
          type: "artifactCard",
          position: { x: 0, y: 0 },
          data: { artifact: a, active: isActive, tone },
        });
        orderedIds.push(id);
      });
      if (detail.artifacts.length > 0) {
        if (activeIndex >= 0) {
          const anchorId = orderedIds[activeIndex];
          spineOrder.push(anchorId);
          artifactRow = { anchorId, orderedIds, activeIndex };
        } else {
          artifactRow = { anchorId: null, orderedIds, activeIndex: -1 };
        }
      }
    } else if (detail.kind === "S5") {
      const id = `${stage}:sequence`;
      nodes.push({
        id,
        type: "moveSequence",
        position: { x: 0, y: 0 },
        data: { sequence: detail.sequence, title: "Wrapping up", tone },
      });
      spineOrder.push(id);
    }
    // S1, S6: no sub-flow nodes.
  }

  // Edges: connect consecutive spine nodes vertically. Off-spine
  // artifact siblings are unconnected — the active one already sits
  // on the spine and carries the sub-flow → S5 chain through itself.
  const edges: Edge[] = [];
  for (let i = 0; i < spineOrder.length - 1; i++) {
    const srcId = spineOrder[i];
    const dstId = spineOrder[i + 1];
    const onCurrentStage = srcId === `stage:${flow.currentStage}`;
    edges.push({
      id: `edge:${srcId}->${dstId}`,
      source: srcId,
      target: dstId,
      type: "straight",
      animated: onCurrentStage,
      style: { stroke: "var(--color-border-default)" },
    });
  }

  return { nodes, edges, spineOrder, artifactRow };
}

// ---------------------------------------------------------------------- //
// Layout (single-column, hand-rolled)
// ---------------------------------------------------------------------- //

const NODE_HEIGHTS: Record<string, number> = {
  stageBadge: 36,
  setupChecklist: 180,
  moveSequence: 96,
  artifactCard: 96,
};

const VERTICAL_GAP = 36;
const ARTIFACT_GAP = 16;

function layoutGraph(built: BuiltGraph & { edges: Edge[] }): { nodes: Node[]; edges: Edge[] } {
  const { nodes, edges, artifactRow } = built;
  const byId = new Map(nodes.map((n) => [n.id, n]));

  const offSpine = new Set<string>();
  if (artifactRow) {
    for (const id of artifactRow.orderedIds) {
      if (id !== artifactRow.anchorId) offSpine.add(id);
    }
  }

  const spineYs = new Map<string, number>();
  let y = 0;
  const positioned: Node[] = [];
  const orderIndex = new Map(built.spineOrder.map((id, i) => [id, i] as const));
  const spineNodes = [...nodes]
    .filter((n) => !offSpine.has(n.id))
    .sort((a, b) => (orderIndex.get(a.id) ?? 0) - (orderIndex.get(b.id) ?? 0));

  let centeredRowY: number | null = null;
  for (const n of spineNodes) {
    const t = n.type ?? "stageBadge";
    const h = NODE_HEIGHTS[t] ?? 60;
    const w = t === "artifactCard" ? ARTIFACT_WIDTH : COLUMN_WIDTH;
    spineYs.set(n.id, y);
    positioned.push({ ...n, position: { x: -w / 2, y } });
    y += h + VERTICAL_GAP;
    if (n.id === "S4:sequence" && artifactRow && !artifactRow.anchorId) {
      centeredRowY = y;
      y += NODE_HEIGHTS.artifactCard + VERTICAL_GAP;
    }
  }

  if (artifactRow) {
    if (artifactRow.anchorId) {
      const anchorY = spineYs.get(artifactRow.anchorId) ?? 0;
      artifactRow.orderedIds.forEach((id, i) => {
        if (id === artifactRow.anchorId) return;
        const node = byId.get(id);
        if (!node) return;
        const offset = i - artifactRow.activeIndex;
        const x = offset * (ARTIFACT_WIDTH + ARTIFACT_GAP) - ARTIFACT_WIDTH / 2;
        positioned.push({ ...node, position: { x, y: anchorY } });
      });
    } else if (centeredRowY !== null) {
      const N = artifactRow.orderedIds.length;
      const stepX = ARTIFACT_WIDTH + ARTIFACT_GAP;
      artifactRow.orderedIds.forEach((id, i) => {
        const node = byId.get(id);
        if (!node) return;
        const x = (i - (N - 1) / 2) * stepX - ARTIFACT_WIDTH / 2;
        positioned.push({ ...node, position: { x, y: centeredRowY } });
      });
    }
  }

  return { nodes: positioned, edges };
}
