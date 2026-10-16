import { useMutation } from "@tanstack/react-query";
import { Eye } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChoicePill } from "@/components/ui/choice";
import { Dialog } from "@/components/ui/dialog";
import { Label } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Spinner } from "@/components/ui/spinner";
import { useRadioGroup } from "@/components/ui/radio";
import { api } from "@/lib/api";
import { useT, type Key } from "@/lib/i18n";
import { fieldLabel } from "@/lib/profile";
import type { BankItem, BankItemType, BankVisibility, ClassGroup, ExemplarsProfile } from "@/lib/types";
import { useClassGroups } from "@/state/queries";

/** What the class sees of an exercise, as a teacher chooses it, and which part of the class. */
export interface VisibilityChoice {
  level: "hidden" | "full" | "fields";
  fields: string[];
  /** The groups that see it; null is the whole class. */
  groups: number[] | null;
}

export const HIDDEN: VisibilityChoice = { level: "hidden", fields: [], groups: null };

/** Whether a choice can be saved: a choice of groups must name one at least. */
export function choiceComplete(value: VisibilityChoice): boolean {
  return value.level === "hidden" || value.groups === null || value.groups.length > 0;
}

/** The body a route takes for a choice: the groups only where something is shown. */
export function choiceBody(value: VisibilityChoice) {
  return {
    level: value.level,
    fields: value.level === "fields" ? value.fields : [],
    groups: value.level === "hidden" ? null : value.groups,
  };
}

const LEVELS: { value: VisibilityChoice["level"]; key: Key }[] = [
  { value: "hidden", key: "bank.visibility.level.hidden" },
  { value: "full", key: "bank.visibility.level.full" },
  { value: "fields", key: "bank.visibility.level.fields" },
];

/**
 * The fields a teacher may show of a type: every field but the difficulty, which is always
 * seen as the level, the statement first. Mirrors `server/bank/marks.showable_fields`.
 */
export function showableFields(type: BankItemType): string[] {
  const fields = type.fields.filter((name) => name !== type.difficulty_field);
  return [type.primary_field, ...fields.filter((name) => name !== type.primary_field)];
}

/**
 * «Visible» or «Visible: N campos» beside an exercise the class sees, and the groups when it
 * is only theirs; nothing when hidden.
 */
export function VisibilityBadge({
  visibility,
  groups = [],
}: {
  visibility: BankVisibility | null | undefined;
  /** The class's groups, to name the ones an exercise is shown to. */
  groups?: ClassGroup[];
}) {
  const { t, plural } = useT();
  if (!visibility) return null;
  const names = (visibility.groups ?? [])
    .map((id) => groups.find((group) => group.id === id)?.name)
    .filter((name): name is string => Boolean(name));
  const level =
    visibility.level === "full"
      ? t("bank.visibility.visible")
      : plural("bank.visibility.someFields", visibility.fields.length);
  return (
    <Badge variant="default" className="max-w-full py-0" title={names.length > 0 ? names.join(", ") : undefined}>
      <Eye />
      <span className="truncate">
        {visibility.groups ? `${level} · ${names.length > 0 ? names.join(", ") : plural("bank.visibility.groupCount", visibility.groups.length)}` : level}
      </span>
    </Badge>
  );
}

/**
 * The three answers to «¿Qué ve la clase?», and the fields when it is some of them.
 *
 * The fields are those of every type concerned, each type under its own caption when there
 * are several; the statement is ticked and cannot be unticked, since it is what the exercise
 * is. A field ticked is shown by every exercise whose type has it.
 */
