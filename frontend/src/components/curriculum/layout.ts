/**
 * Positions the course graph with ELK's layered algorithm: prerequisites flow
 * left to right, catalog order is kept inside each layer. Loaded only with the
 * roadmap chunk (elkjs is large).
 */
import ELK from "elkjs/lib/elk.bundled.js";
import type { CurriculumGraph } from "./graph";

export const NODE_WIDTH = 228;
export const NODE_HEIGHT = 76;

export type Positions = Map<string, { x: number; y: number }>;

let elk: InstanceType<typeof ELK> | undefined;

export async function layoutRoadmap(graph: CurriculumGraph): Promise<Positions> {
  elk ??= new ELK();
  const result = await elk.layout({
    id: "curriculum",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "RIGHT",
      "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
      "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
      "elk.layered.spacing.nodeNodeBetweenLayers": "72",
      "elk.spacing.nodeNode": "22",
      "elk.padding": "[top=16,left=16,bottom=16,right=16]",
    },
    children: [...graph.nodes]
      .sort((a, b) => a.number - b.number)
      .map((node) => ({ id: node.id, width: NODE_WIDTH, height: NODE_HEIGHT })),
    edges: graph.edges.map((edge) => ({
      id: edge.id,
      sources: [edge.source],
      targets: [edge.target],
    })),
  });
  const positions: Positions = new Map();
  for (const child of result.children ?? [])
    positions.set(child.id, { x: child.x ?? 0, y: child.y ?? 0 });
  return positions;
}
