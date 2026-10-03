import { BookOpen, ChevronRight, RotateCcw } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Alert, LoadError, Skeleton } from "@/components/ui/misc";
import { when } from "@/lib/format";
import { useT, type Key } from "@/lib/i18n";

import { Composer, type Picking } from "./Composer";
import { ConceptMap } from "./ConceptMap";
import type { TutorDraft } from "./draft";
import { NotesReader } from "./NotesReader";
import { Reply } from "./Reply";
import {
  useCancelTurn,
  useConversation,
  useOpenConversation,
  useRetryTurn,
  useSendMessage,
  useSyllabus,
} from "./queries";
import type { SyllabusUnit } from "./syllabus";
import { Thinking } from "./Thinking";
import { UnitDot } from "./TopicPicker";
import type { Conversation, Place, Turn } from "./types";

const FAILED_KEYS: Record<string, Key> = {
  failed: "tutor.failed.failed",
  cancelled: "tutor.failed.cancelled",
  interrupted: "tutor.failed.interrupted",
};

// The panel is one fixed height, so a long conversation scrolls inside it instead of
// pushing the box to write in below the fold: the window less what sits above it (the bar,
// the title and the tabs, about 18rem), never under 24rem. Shared with the list beside it.
export const PANEL_HEIGHT = "h-[max(24rem,calc(100dvh-18rem))]";

/**
 * One conversation: the turns, the reply on its way, and the box to write the next message.
 *
 * With no conversation chosen it is the start of a new one, which the first message creates;
 * the empty panel then shows the syllabus's units, each opening the concept picker on itself,
 * so a student who does not know how to begin begins by pointing at a unit.
 *
 * The concept a student chooses belongs to ONE message: it travels with it and is cleared
 * once sent, because from then on the conversation stands on it and the «Sobre» line shows
 * it as the server's own focus.
 * A reply arrives WHOLE, never token by token: the server checks it against the method before
 * anybody reads it, and a stream would show the very text a check may withdraw.
 */
