import { Check, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { Alert, Skeleton, Spinner } from "@/components/ui/misc";
import { useT } from "@/lib/i18n";
import { Link } from "@/lib/router";
import { cn } from "@/lib/utils";

import { useOpenStageReview, useSaveStageReview, useStageReview } from "./queries";
import type { StageInstrument, StageQuestion } from "./types";

/**
 * WHAT THE TEACHER SAYS ABOUT THE BUILD THEY ARE LOOKING AT.
 *
 * The blind comparison measures the variants; this measures the chain that produces them,
 * and it is asked HERE — beside the artifact, on the stage's own screen — because a
 * judgement collected anywhere else is a judgement about a memory of it. That is also why
 * it is a column and not a page: what is being scored has to be on screen while the
 * scoring happens.
 *
 * NOTHING IN THE WORDING LIVES IN THIS FILE. The questions, their options and their order
 * come from `study/api/stage_instruments.py`, because rewording one changes what was
 * measured and that has to be one edit in one place. What is here is the frame: the title,
 * the state, the button, and what to do next.
 *
 * `--attention` is spent once and on the last thing: the button while there is something
 * to save, and then the step that follows. A form whose every row shouts is a form nobody
 * reads to the end.
 *
 * NO GROUND OF ITS OWN (2026-09-01, explicit user request, reversing the tint added the
 * same day). `--study` moved to the BUTTON that opens this panel, in `StageGate`, which is
 * where it now does the work the tint was doing: saying that this block is the study's and
 * not the artifact's. A coloured ground under a form is the wrong place for it anyway —
 * every control inside then has to fight it, and the selected radios did.
 */
export function StageReview({
  artifact,
  nextStep,
  onClose,
}: {
  artifact: string;
  nextStep: number | null;
  /** Given by the drawer that holds it, so the panel can shut itself once it is answered. */
  onClose?: () => void;
}) {
  const { t, plural } = useT();
  const review = useStageReview(artifact);
  const save = useSaveStageReview(artifact);
  const open = useOpenStageReview();

  const mine = review.data?.mine ?? null;
  const [answers, setAnswers] = useState<Record<string, string>>({});
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
  // the bundle does not serve this route, and a blank column reads as «esto no existe».
  if (review.isError || !instrument) return null;

  if (!review.data?.built) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-study">{t("stageReview.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-small text-muted-foreground">{t("stageReview.notBuilt")}</p>
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

  const pick = (key: string, value: string) => {
    setTouched(true);
    setAnswers((current) => ({ ...current, [key]: value }));
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="gap-1 pb-3">
          <div className="flex items-center gap-2">
            <CardTitle className="flex-1 text-study">{t("stageReview.title")}</CardTitle>
            <Badge variant={answered ? "settled" : "attention"}>
              {t(answered ? "stageReview.saved" : "stageReview.unanswered")}
            </Badge>
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
          {instrument.questions.map((question) => (
            <Choice
              key={question.key}
              question={question}
              value={answers[question.key]}
              onPick={(value) => pick(question.key, value)}
            />
          ))}

          {/* The one scale shared with the rest of the study, and the last question: with
              it set, the person reached the end of the form. */}
          <fieldset className="space-y-2">
            <legend className="text-small font-medium">{instrument.overall.question}</legend>
            <div
              role="radiogroup"
              aria-label={instrument.overall.question}
              className="grid grid-cols-5 gap-1.5"
            >
              {Array.from(
                { length: instrument.overall.scale.max - instrument.overall.scale.min + 1 },
                (_, i) => instrument.overall.scale.min + i,
              ).map((value) => (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={overall === value}
                  onClick={() => {
                    setTouched(true);
                    setOverall(value);
                  }}
                  className={cn(
                    "nums border px-2 py-1.5 text-small transition-colors",
                    overall === value
                      ? "border-primary bg-accent font-medium"
                      : "border-border bg-card hover:bg-accent",
                  )}
                >
                  {value}
                </button>
              ))}
            </div>
            <div className="flex justify-between">
              {instrument.overall.scale.ends.map((end) => (
                <span key={end} className="text-micro text-muted-foreground">
                  {end}
                </span>
              ))}
            </div>
          </fieldset>

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

          {save.isError ? <Alert tone="danger">{t("stageReview.failed")}</Alert> : null}

          <div className="space-y-1.5">
            <Button
              // The colour goes where the next move is: on the button while there is
              // something to save, and on the step that follows once there is not.
              variant={dirty ? "attention" : "outline"}
              className="w-full"
              disabled={save.isPending || (!dirty && answered)}
              onClick={() =>
                save.mutate(
                  { answers, overall, note: note.trim() || null },
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

      {/* THE ONE OBVIOUS NEXT MOVE, and it appears only once the verdict is in. There is no
          «corregir a mano» button beside it because correcting is what the whole left-hand
          column already is: an extra button would only scroll the page to something that
          is already on screen. */}
      {answered ? (
        <Alert tone="attention" title={t("stageReview.done.title")}>
          <p>{t("stageReview.done.body")}</p>
          <div className="mt-3">
            <Link to={nextStep === null ? "/generate" : STEP_PATH[nextStep]}>
              <Button variant="attention">
                {nextStep === null
                  ? t("stageReview.done.generate")
                  : t("stageReview.done.next", { n: nextStep })}
              </Button>
            </Link>
          </div>
        </Alert>
      ) : null}
    </div>
  );
}

// Where «el paso siguiente» leads. The numbers are the bar's, so a renamed route breaks
// here and not silently on the one button a person is meant to press.
const STEP_PATH: Record<number, string> = {
  2: "/prepare/profile",
  3: "/prepare/graph",
  4: "/prepare/bank",
};

/**
 * One question, its options stacked, best first.
 *
 * A row and not a chip row: the options are sentences («Falta alguna secundaria»), and a
 * wrapped chip row makes three sentences look like six. The selected one is marked with
 * the ink and not with a colour — this palette spends colour on evidence, and a preference
 * somebody has just expressed is not evidence of anything yet.
 */
function Choice({
  question,
  value,
  onPick,
}: {
  question: StageQuestion;
  value: string | undefined;
  onPick: (value: string) => void;
}) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-small font-medium">{question.question}</legend>
      {question.hint ? (
        <p className="-mt-1 text-small text-muted-foreground">{question.hint}</p>
      ) : null}
      <div role="radiogroup" aria-label={question.question} className="space-y-1.5">
        {(question.options ?? []).map((option) => {
          const on = value === option.value;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={on}
              onClick={() => onPick(option.value)}
              className={cn(
                "flex w-full items-center gap-2.5 border px-2.5 py-2 text-left text-small transition-colors",
                on
                  ? "border-primary bg-accent font-medium"
                  : "border-border bg-card hover:bg-accent",
              )}
            >
              <span
                aria-hidden
                className={cn(
                  "size-3 shrink-0 rounded-full",
                  on ? "border-[3px] border-primary bg-card" : "border border-input",
                )}
              />
              {option.label}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

export type { StageInstrument };
