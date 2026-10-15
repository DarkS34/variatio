import { useId } from "react";

import { Label, Select } from "@/components/ui/input";
import { Tabs } from "@/components/ui/tabs";
import { useT } from "@/lib/i18n";
import type { ClassGroup } from "@/lib/types";

/** Up to this many groups the scope is a row of tabs; past it, a select. */
const AS_TABS = 3;

/**
 * Who a section of «Clase» acts on: the whole class, or one of its groups (the user's
 * decision, 2026-10-14: with a group a teacher does what they do with the class).
 *
 * A filter over what the section shows, so tabs (DESIGN.md 7.3) while the groups are few, a
 * select once they are many. Nothing is drawn while the class has no group. The screen holds
 * the scope, so moving between sections keeps it.
 */
export function GroupScope({
  groups,
  value,
  onChange,
}: {
  groups: ClassGroup[];
  value: number | null;
  onChange: (group: number | null) => void;
}) {
  const { t } = useT();
  const id = useId();
  if (groups.length === 0) return null;
  if (groups.length <= AS_TABS) {
    return (
      <Tabs
        items={[
          { value: "", label: t("class.scope.class") },
          ...groups.map((group) => ({ value: String(group.id), label: group.name })),
        ]}
        value={value === null ? "" : String(value)}
        onChange={(next) => onChange(next ? Number(next) : null)}
      />
    );
  }
  return (
    <span className="flex items-center gap-2">
      <Label htmlFor={id} className="sr-only">
        {t("class.scope.label")}
      </Label>
      <Select
        id={id}
        value={value === null ? "" : String(value)}
        className="w-full sm:w-56"
        onChange={(event) => onChange(event.target.value ? Number(event.target.value) : null)}
      >
        <option value="">{t("class.scope.class")}</option>
        {groups.map((group) => (
          <option key={group.id} value={group.id}>
            {group.name}
          </option>
        ))}
      </Select>
    </span>
  );
}

/** The name of the group a scope names, for a sentence; null for the class. */
export function scopeName(groups: ClassGroup[], value: number | null): string | null {
  return value === null ? null : (groups.find((group) => group.id === value)?.name ?? null);
}
