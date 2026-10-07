import { describe, expect, it } from "vitest";

import { readNetwork } from "./networks";

describe("readNetwork", () => {
  it("writes an IPv4 network as its network address, and an address as its own network", () => {
    expect(readNetwork("10.1.2.3/16")).toEqual({ network: "10.1.0.0/16" });
    expect(readNetwork(" 192.168.1.7 ")).toEqual({ network: "192.168.1.7/32" });
    expect(readNetwork("203.0.113.0/24")).toEqual({ network: "203.0.113.0/24" });
  });

  it("refuses a network too wide to be one school's", () => {
    expect(readNetwork("0.0.0.0/0")).toEqual({ error: "tooWide" });
    expect(readNetwork("10.0.0.0/4")).toEqual({ error: "tooWide" });
    expect(readNetwork("2001:db8::/16")).toEqual({ error: "tooWide" });
  });

  it("refuses what is not a network", () => {
    for (const text of ["", "colegio", "10.0.0/24", "300.1.1.1", "10.0.0.0/33", "1::2::3", "10.0.0.0/8/8"]) {
      expect(readNetwork(text)).toEqual({ error: "invalid" });
    }
  });

  it("checks an IPv6 network's shape and leaves its spelling to the server", () => {
    expect(readNetwork("2001:DB8:5::/48")).toEqual({ network: "2001:db8:5::/48" });
    expect(readNetwork("2001:db8::1")).toEqual({ network: "2001:db8::1/128" });
  });
});
