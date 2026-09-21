import type { GraphView } from "@/lib/types";

import {
  computeMapLayout,
  layoutKey,
  seedsFrom,
  type MapLayout,
  type Seeds,
} from "./mapLayout";

/**
 * THE MAP IS COMPUTED ONCE PER STRUCTURE, OFF THE MAIN THREAD, AND KEPT.
 *
 * Three layers, cheapest first. In memory, for the rest of the visit: the card and the expanded
 * view of one screen draw the same map, and so does the generate form's graph. In
 * `localStorage`, for the next visit: a reload, or coming back tomorrow, draws the map at once
 * instead of computing it again. And a worker, for a structure nobody has laid out on this
 * device yet.
 *
 * The key is `layoutKey`, which is the STRUCTURE — units and relations — so the entry survives
 * everything that does not move a concept: a description, a rename in place, a taggability
 * switch. Storage is a convenience and never a requirement: every read and write is guarded,
 * and a browser that refuses storage simply computes again.
 */

const MEMORY_LIMIT = 6;
// A 10 000-concept map is ~110 KB stored; three subjects is what somebody moving between their
// own tends to keep open.
const STORED_LIMIT = 3;
const STORAGE_KEY = "vg.graphMaps";

const memory = new Map<string, MapLayout>();
const pending = new Map<string, Promise<MapLayout>>();

interface Stored {
  key: string;
  width: number;
  height: number;
  regions: MapLayout["regions"];
  lanes: MapLayout["lanes"];
  positions: string;
}

/** The map for this structure if it was already computed, on this visit or a previous one. */
export function cachedLayout(key: string): MapLayout | null {
  const hit = memory.get(key);
  if (hit) return hit;
  const stored = readStored().find((entry) => entry.key === key);
  if (!stored) return null;
  try {
    const layout: MapLayout = {
      key: stored.key,
      width: stored.width,
      height: stored.height,
      regions: stored.regions,
      lanes: stored.lanes,
      positions: decode(stored.positions),
    };
    remember(layout);
    return layout;
  } catch {
    return null;
  }
}

/**
 * The map for `graph`, computed in a worker unless it is already known.
 *
 * `previous` is the map the reader is looking at, when there is one: the new layout starts from
 * where each concept already is, so an edit moves what it touched instead of reshuffling the
 * picture. `fresh` is "Recolocar": it ignores what is known, draws a different map of the same
 * structure, and keeps that one instead.
 */
export function requestLayout(
  graph: GraphView,
  previous?: { graph: GraphView; layout: MapLayout } | null,
  fresh = false,
): Promise<MapLayout> {
  const key = layoutKey(graph);
  if (!fresh) {
    const known = cachedLayout(key);
    if (known) return Promise.resolve(known);
    const running = pending.get(key);
    if (running) return running;
  }
  const seeds = previous && !fresh ? seedsFrom(graph, previous) : null;
  const salt = fresh ? String(Date.now()) : "";
  const job = compute(graph, seeds, salt)
    .then((layout) => {
      remember(layout);
      store(layout);
      return layout;
    })
    .finally(() => {
      if (pending.get(key) === job) pending.delete(key);
    });
  pending.set(key, job);
  return job;
}

let sequence = 0;

function compute(graph: GraphView, seeds: Seeds | null, salt: string): Promise<MapLayout> {
  let worker: Worker;
  try {
    worker = new Worker(new URL("./layout.worker.ts", import.meta.url), { type: "module" });
  } catch {
    // No worker — a test renderer, or a browser that refuses one: the same function, one tick
    // later, so the caller never blocks inside its own render.
    return new Promise((resolve, reject) =>
      setTimeout(() => {
        try {
          resolve(computeMapLayout(graph, seeds, salt));
        } catch (error) {
          reject(error);
        }
      }, 0),
    );
  }
  const id = (sequence += 1);
  return new Promise<MapLayout>((resolve, reject) => {
    worker.onmessage = (event: MessageEvent<{ id: number; layout?: MapLayout; error?: string }>) => {
      if (event.data.id !== id) return;
      worker.terminate();
      if (event.data.layout) resolve(event.data.layout);
      else reject(new Error(event.data.error ?? "layout failed"));
    };
    worker.onerror = (event) => {
      worker.terminate();
      reject(new Error(event.message || "layout worker failed"));
    };
    worker.postMessage({ id, graph, seeds, salt });
  });
}

function remember(layout: MapLayout) {
  memory.delete(layout.key);
  memory.set(layout.key, layout);
  while (memory.size > MEMORY_LIMIT) memory.delete(memory.keys().next().value as string);
}

function readStored(): Stored[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function store(layout: MapLayout) {
  let entry: Stored;
  try {
    entry = {
      key: layout.key,
      width: layout.width,
      height: layout.height,
      regions: layout.regions,
      lanes: layout.lanes,
      positions: encode(layout.positions),
    };
  } catch {
    return;
  }
  const others = readStored().filter((stored) => stored.key !== layout.key);
  // Newest first; when the quota refuses the lot, try the new map alone before giving up.
  for (const entries of [[entry, ...others].slice(0, STORED_LIMIT), [entry]]) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
      return;
    } catch {
      continue;
    }
  }
}

function encode(positions: Float32Array): string {
  const bytes = new Uint8Array(positions.buffer, positions.byteOffset, positions.byteLength);
  let binary = "";
  for (let index = 0; index < bytes.length; index += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
  }
  return btoa(binary);
}

function decode(text: string): Float32Array {
  const binary = atob(text);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return new Float32Array(bytes.buffer);
}
