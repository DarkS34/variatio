import { CircleAlert, CircleSlash, Pencil, Plus, Save, Trash2 } from "lucide-react";
import { type RefObject, type UIEventHandler, useCallback, useId } from "react";

import { Markdown } from "@/components/Markdown";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Textarea } from "@/components/ui/input";
import { Alert, Spinner } from "@/components/ui/misc";
import { RowAction, RowGestures } from "@/components/ui/table";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

import type { DocumentPage } from "../types";

const FAILED_MARK = "> [TRANSCRIPCIÓN FALLIDA"; // i18n-exempt: lo escribe `pages.py`

export type PageMark = "failed" | "empty" | "ok";

/** What a page needs: nothing, a look because it came back empty, or writing because it failed. */
export function pageMark(page: DocumentPage): PageMark {
  if (page.failed) return "failed";
  return page.text.trim() ? "ok" : "empty";
}

function draftMark(text: string): PageMark {
  if (text.trimStart().startsWith(FAILED_MARK)) return "failed";
  return text.trim() ? "ok" : "empty";
}

/** The page being corrected — one at a time — and what has been written in it so far. */
export interface Editing {
  index: number;
  draft: string;
}

/**
 * The transcription, every page one under another as the builds read it — formatted, not as
 * markdown source — each corrected in place.
 *
 * A page opens for correction from its pencil, which stays in sight; inserting and deleting
 * show on hover or focus, as a row's gestures do, and wait while a page is being corrected,
 * since both renumber the pages after them.
 */
export function TextPane({
  name,
  pages,
  register,
  paneRef,
  onScroll,
  editing,
  working,
  saving,
  onDraft,
  onEdit,
  onCancel,
  onSave,
  onInsert,
  onDelete,
  className,
}: {
  name: string;
  pages: DocumentPage[];
  register: (number: number, node: HTMLElement | null) => void;
  paneRef: RefObject<HTMLDivElement | null>;
  onScroll: UIEventHandler<HTMLDivElement>;
  editing: Editing | null;
  working: boolean;
  saving: boolean;
  onDraft: (text: string) => void;
  onEdit: (page: DocumentPage) => void;
  onCancel: () => void;
  onSave: () => void;
  onInsert: (after: number) => void;
  onDelete: (index: number) => void;
  className?: string;
}) {
  const { t } = useT();
  return (
    <div
      ref={paneRef}
      onScroll={onScroll}
      role="region"
      aria-label={t("doc.view.text")}
      tabIndex={0}
      className={cn("well thin-scroll rows min-h-0 overflow-y-auto px-4 py-4", className)}
    >
      {pages.map((page) => (
        <PageBlock
          key={page.index}
          name={name}
          page={page}
          register={register}
          editing={editing?.index === page.index ? editing : null}
          locked={working || editing !== null}
          only={pages.length === 1}
          saving={saving}
          onDraft={onDraft}
          onEdit={() => onEdit(page)}
          onCancel={onCancel}
          onSave={onSave}
          onInsert={() => onInsert(page.index)}
          onDelete={() => onDelete(page.index)}
        />
      ))}
    </div>
  );
}