export function VisibilityPicker({
  value,
  onChange,
  types,
  profile,
}: {
  value: VisibilityChoice;
  onChange: (next: VisibilityChoice) => void;
  types: BankItemType[];
  profile: ExemplarsProfile | null;
}) {
  const { t } = useT();
  const radios = useRadioGroup(
    LEVELS.map((level) => level.value),
    value.level,
    (level) => onChange({ ...value, level }),
  );
  // Who sees it, where the class has groups: the whole class, or the groups ticked.
  const groups = useClassGroups().data ?? [];
  const scope = value.groups === null ? "class" : "groups";
  const scopes = useRadioGroup(["class", "groups"] as const, scope, (next) =>
    onChange({ ...value, groups: next === "class" ? null : (value.groups ?? []) }),
  );
  const toggleGroup = (id: number) => {
    const chosen = value.groups ?? [];
    onChange({
      ...value,
      groups: chosen.includes(id) ? chosen.filter((group) => group !== id) : [...chosen, id],
    });
  };
  const toggle = (field: string) =>
    onChange({
      ...value,
      fields: value.fields.includes(field)
        ? value.fields.filter((name) => name !== field)
        : [...value.fields, field],
    });

  return (
    <div className="space-y-3">
      <div role="radiogroup" aria-label={t("bank.visibility.question")} className="flex flex-wrap gap-2" {...radios.group}>
        {LEVELS.map((level) => (
          <ChoicePill
            key={level.value}
            {...radios.radio(level.value)}
            chosen={value.level === level.value}
            onClick={() => onChange({ ...value, level: level.value })}
          >
            {t(level.key)}
          </ChoicePill>
        ))}
      </div>
      {value.level === "fields" ? (
        <div className="space-y-3">
          {types.map((type) => {
            const spec = profile?.item_types?.[type.key] ?? null;
            return (
              <div key={type.key} className="space-y-2">
                {types.length > 1 ? (
                  <Label>{t("bank.visibility.typeFields", { type: type.label || type.key })}</Label>
                ) : null}
                <div className="flex flex-wrap gap-x-5 gap-y-2">
                  {showableFields(type).map((field) => {
                    const statement = field === type.primary_field;
                    return (
                      <span key={field} className="flex items-center gap-2 text-body">
                        <Checkbox
                          checked={statement || value.fields.includes(field)}
                          disabled={statement}
                          onCheckedChange={() => toggle(field)}
                          label={fieldLabel(field, spec)}
                        />
                        {fieldLabel(field, spec)}
                        {statement ? (
                          <span className="text-small text-muted-foreground">
                            · {t("bank.visibility.always")}
                          </span>
                        ) : null}
                      </span>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
      {value.level !== "hidden" && groups.length > 0 ? (
        <div className="space-y-2">
          <Label>{t("bank.visibility.who")}</Label>
          <div role="radiogroup" aria-label={t("bank.visibility.who")} className="flex flex-wrap gap-2" {...scopes.group}>
            <ChoicePill {...scopes.radio("class")} chosen={scope === "class"} onClick={() => onChange({ ...value, groups: null })}>
              {t("bank.visibility.wholeClass")}
            </ChoicePill>
            <ChoicePill
              {...scopes.radio("groups")}
              chosen={scope === "groups"}
              onClick={() => onChange({ ...value, groups: value.groups ?? [] })}
            >
              {t("bank.visibility.someGroups")}
            </ChoicePill>
          </div>
          {scope === "groups" ? (
            <div className="flex flex-wrap gap-x-5 gap-y-2">
              {groups.map((group) => (
                <span key={group.id} className="flex items-center gap-2 text-body">
                  <Checkbox
                    checked={(value.groups ?? []).includes(group.id)}
                    onCheckedChange={() => toggleGroup(group.id)}
                    label={group.name}
                  />
                  {group.name}
                </span>
              ))}
            </div>
          ) : null}
          {!choiceComplete(value) ? (
            <p className="text-small text-muted-foreground">{t("bank.visibility.pickGroup")}</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/** What a set of exercises shows, as the picker opens on it: theirs if they agree, else none. */
function choiceOf(items: BankItem[]): VisibilityChoice {
  const levels = new Set(items.map((item) => item.visibility?.level ?? "hidden"));
  if (levels.size !== 1) return HIDDEN;
  const [level] = [...levels] as VisibilityChoice["level"][];
  const fields = [...new Set(items.flatMap((item) => item.visibility?.fields ?? []))];
  // The groups too, when every one names the same; else the whole class.
  const scopes = new Set(items.map((item) => JSON.stringify([...(item.visibility?.groups ?? [])].sort())));
  const named = items[0]?.visibility?.groups ?? null;
  const groups = scopes.size === 1 && named ? [...named] : null;
  return { level, fields: level === "fields" ? fields : [], groups };
}

/** «Lo que ve la clase» of one exercise or of the ones ticked, saved in one press. */
export function VisibilityDialog({
  items,
  itemTypes,
  profile,
  onClose,
}: {
  items: BankItem[];
  itemTypes: BankItemType[];
  profile: ExemplarsProfile | null;
  /** Called with whether anything was saved. */
  onClose: (saved: boolean) => void;
}) {
  const { t, plural } = useT();
  const [value, setValue] = useState<VisibilityChoice>(() => choiceOf(items));
  const keys = new Set(items.map((item) => item.item_type ?? itemTypes[0]?.key));
  const types = itemTypes.filter((type) => keys.has(type.key));
  const save = useMutation({
    mutationFn: () => {
      const body = choiceBody(value);
      return api.setVisibility(
        items.map((item) => item.id),
        body.level,
        body.fields,
        body.groups,
      );
    },
    onSuccess: () => onClose(true),
  });

  return (
    <Dialog
      open
      onClose={() => onClose(false)}
      title={plural("bank.visibility.title", items.length, { id: items[0]?.id ?? "" })}
      description={t("bank.visibility.description")}
      footer={
        <>
          <Button variant="ghost" onClick={() => onClose(false)}>
            {t("common.cancel")}
          </Button>
          <Button onClick={() => save.mutate()} disabled={save.isPending || !choiceComplete(value)}>
            {save.isPending ? <Spinner /> : null}
            {t("common.save")}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <VisibilityPicker value={value} onChange={setValue} types={types} profile={profile} />
        {save.isError ? (
          <p role="alert" className="text-small text-destructive">
            {(save.error as Error).message}
          </p>
        ) : null}
      </div>
    </Dialog>
  );
}