export function ConversationView({
  id,
  ready,
  draft,
  onOpened,
}: {
  id: string | null;
  ready: boolean;
  draft: TutorDraft | null;
  onOpened: (id: string) => void;
}) {
  const { t } = useT();
  const conversation = useConversation(id);
  const open = useOpenConversation();
  const send = useSendMessage(id);
  const retry = useRetryTurn(id);
  const cancel = useCancelTurn(id);
  const syllabus = useSyllabus();
  const [message, setMessage] = useState(draft?.message ?? "");
  const [chosen, setChosen] = useState<string | null>(null);
  const [picking, setPicking] = useState<Picking>(null);
  const [reading, setReading] = useState<Place | null>(null);
  const scroller = useRef<HTMLDivElement>(null);

  const data = conversation.data;
  const pending = data?.pending ?? null;
  const turns = data?.turns ?? [];
  // The panel's own scroll, never the page's, and to the START of the newest turn: a reply
  // is read from its first line, and one with a concept map under it is taller than the
  // panel — scrolled to the foot, it showed the map and hid the question. The browser clamps
  // the position, so a turn shorter than the panel simply sits at the foot.
  useEffect(() => {
    const node = scroller.current;
    if (!node) return;
    const shown = node.querySelectorAll<HTMLElement>("[data-turn]");
    const last = shown[shown.length - 1];
    node.scrollTop = last
      ? last.getBoundingClientRect().top - node.getBoundingClientRect().top + node.scrollTop - 16
      : node.scrollHeight;
  }, [turns.length, pending?.status]);

  const sending = open.isPending || send.isPending;
  const error = open.error ?? send.error ?? retry.error;
  const canSend = ready && !sending && !pending && message.trim().length > 0;

  const submit = () => {
    if (!canSend) return;
    const text = message.trim();
    setPicking(null);
    if (id === null) {
      open.mutate(
        { message: text, generationId: draft?.generationId ?? null, concept: chosen },
        { onSuccess: (queued) => onOpened(queued.conversation.id) },
      );
    } else {
      send.mutate(
        { message: text, concept: chosen },
        {
          onSuccess: () => {
            setMessage("");
            setChosen(null);
          },
        },
      );
    }
  };

  if (id !== null && conversation.isLoading) return <Skeleton className={PANEL_HEIGHT} />;
  if (id !== null && !data) {
    return (
      <LoadError
        title={t("tutor.unreadable")}
        error={conversation.error}
        onRetry={conversation.refetch}
      />
    );
  }

  const last = turns[turns.length - 1];
  const unanswered = last?.role === "student" && last.failed ? last.failed : null;
  const units = syllabus.data ?? [];

  return (
    // `min-w-0`: a grid item is as wide as its widest content unless told otherwise, and an
    // unscaled concept map on a phone is wider than the phone.
    <section className={`flex min-w-0 flex-col rounded-lg border border-border bg-card ${PANEL_HEIGHT}`}>
      <div ref={scroller} className="thin-scroll min-h-0 flex-1 space-y-6 overflow-y-auto p-4 sm:px-6">
        {id === null ? (
          <Welcome
            fromExercise={Boolean(draft?.generationId)}
            units={ready ? units : []}
            onUnit={(unit) => setPicking({ unit })}
          />
        ) : null}
        {data ? <Opened conversation={data} /> : null}
        {turns.map((turn, index) => (
          <TurnBubble key={`${index}-${turn.at}`} turn={turn} onRead={setReading} />
        ))}
        {pending ? <Thinking pending={pending} onStop={() => cancel.mutate()} /> : null}
        {unanswered ? (
          <div className="flex flex-wrap items-center gap-2 text-small text-muted-foreground">
            <span>{t(FAILED_KEYS[unanswered] ?? "tutor.failed.failed")}</span>
            <Button
              variant="outline"
              size="sm"
              disabled={!ready || retry.isPending}
              onClick={() => retry.mutate()}
            >
              <RotateCcw />
              {t("tutor.retry")}
            </Button>
          </div>
        ) : null}
      </div>

      <div className="space-y-2 border-t border-border p-3">
        {error ? (
          <Alert tone="danger" title={t("tutor.sendFailed")}>
            <p>{error.message}</p>
          </Alert>
        ) : null}
        <Composer
          value={message}
          onChange={setMessage}
          onSubmit={submit}
          disabled={!ready}
          canSend={canSend}
          sending={sending}
          units={units}
          focus={data?.state?.focus ?? []}
          chosen={chosen}
          onChosen={setChosen}
          picking={picking}
          onPicking={setPicking}
        />
      </div>
      <NotesReader place={reading} onClose={() => setReading(null)} />
    </section>
  );
}

/**
 * The empty conversation: what the tutor is, and the syllabus as a way in.
 *
 * The units are numbered because a syllabus is a sequence and its order is what a student
 * remembers it by. Each row opens the picker on that unit; none of them sends anything.
 */