function PageBlock({
  name,
  page,
  register,
  editing,
  locked,
  only,
  saving,
  onDraft,
  onEdit,
  onCancel,
  onSave,
  onInsert,
  onDelete,
}: {
  name: string;
  page: DocumentPage;
  register: (number: number, node: HTMLElement | null) => void;
  editing: Editing | null;
  locked: boolean;
  only: boolean;
  saving: boolean;
  onDraft: (text: string) => void;
  onEdit: () => void;
  onCancel: () => void;
  onSave: () => void;
  onInsert: () => void;
  onDelete: () => void;
}) {
  const { t } = useT();
  const titleId = useId();
  const mark = pageMark(page);
  const attach = useCallback(
    (node: HTMLElement | null) => register(page.index, node),
    [page.index, register],
  );

  return (
    <section ref={attach} aria-labelledby={titleId} className="group space-y-2">
      <header className="flex min-h-7 items-center gap-2">
        <h3 id={titleId} className="text-micro font-condensed uppercase text-muted-foreground nums">
          {t("doc.pageNumber", { n: page.index })}
        </h3>
        <PageMarkBadge mark={mark} />
        {editing ? null : (
          <RowGestures
            className="ml-auto"
            always={
              <RowAction
                label={t("doc.correctPage", { page: page.index, name })}
                title={t("doc.correct")}
                icon={<Pencil />}
                onClick={onEdit}
                disabled={saving}
              />
            }
          >
            <RowAction
              label={t("doc.insertAfterPage", { page: page.index })}
              title={t("doc.insertHint")}
              icon={<Plus />}
              onClick={onInsert}
              disabled={locked}
            />
            <RowAction
              label={t("doc.deletePageN", { page: page.index })}
              title={only ? t("doc.onlyPage") : t("doc.deleteHint")}
              icon={<Trash2 />}
              onClick={onDelete}
              disabled={locked || only}
              danger
            />
          </RowGestures>
        )}
      </header>
      {editing ? (
        <PageEditor
          index={page.index}
          draft={editing.draft}
          dirty={editing.draft !== page.text}
          saving={saving}
          onDraft={onDraft}
          onCancel={onCancel}
          onSave={onSave}
        />
      ) : mark === "empty" ? (
        <p className="text-small text-muted-foreground">{t("doc.noContent")}</p>
      ) : (
        <Markdown>{page.text}</Markdown>
      )}
    </section>
  );
}

/**
 * One page open for correction: its markdown as it is saved, what a correction means, and
 * the two ways out. What is written here wins over the model in every later build.
 */
function PageEditor({
  index,
  draft,
  dirty,
  saving,
  onDraft,
  onCancel,
  onSave,
}: {
  index: number;
  draft: string;
  dirty: boolean;
  saving: boolean;
  onDraft: (text: string) => void;
  onCancel: () => void;
  onSave: () => void;
}) {
  const { t } = useT();
  const mark = draftMark(draft);
  return (
    <div className="space-y-3">
      {mark === "failed" ? (
        <Alert tone="danger" title={t("doc.failed")}>
          <p>{t("doc.failedPage")}</p>
        </Alert>
      ) : mark === "empty" ? (
        <Alert tone="attention" title={t("doc.blank")}>
          <p>{t("doc.emptyPage")}</p>
        </Alert>
      ) : null}
      <Field
        label={t("doc.markdownOf", { page: index })}
        description={`${t("doc.description")} ${t("doc.savedAsIs")}`}
      >
        {(props) => (
          <Textarea
            {...props}
            value={draft}
            onChange={(event) => onDraft(event.target.value)}
            spellCheck={false}
            autoFocus
            autoGrow
            className="min-h-40 font-mono leading-relaxed"
          />
        )}
      </Field>
      <div className="flex flex-wrap items-center justify-end gap-2">
        {dirty ? (
          <p className="mr-auto text-small text-muted-foreground">{t("doc.pageDirty", { page: index })}</p>
        ) : null}
        <Button variant="ghost" onClick={onCancel} disabled={saving}>
          {t("common.cancel")}
        </Button>
        <Button onClick={onSave} disabled={!dirty || saving}>
          {saving ? <Spinner /> : <Save />}
          {t("doc.savePage")}
        </Button>
      </div>
    </div>
  );
}

function PageMarkBadge({ mark }: { mark: PageMark }) {
  const { t } = useT();
  if (mark === "failed") {
    return (
      <Badge variant="danger" mark={<CircleAlert />}>
        {t("doc.mark.failed")}
      </Badge>
    );
  }
  if (mark === "empty") {
    return (
      <Badge variant="attention" mark={<CircleSlash />}>
        {t("doc.mark.empty")}
      </Badge>
    );
  }
  return null;
}
