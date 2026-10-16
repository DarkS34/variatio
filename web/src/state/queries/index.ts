/**
 * The data hooks, one module per area of the server they read, and the query keys they share.
 *
 * `@/state/queries` resolves here; `scoped`, which names one instance in a key, stays the
 * modules' own.
 */

export { keys, stageReviewKeys } from "./keys";
export * from "./core";
export * from "./workspaces";
export * from "./jobs";
export * from "./pipeline";
export * from "./raw";
export * from "./kg";
export * from "./bank";
export * from "./classroom";
export * from "./generations";
export * from "./admin";
