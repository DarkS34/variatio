import { describe, expect, it, vi } from "vitest";

// `api.ts` asks the tab for its workspace on every request, and that store reads
// `sessionStorage` on import, which node does not have. Nothing here sends a request.
vi.mock("@/state/workspace", () => ({ workspaceHeader: () => ({}) }));

import { retryAfterSeconds } from "./api";

const NOW = Date.parse("Sun, 04 Oct 2026 10:00:00 GMT");

describe("retryAfterSeconds", () => {
  it("reads the seconds the server sends", () => {
    expect(retryAfterSeconds("3600", NOW)).toBe(3600);
    expect(retryAfterSeconds(" 0 ", NOW)).toBe(0);
  });

  it("reads an HTTP date as the seconds left until it", () => {
    expect(retryAfterSeconds("Sun, 04 Oct 2026 11:30:00 GMT", NOW)).toBe(5400);
  });

  it("reads a date already past as no wait at all", () => {
    expect(retryAfterSeconds("Sun, 04 Oct 2026 09:00:00 GMT", NOW)).toBe(0);
  });

  it("is null for a header that is absent, blank or unreadable", () => {
    expect(retryAfterSeconds(null, NOW)).toBeNull();
    expect(retryAfterSeconds("", NOW)).toBeNull();
    expect(retryAfterSeconds("   ", NOW)).toBeNull();
    expect(retryAfterSeconds("mañana", NOW)).toBeNull();
  });

  // `Date.parse` takes both for dates long past, which read as a wait of zero: the
  // sentence would then promise the limit reopens now.
  it("does not take a fraction or a negative number for a date", () => {
    expect(retryAfterSeconds("1.5", NOW)).toBeNull();
    expect(retryAfterSeconds("-5", NOW)).toBeNull();
  });
});
