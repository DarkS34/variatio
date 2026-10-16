/**
 * What the API answers and takes, one module per area of the server that sends it.
 *
 * `@/lib/types` resolves here, so an importer names no area; a type lives beside the route that
 * answers it (`server/<area>/`).
 */

export * from "./core";
export * from "./auth";
export * from "./workspaces";
export * from "./jobs";
export * from "./pipeline";
export * from "./raw";
export * from "./kg";
export * from "./bank";
export * from "./classroom";
export * from "./generations";
export * from "./admin";
