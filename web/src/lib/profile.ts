import type { ExemplarsProfile, ItemTypeSpec } from "@/lib/types";
import type { Key } from "@/lib/i18n";

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

export function typeLabel(
  profile: ExemplarsProfile | null,
  key: string | null,
  t: (key: Key) => string,
): string {
  if (!key) return t("profile.noModality");
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

// THE ONE FIELD EVERY MODALITY CARRIES ------------------------------------------------------

/**
 * Mirrors DIFFICULTY_FIELDS in variatio/instance/exemplars_profile.py.
 *
 * Two names because the name is the workspace's PROMPT language's: `prompts/es` writes
 * Spanish field names and `prompts/en` English ones. A screen does not know which language a
 * profile was built in and should not have to look it up, so it asks the modality which of
 * the two it actually declares. Edit the Python first.
 */
export const DIFFICULTY_FIELDS = ["nivel_dificultad", "difficulty_level"] as const;

/** Which key carries this modality's difficulty, or null when it declares none. */
export function difficultyFieldOf(spec: ItemTypeSpec | null | undefined): string | null {
  if (!spec) return null;
  return DIFFICULTY_FIELDS.find((name) => name in spec.fields) ?? null;
}

/** Its rungs, in the order the modality declares them — never a table written here. */
export function difficultyLevelsOf(spec: ItemTypeSpec | null | undefined): string[] {
  const name = difficultyFieldOf(spec);
  const values = name ? spec!.fields[name]?.schema?.enum : undefined;
  return Array.isArray(values) ? values.map(String) : [];
}
