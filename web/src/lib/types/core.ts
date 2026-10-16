/** What the process answers about itself: the engine's health and the door. */

/**
 * A model resident in the engine RIGHT NOW, as `/api/ps` reports it.
 *
 * The only real measure of what the machine is using: `required` says what the config
 * names, and a named constant is not a loaded model. `expires_at` tells a VRAM eviction
 * from the residency timer running out.
 */
export interface RunningModel {
  model: string;
  size: number | null;
  size_vram: number | null;
  context_length: number | null;
  expires_at: string | null;
}

export interface Health {
  engine: string;
  host: string;
  available: boolean;
  models: {
    required: Record<string, string>;
    /** What a commission may choose between, the default first. */
    offered: string[];
    /** Those of them whose reasoning effort may not be adjusted per commission — measured
     *  to answer the same at every level. Read defensively: an API older than this bundle
     *  sends none, and every model is then adjustable, which is the safe half. */
    fixed_effort?: string[];
    /** With which level each of those is called, declared by the installation. A locked
     *  model absent from the map is called with whatever the engine resolves. */
    fixed_effort_levels?: Record<string, string>;
    installed: string[];
    missing: string[];
    /** Required models a remote provider serves: never on this disk, never "sin instalar". */
    remote: string[];
    running: RunningModel[];
  };
  context_ready: boolean;
  paths: {
    /** The subject's `artifacts/` directory; an API older than 2026-10-08 says `instance`. */
    artifacts?: string;
    raw_exemplars: string;
    raw_corpus: string;
    raw_exemplars_exists: boolean;
    raw_corpus_exists: boolean;
  };
  busy: boolean;
}

/**
 * The installation's door. `since` is an ISO stamp, `by` only ever arrives on the
 * administrator's own reading of it — the public route deliberately omits it.
 */
export type MaintenanceState = {
  active: boolean;
  message: string;
  since: string | null;
  by?: string | null;
};
