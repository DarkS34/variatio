import "./i18n";

import { useState } from "react";

import { ChainGate } from "@/components/ChainGate";
import { GuideLink } from "@/components/GuideLink";
import { InfoHint } from "@/components/ui/hint";
import { Alert, LoadError, Skeleton } from "@/components/ui/misc";
import { Tabs } from "@/components/ui/tabs";
import { useT } from "@/lib/i18n";
import { useEngineOffline, usePipeline } from "@/state/queries";

import { ConversationList } from "./ConversationList";
import { ConversationView } from "./ConversationView";
import { CriteriaPanel } from "./CriteriaPanel";
import { takeTutorDraft, type TutorDraft } from "@/lib/tutorDraft";
import { useTutorStatus } from "./queries";

/**
 * THE SOCRATIC TUTOR: A CHAT, AND FOR A TEACHER ALSO THE SUBJECT'S CRITERIA.
 *
 * A student sees one thing — their conversations, the list beside the one open — because the
 * advantage over a chatbot is on the server (the card each reply is written with) and not in
 * controls: there is nothing to choose before asking. A teacher sees a second tab with the
 * criteria the tutor applies in this subject, built by the system and corrected there; the
 * role decides it (`can_edit`), never something the account declared about itself.
 */
export function TutorScreen() {
  const { t } = useT();
  const status = useTutorStatus();
  const pipeline = usePipeline();
  const offline = useEngineOffline();
  const [tab, setTab] = useState("conversation");
  const [selected, setSelected] = useState<string | null>(null);
  // Taken once, on the first render: a draft handed over by «Trabajar con el tutor».
  const [draft, setDraft] = useState<TutorDraft | null>(() => takeTutorDraft());

  const header = (
    <header className="space-y-1.5">
      <div className="flex items-center gap-2">
        <h1 className="font-display font-expanded text-display">{t("tutor.title")}</h1>
        <InfoHint label={t("tutor.whatIsThis")}>{t("tutor.whatIsThis.body")}</InfoHint>
      </div>
      <GuideLink slug="tutor" />
    </header>
  );

  if (status.isLoading) {
    return (
      <div className="space-y-5">
        {header}
        <Skeleton className="h-96" />
      </div>
    );
  }
  if (!status.data) {
    return (
      <div className="space-y-5">
        {header}
        <LoadError title={t("tutor.unreadable")} error={status.error} onRetry={status.refetch} />
      </div>
    );
  }

  const canEdit = status.data.can_edit;
  return (
    <div className="space-y-5">
      {header}

      {status.data.ready && offline ? (
        <Alert tone="attention" title={t("generate.noEngine")}>
          <p>{t("generate.noEngineBody", { reason: t(offline) })}</p>
        </Alert>
      ) : null}

      {!status.data.ready ? (
        <ChainGate title={t("tutor.blocked")} stages={pipeline.data?.stages ?? []} />
      ) : null}

      {canEdit ? (
        <Tabs
          items={[
            { value: "conversation", label: t("tutor.tab.conversation") },
            { value: "criteria", label: t("tutor.tab.criteria") },
          ]}
          value={tab}
          onChange={setTab}
        />
      ) : null}

      {tab === "criteria" && canEdit ? (
        <CriteriaPanel ready={status.data.ready} />
      ) : (
        <div className="grid gap-7 lg:grid-cols-[18rem_minmax(0,1fr)]">
          <ConversationList
            selected={selected}
            onSelect={(id) => {
              setDraft(null);
              setSelected(id);
            }}
          />
          <ConversationView
            key={selected ?? "new"}
            id={selected}
            ready={status.data.ready && !offline}
            draft={selected === null ? draft : null}
            onOpened={(id) => {
              setDraft(null);
              setSelected(id);
            }}
          />
        </div>
      )}
    </div>
  );
}