function Welcome({
  fromExercise,
  units,
  onUnit,
}: {
  fromExercise: boolean;
  units: SyllabusUnit[];
  onUnit: (unit: number) => void;
}) {
  const { t, plural } = useT();
  return (
    <div className="mx-auto max-w-2xl space-y-5 py-4">
      <div className="space-y-2">
        <p className="text-title font-semibold">{t("tutor.start.title")}</p>
        <p className="max-w-prose text-muted-foreground">
          {fromExercise ? t("tutor.start.fromExercise") : t("tutor.start.body")}
        </p>
      </div>
      {!fromExercise && units.length > 0 ? (
        <div className="space-y-1">
          <p className="text-micro font-condensed uppercase text-muted-foreground">
            {t("tutor.start.units")}
          </p>
          <ol className="border-y border-border">
            {units.map((unit, index) => (
              <li key={unit.name} className="border-t border-border first:border-t-0">
                <button
                  type="button"
                  onClick={() => onUnit(index)}
                  className="group flex w-full items-baseline gap-3 px-1 py-2 text-left transition-colors hover:bg-accent"
                >
                  <span className="nums w-4 shrink-0 text-small text-muted-foreground">{index + 1}</span>
                  <UnitDot index={index} total={units.length} />
                  <span className="min-w-0 flex-1">{unit.name}</span>
                  <span className="shrink-0 text-small text-muted-foreground">
                    {plural("tutor.topic.count", unit.concepts.length, { n: unit.concepts.length })}
                  </span>
                  <ChevronRight
                    className="size-4 shrink-0 self-center text-muted-foreground transition-transform group-hover:translate-x-0.5"
                    aria-hidden
                  />
                </button>
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </div>
  );
}

function Opened({ conversation }: { conversation: Conversation }) {
  const { t } = useT();
  if (conversation.opened_from?.kind !== "generation") return null;
  return <p className="text-small text-muted-foreground">{t("tutor.openedFrom")}</p>;
}

// Who is speaking, written over every turn: the name in ink, the rest quiet.
const SPEAKER = "text-micro font-condensed uppercase text-muted-foreground";

/**
 * One turn, and whose it is at a glance.
 *
 * The two voices are two materials, not two shades of one. What the student sent is a block
 * of INK on the right, as wide as its text: something handed over, closed. What the tutor
 * answers is the page itself on the left — open text on the card, tied by one rule to the
 * map and the places of the notes that belong to it — because it is the part to read and
 * work on, with the question it closes with set apart from its explanation (`Reply`). Each is named above, so the difference never rests on colour or side alone.
 */
function TurnBubble({ turn, onRead }: { turn: Turn; onRead: (place: Place) => void }) {
  const { t } = useT();
  if (turn.role === "student") {
    return (
      <div data-turn className="flex flex-col items-end gap-1.5">
        <p className={`${SPEAKER} text-right`}>
          <span className="font-semibold text-foreground">{t("tutor.you")}</span>
          {turn.concept ? ` · ${t("tutor.topic.about", { name: turn.concept })}` : ""} · {when(turn.at)}
        </p>
        <div className="max-w-[85%] whitespace-pre-wrap break-words bg-primary px-3.5 py-2.5 text-body text-primary-foreground">
          {turn.text}
        </div>
      </div>
    );
  }
  return (
    <div data-turn className="space-y-2.5 border-l-2 border-foreground pl-4">
      <p className={SPEAKER}>
        <span className="font-semibold text-foreground">{t("tutor.tutor")}</span> · {when(turn.at)}
      </p>
      <Reply text={turn.text} />
      <ConceptMap map={turn.concept_map} />
      {turn.references && turn.references.length > 0 ? (
        <References places={turn.references} onRead={onRead} />
      ) : null}
    </div>
  );
}

/**
 * Where in the notes to look, each place opening the reader at it. This is the only place a
 * reply's origin is written — the reply itself says «en los apuntes» and names no section —
 * and the places are the card's, never the model's.
 */
function References({ places, onRead }: { places: Place[]; onRead: (place: Place) => void }) {
  const { t } = useT();
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-small text-muted-foreground">
      <BookOpen className="size-3.5" aria-hidden />
      <span>{t("tutor.references")}</span>
      {places.map((place) => {
        const label = lastPart(place.location) || place.document;
        return (
          <button
            key={`${place.document}|${place.location}`}
            type="button"
            onClick={() => onRead(place)}
            title={t("tutor.notes.open", { place: place.location || place.document })}
            className="max-w-full truncate rounded-full border border-border px-2 py-0.5 text-foreground underline-offset-2 transition-colors hover:bg-accent hover:underline"
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

/** The section a heading path ends in, which is what a reply names. */
function lastPart(location: string): string {
  const parts = location.split(" > ");
  return parts[parts.length - 1] ?? "";
}
