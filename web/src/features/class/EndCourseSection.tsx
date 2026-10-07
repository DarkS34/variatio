import { UserMinus, UserX } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import { useRadioGroup } from "@/components/ui/radio";
import { useToast } from "@/components/ui/toast";
import { SectionHeader } from "@/features/admin/Sections";
import { useT, type Key } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { useEndCourse } from "@/state/queries";

type Ending = "disable" | "remove";

const ENDINGS: Ending[] = ["disable", "remove"];

const ENDING_KEYS: Record<Ending, { title: Key; body: Key }> = {
  disable: { title: "class.end.disable", body: "class.end.disable.body" },
  remove: { title: "class.end.remove", body: "class.end.remove.body" },
};

/**
 * «Fin de curso»: every student of the subject out at once, paused by default or removed,
 * and the class link paused. The owner's alone (`MANAGE` on the route, and the screen draws
 * the section for an owner only).
 *
 * Destructive, so it asks for the subject's name typed and spends no `--attention`: the coral
 * is for the thing to do next, and ending a course is never that by default.
 */
export function EndCourseSection({ subject }: { subject: string }) {
  const { t, plural } = useT();
  const toast = useToast();
  const end = useEndCourse();
  const [ending, setEnding] = useState<Ending>("disable");
  const [typed, setTyped] = useState("");
  const radios = useRadioGroup(ENDINGS, ending, setEnding);
  const confirmed = typed.trim() === subject.trim() && subject.trim() !== "";

  const run = () =>
    end.mutate(ending, {
      onSuccess: ({ students }) => {
        setTyped("");
        toast({
          title: plural(ending === "disable" ? "class.end.paused" : "class.end.removed", students),
          tone: "attention",
        });
      },
      onError: (error: Error) =>
        toast({ title: t("class.failed"), description: error.message, tone: "danger" }),
    });

  return (
    <>
      <SectionHeader title={t("class.end")} description={t("class.end.lead")} />

      <section className="surface space-y-4 p-5" aria-labelledby="class-end-choice">
        <h3 id="class-end-choice" className="text-heading">
          {t("class.end.what")}
        </h3>
        <div role="radiogroup" aria-labelledby="class-end-choice" className="grid gap-3 sm:grid-cols-2" {...radios.group}>
          {ENDINGS.map((choice) => {
            const chosen = choice === ending;
            return (
              <button
                key={choice}
                {...radios.radio(choice)}
                type="button"
                role="radio"
                aria-checked={chosen}
                onClick={() => setEnding(choice)}
                className={cn(
                  "rounded-lg flex items-start gap-3 border p-3 text-left transition-colors",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                  chosen ? "border-ink bg-sunk" : "border-input hover:border-ink",
                )}
              >
                <span
                  aria-hidden
                  className={cn(
                    "mt-1 size-3 shrink-0 border-[1.5px]",
                    chosen ? "border-ink bg-ink" : "border-input",
                  )}
                />
                <span className="min-w-0 space-y-0.5">
                  <span className="block font-medium">{t(ENDING_KEYS[choice].title)}</span>
                  <span className="block text-small text-muted-foreground">
                    {t(ENDING_KEYS[choice].body)}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
        <p className="max-w-3xl text-small text-muted-foreground">{t("class.end.both")}</p>

        <div className="max-w-md space-y-1">
          {/* The name in its own case: the label is set in capitals, and what is compared is
              the name as it is written. */}
          <Label htmlFor="class-end-confirm">
            {t("class.end.typeName")}{" "}
            <span className="font-medium normal-case tracking-normal">«{subject}»</span>
          </Label>
          <Input
            id="class-end-confirm"
            value={typed}
            autoComplete="off"
            onChange={(event) => setTyped(event.target.value)}
          />
        </div>
        <Button variant="destructive" disabled={!confirmed || end.isPending} onClick={run}>
          {end.isPending ? <Spinner /> : ending === "disable" ? <UserX /> : <UserMinus />}
          {t("class.end.run")}
        </Button>
      </section>
    </>
  );
}
