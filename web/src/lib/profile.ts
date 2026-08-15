import type { ExemplarsProfile, ItemTypeSpec } from "@/lib/types";

/** Mirrors ExemplarsProfile.type_key_of: with a single modality declared, an item that
 *  never named one still belongs to it — there was nothing to choose. */
export function typeKeys(profile: ExemplarsProfile | null): string[] {
  return profile ? Object.keys(profile.item_types) : [];
}

export function defaultTypeKey(profile: ExemplarsProfile | null): string | null {
  return typeKeys(profile)[0] ?? null;
}

export function typeKeyOf(
  profile: ExemplarsProfile | null,
  item: { item_type?: string } | null | undefined,
): string | null {
  const keys = typeKeys(profile);
  const declared = item?.item_type;
  if (declared && keys.includes(declared)) return declared;
  if (!declared && keys.length === 1) return keys[0];
  return null;
}

export function itemTypeOf(
  profile: ExemplarsProfile | null,
  item: { item_type?: string } | null | undefined,
): ItemTypeSpec | null {
  const key = typeKeyOf(profile, item);
  return key && profile ? profile.item_types[key] : null;
}

export function typeLabel(profile: ExemplarsProfile | null, key: string | null): string {
  if (!key) return "sin modalidad";
  return profile?.item_types[key]?.label || key;
}

/** Mirrors ItemType.embed_fields: absent means the primary field alone. */
export function embedFields(spec: ItemTypeSpec | null | undefined): string[] {
  if (!spec) return [];
  const declared = spec.embed_fields?.filter((name) => name in spec.fields) ?? [];
  return declared.length ? declared : [spec.primary_field];
}

export function userDecidedFields(spec: ItemTypeSpec | null | undefined): string[] {
  if (!spec) return [];
  return Object.entries(spec.fields)
    .filter(([, field]) => field.decided_by === "user")
    .map(([name]) => name);
}
