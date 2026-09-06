import { Check, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { Alert, Skeleton, Spinner } from "@/components/ui/misc";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

import { useOpenStageReview, useSaveStageReview, useStageReview } from "./queries";
import { questionCount, type StageInstrument, type StageScale } from "./types";

/**
 * What the teacher says about the build they are looking at.
 *
 * The blind comparison measures the variants; this measures the chain that produces them,
 * and it is asked HERE, beside the artifact, because a judgement collected anywhere else is
 * a judgement about a memory of it.
 *
 * NOTHING in the wording lives in this file: the statements, the rungs and their order come
 * from `evaluation/api/stage_instruments.py`, because rewording one changes what was
 * measured. What is here is the frame — the title, the state, the button, what comes next.
 *
 * A Likert form: every item is a statement and the answer is how far the person agrees, on
 * ONE five-rung scale shared by all of them, "en conjunto" included. The rungs are named
 * once in a header row aligned to the five columns every row of buttons uses, and each
 * button carries its rung as its accessible name. The number IS the score, 5 being best.
 *
 * `--attention` is spent once and on the last thing: the button while there is something to
 * save, then the step that follows. A form whose every row shouts is one nobody finishes.
 *
 * No ground of its own — `--evaluation` is on the BUTTON that opens this panel, which is
 * where it does the work: a coloured ground under a form is fought by every control inside
 * it, the selected radios first.
 */
export function StageReview({
  artifact,
  curated,
  onClose,
}: {
  artifact: string;
  /** Whether the artifact was corrected before this verdict — the evaluation's own contrast.
   *  Told from above, because the panel cannot see an edit made beside it. */
  curated?: boolean;
  /** Given by the drawer that holds it, so the panel can shut itself once it is answered. */
  onClose?: () => void;
}) {
  const { t, plural } = useT();
  const review = useStageReview(artifact);
  const save = useSaveStageReview(artifact);
  const open = useOpenStageReview();

  const mine = review.data?.mine ?? null;
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [overall, setOverall] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [touched, setTouched] = useState(false);

  // The saved answers become the form's state ONCE the payload lands, and never again
  // afterwards: re-seeding on every render would throw away whatever is being typed, and
  // re-seeding on every refetch would undo a click the moment the window regains focus.
  useEffect(() => {
    if (!review.data || touched) return;
    setAnswers(mine?.answers ?? {});
    setOverall(mine?.overall ?? null);
    setNote(mine?.note ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [review.data]);

  // Recorded once, when the form is actually DRAWN — which is something the browser knows
  // and the server cannot: fetching the payload is not the same as a person seeing it.
  const built = review.data?.built ?? false;
  useEffect(() => {
    if (built) open.mutate(artifact);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [built, artifact]);

  const instrument = review.data?.instrument;
  const remaining = useMemo(() => {
    if (!instrument) return 0;
    const unanswered = instrument.questions.filter((q) => !answers[q.key]).length;
    return unanswered + (overall === null ? 1 : 0);
  }, [instrument, answers, overall]);

  if (review.isLoading) {
    return (
      <Card>
        <CardContent className="space-y-3 p-4">
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-24 w-full" />
        </CardContent>
      </Card>
    );
  }

  // A panel that cannot load its data says so; it never renders null. An API older than
  // the bundle does not serve this route, and a blank column reads as "esto no existe".
  if (review.isError || !instrument) return null;

  if (!review.data?.built) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-evaluation">{t("stageReview.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-small text-muted-foreground">
            {plural("stageReview.notBuilt", questionCount(instrument))}
          </p>
        </CardContent>
      </Card>
    );
  }

  const answered = mine?.answered ?? false;
  const dirty =
    touched &&
    (JSON.stringify(answers) !== JSON.stringify(mine?.answers ?? {}) ||
      overall !== (mine?.overall ?? null) ||
      note !== (mine?.note ?? ""));

  const pick = (key: string, value: number) => {
    setTouched(true);
    setAnswers((current) => ({ ...current, [key]: value }));
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="gap-1 pb-3">
          <div className="flex items-center gap-2">
            <CardTitle className="flex-1 text-evaluation">{t("stageReview.title")}</CardTitle>
            {/* Only "guardada", never "sin contestar": the button that opens this panel is
                already filled while the form is unanswered and quiet once it is not, so a
                badge repeating it inside was the same fact twice, a centimetre apart. What
                survives is the half the opener cannot say — that what you typed persisted. */}
            {answered ? <Badge variant="settled">{t("stageReview.saved")}</Badge> : null}
            {onClose ? (
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={onClose}
                aria-label={t("stageReview.close")}
                title={t("stageReview.close")}
              >
                <X />
              </Button>
            ) : null}
          </div>
          <p className="text-small text-muted-foreground">{instrument.preamble}</p>
        </CardHeader>

        <CardContent className="space-y-5">
          <ScaleHeader scale={instrument.scale} />

          {instrument.questions.map((question) => (
            <Statement
              key={question.key}
              statement={question.statement}
              hint={question.hint}
              scale={instrument.scale}
              value={answers[question.key]}
              onPick={(value) => pick(question.key, value)}
            />
          ))}

          {/* The one column shared with the rest of the evaluation, and the last statement:
              with it set, the person reached the end of the form. */}
          <Statement
            statement={instrument.overall.statement}
            scale={instrument.scale}
            value={overall ?? undefined}
            onPick={(value) => {
              setTouched(true);
              setOverall(value);
            }}
          />

          <div className="space-y-2">
            <label htmlFor="stage-review-note" className="block text-small font-medium">
              {instrument.note.question}{" "}
              <span className="font-normal text-muted-foreground">
                {t("stageReview.optional")}
              </span>
            </label>
            <Textarea
              id="stage-review-note"
              rows={3}
              value={note}
              placeholder={instrument.note.hint}
              onChange={(event) => {
                setTouched(true);
                setNote(event.target.value);
              }}
            />
          </div>

          {save.isError ? <Alert tone="danger" title={t("stageReview.failed")} /> : null}

          <div className="space-y-1.5">
            <Button
              // The colour goes where the next move is: on the button while there is
              // something to save, and on the step that follows once there is not.
              variant={dirty ? "attention" : "outline"}
              className="w-full"
              disabled={save.isPending || (!dirty && answered)}
              onClick={() =>
                save.mutate(
                  { answers, overall, note: note.trim() || null, curated },
                  { onSuccess: () => setTouched(false) },
                )
              }
            >
              {save.isPending ? <Spinner /> : answered ? <Check /> : null}
              {t(answered && !dirty ? "stageReview.saved" : answered ? "stageReview.saveAgain" : "stageReview.save")}
            </Button>
            {remaining > 0 ? (
              <p className="text-center text-small text-muted-foreground">
                {plural("stageReview.remaining", remaining)}
              </p>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {/* THE VERDICT IS SAVED AND THAT IS ALL THIS SAYS. The forward button used to live
          here and navigate without closing the stage, which walked a person into a step
          that then refused to build. There is ONE "continuar" now and it is at the foot of
          the screen, beside the offer to correct — two exits together, as they were asked
          for. */}
      {answered ? (
        <Alert tone="settled" title={t("stageReview.done.title")}>
          <p>{t("stageReview.done.body")}</p>
        </Alert>
      ) : null}
    </div>
  );
}


/** The rungs of the scale, in order, from what the instrument declares. */
function rungs(scale: StageScale): number[] {
  return Array.from({ length: scale.max - scale.min + 1 }, (_, i) => scale.min + i);
}

/**
 * The five rungs named once, over the same five columns every statement's buttons use.
 *
 * `aria-hidden`, because each button below already carries its rung's name: read aloud
 * this row would be the same five labels a second time before the first statement.
 */
function ScaleHeader({ scale }: { scale: StageScale }) {
  return (
    <div aria-hidden className="grid grid-cols-5 gap-1.5 border-b border-border pb-2">
      {rungs(scale).map((value, i) => (
        <div key={value} className="text-center">
          <span className="nums block text-small font-medium">{value}</span>
          <span className="block text-small leading-tight text-muted-foreground">
            {scale.labels[i]}
          </span>
        </div>
      ))}
    </div>
  );
}

/**
 * One statement and the five rungs under it.
 *
 * The selected rung is marked with the ink and not with a colour — this palette spends
 * colour on evidence, and a degree of agreement somebody has just expressed is not
 * evidence of anything yet.
 */
function Statement({
  statement,
  hint,
  scale,
  value,
  onPick,
}: {
  statement: string;
  hint?: string;
  scale: StageScale;
  value: number | undefined;
  onPick: (value: number) => void;
}) {
  const { t } = useT();
  return (
    <fieldset className="space-y-2">
      <legend className="text-body font-medium">{statement}</legend>
      {hint ? <p className="-mt-1 text-small text-muted-foreground">{hint}</p> : null}
      <div role="radiogroup" aria-label={statement} className="grid grid-cols-5 gap-1.5">
        {rungs(scale).map((rung, i) => {
          const on = value === rung;
          const name = t("stageReview.rung", { n: rung, label: scale.labels[i] ?? "" });
          return (
            <button
              key={rung}
              type="button"
              role="radio"
              aria-checked={on}
              aria-label={name}
              title={name}
              onClick={() => onPick(rung)}
              className={cn(
                "nums border px-2 py-1.5 text-small transition-colors",
                on ? "border-primary bg-accent font-medium" : "border-border bg-card hover:bg-accent",
              )}
            >
              {rung}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

export type { StageInstrument };
