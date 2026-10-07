/**
 * A school's network as the panel reads it, mirroring `variatio/settings/registry/access.py`.
 *
 * IPv4 is read whole and written as its network address (`10.1.2.3/16` is `10.1.0.0/16`),
 * so the list shows what the server will store. IPv6 is only checked for its shape and its
 * width: the server writes its canonical form, and the list reloads from that.
 */

/** The narrowest mask a school's network may have, per IP version. */
export const MIN_PREFIX = { 4: 8, 6: 32 } as const;

export type NetworkReading = { network: string } | { error: "invalid" | "tooWide" };

/** Read what was typed as a network, or say why it is not one a school could have. */
export function readNetwork(text: string): NetworkReading {
  const value = text.trim();
  const [address, prefix, ...rest] = value.split("/");
  if (!address || rest.length > 0 || (prefix !== undefined && !/^\d{1,3}$/.test(prefix))) {
    return { error: "invalid" };
  }
  return address.includes(":") ? readV6(address, prefix) : readV4(address, prefix);
}

function readV4(address: string, prefixText: string | undefined): NetworkReading {
  const parts = address.split(".");
  if (parts.length !== 4 || parts.some((part) => !/^\d{1,3}$/.test(part) || Number(part) > 255)) {
    return { error: "invalid" };
  }
  const prefix = prefixText === undefined ? 32 : Number(prefixText);
  if (prefix > 32) return { error: "invalid" };
  if (prefix < MIN_PREFIX[4]) return { error: "tooWide" };
  const value = parts.reduce((total, part) => total * 256 + Number(part), 0);
  const mask = (~0 << (32 - prefix)) >>> 0;
  const network = (value & mask) >>> 0;
  const octets = [24, 16, 8, 0].map((shift) => (network >>> shift) & 255);
  return { network: `${octets.join(".")}/${prefix}` };
}

function readV6(address: string, prefixText: string | undefined): NetworkReading {
  const halves = address.split("::");
  const groups = halves.flatMap((half) => (half ? half.split(":") : []));
  const shaped =
    halves.length <= 2 &&
    groups.every((group) => /^[0-9a-f]{1,4}$/i.test(group)) &&
    (halves.length === 2 ? groups.length < 8 : groups.length === 8);
  if (!shaped) return { error: "invalid" };
  const prefix = prefixText === undefined ? 128 : Number(prefixText);
  if (prefix > 128) return { error: "invalid" };
  if (prefix < MIN_PREFIX[6]) return { error: "tooWide" };
  return { network: `${address.toLowerCase()}/${prefix}` };
}
