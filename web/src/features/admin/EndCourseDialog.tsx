import { UserMinus, UserX } from "lucide-react";
import { useState } from "react";

import { CARD_CHOICE, CARD_CHOSEN, ChoiceMark } from "@/components/ui/choice";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input, Label } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import { useRadioGroup } from "@/components/ui/radio";
import { useToast } from "@/components/ui/toast";
import { useT, type Key } from "@/lib/i18n";
import type { AdminWorkspace } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useAdminEndCourse } from "@/state/queries";

type Ending = "disable" | "remove";

const ENDINGS: Ending[] = ["disable", "remove"];

const ENDING_KEYS: Record<Ending, { title: Key; body: Key }> = {
  disable: { title: "class.end.disable", body: "class.end.disable.body" },
  remove: { title: "class.end.remove", body: "class.end.remove.body" },
};

/**
 * «Fin de curso» of one subject, opened from its row in «Asignaturas»: every student out at
 * once, paused by default or removed, and the class link paused. The administrator's alone
 * (the user's decision, 2026-10-07: it was the owner's, at the foot of «Clase»).
 *
 * One dialog says what happens, lets the administrator choose, and asks for the subject's
 * name typed, as deleting a subject does. Destructive, so it spends no `--attention`. Mounted
 * only while open, so it never keeps a choice or a name from the time before.
 */
export function EndCourseDialog({ workspace, onClose }: { workspace: AdminWorkspace; onClose: () => void }) {
  const { t, plural } = useT();
  const toast = useToast();
  const end = useAdminEndCourse();
  const [ending, setEnding] = useState<Ending>("disable");
  const [typed, setTyped] = useState("");
  const radios = useRadioGroup(ENDINGS, ending, setEnding);
  const subject = workspace.name;
  const confirmed = typed.trim() === subject.trim() && subject.trim() !== "";

  const run = () =>
    end.mutate(
      { slug: workspace.slug, action: ending },
      {
        onSuccess: ({ students }) => {
          onClose();
          toast({
            title: plural(ending === "disable" ? "class.end.paused" : "class.end.removed", students),
            description: subject,
          });
        },
        onError: (error: Error) =>
          toast({ title: t("class.failed"), description: error.message, tone: "danger" }),
      },
    );

  return (
    <Dialog
      open
      onClose={onClose}
      title={t("class.end.confirmTitle", { subject })}
      description={t("class.end.lead")}
      className="max-w-xl"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button variant="destructive" disabled={!confirmed || end.isPending} onClick={run}>
            {end.isPending ? <Spinner /> : ending === "disable" ? <UserX /> : <UserMinus />}
            {t("class.end.run")}
          </Button>
        </>
      }
    >
      <div className="space-y-4 text-body">
        <div className="space-y-2">
          <p id="admin-end-choice" className="text-micro font-condensed uppercase text-muted-foreground">
            {t("class.end.what")}
          </p>
          <div role="radiogroup" aria-labelledby="admin-end-choice" className="grid gap-3 sm:grid-cols-2" {...radios.group}>
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
                  className={cn(CARD_CHOICE, "flex items-start gap-3 p-3", chosen && CARD_CHOSEN)}
                >
                  <ChoiceMark chosen={chosen} className="mt-1.5" />
                  <span className="min-w-0 space-y-0.5">
                    <span className="block font-medium">{t(ENDING_KEYS[choice].title)}</span>
                    <span className="block text-small text-muted-foreground">{t(ENDING_KEYS[choice].body)}</span>
                  </span>
                </button>
              );
            })}
          </div>
          <p className="text-small text-muted-foreground">{t("class.end.both")}</p>
        </div>
        <div className="space-y-1">
          {/* The name in its own case: the label is set in capitals, and what is compared is
              the name as it is written. */}
          <Label htmlFor="admin-end-confirm">
            {t("class.end.typeName")}{" "}
            <span className="font-medium normal-case tracking-normal">«{subject}»</span>
          </Label>
          <Input
            id="admin-end-confirm"
            autoFocus
            autoComplete="off"
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && confirmed && !end.isPending) run();
            }}
          />
        </div>
      </div>
    </Dialog>
  );
}
