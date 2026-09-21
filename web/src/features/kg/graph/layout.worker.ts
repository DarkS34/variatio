import type { GraphView } from "@/lib/types";

import { computeMapLayout, type Seeds } from "./mapLayout";

/**
 * The map's layout, off the main thread.
 *
 * Laying out a 10 000-concept subject takes over a second even at O(n log n), and on the main
 * thread that second is a page that does not scroll, type or answer a click. Here it costs
 * nothing the reader can feel: the canvas draws the units at once and the concepts land when
 * this answers. The positions travel back TRANSFERRED, not copied.
 */

export interface LayoutRequest {
  id: number;
  graph: GraphView;
  seeds: Seeds | null;
  salt: string;
}

const scope = self as unknown as {
  onmessage: ((event: MessageEvent<LayoutRequest>) => void) | null;
  postMessage(message: unknown, transfer?: Transferable[]): void;
};

scope.onmessage = (event) => {
  const { id, graph, seeds, salt } = event.data;
  try {
    const layout = computeMapLayout(graph, seeds, salt);
    scope.postMessage({ id, layout }, [layout.positions.buffer]);
  } catch (error) {
    scope.postMessage({ id, error: error instanceof Error ? error.message : String(error) });
  }
};
