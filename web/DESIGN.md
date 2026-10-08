# DESIGN.md — how every element of the interface is built

This file is the **rulebook for building UI** in `web/`. Read it before you add or change a
screen, a block, a table, a list, a control or a text. Every rule here is already applied
somewhere in the app; follow the existing primitive instead of drawing a new one.

- If a rule here and a request conflict, ask the user before you break the rule.
- If you must break a rule, write the reason in a comment beside the code and add the
  exception here and in `AGENTS.md`.
- The colour values and the why behind each token live in `src/index.css` (its comments)
  and in `AGENTS.md` → *Material and tokens*. This file says **what to use**; those say why.
- Verify in the browser, in light **and** dark, at 1440 px and at a narrow width. A green
  test suite does not prove a visual rule.

---

## 0. The checklist (run it on every new or changed element)

1. Is it a **block**? → `Card`/`.surface`, padding 20 px, head per §3. Blocks 28 px apart.
2. Is it a **table or a list of data rows**? → `Table` or `.rows`, **flat** in its block,
   never in a `.well`, never framed (§4).
3. Does a row have **gestures**? → `RowGestures` + `RowAction`, shown on hover/focus; the
   one that opens something stays visible (§4.4).
4. Is it a **list of sections** beside a section? → `Sections` with a 16 px mark and a
   detail line on every row (§5).
5. Do controls **share a line**? → one height: 36 px in a toolbar, 28 px in a row (§6).
6. Is it a **choice**? → `ChoicePill` (a few words) or `CARD_CHOICE` (a sentence) (§7).
7. Is it a **tab**? → `Tabs` or `TabStrip` (both are the sunk pill) (§7.3).
8. Is it a **search**? → `SearchInput` (§6.2).
9. Any **caption**? → `text-micro font-condensed uppercase text-muted-foreground` (§8).
10. Any **colour**? → a token, never a literal; one `--attention` per screen (§2).
11. Any **text**? → in `src/lib/i18n/es.ts` + `en.ts` (or the function's catalogue) (§10).
12. Run `pnpm exec tsc --noEmit`, `pnpm test`, `pnpm check:color`, `pnpm check:ui`,
    `pnpm check:i18n`, `pnpm build`, `pnpm check:lazy`, then look at it in the browser.

---

## 1. The material: Atlas in clay

The ground and the card are **one colour**. A block is told from the ground by **depth**, not
by a lighter sheet, not by a border.

| Class | What it is | Use it for | Never |
|---|---|---|---|
| `.surface` (`Card`) | a **block**: stands out of the ground | every group of content on a screen | inside another `.surface` (it goes flat there) |
| `.raised` | what can be **pressed** inside a block | a choice card (`CARD_CHOICE`), an `lg`/`xl` outline button | for decoration |
| `.well` | what **holds** something inside a block that is **not a row of data** | the drop zone, the graph canvas/tray, the tutor's box, a diagram, a live status strip, a QR code, a form or a conversation that **unfolds under a row**, a list that **scrolls inside** its block, the **pages of a document** (images that keep their white in either theme) | a table, a list of people/documents/invitations, an empty-state sentence, a form that is the block's only content |

Hard rules:

- **No white anywhere**, shadows included, in either theme. No token above L 0.93.
- **Two levels of depth, no more.** Block → raised/well. Nothing deeper.
- **Small things never cast a shadow**: chips, badges, tabs, fields, checkboxes, small
  buttons. What is chosen is the sunk tint `bg-sunk`, never a relief.
- **Never a border and a shadow on one element.** Depth draws the edge.
- **Never a frame per row, never a frame around a table or a list.** Rows are parted by
  rules.
- **Dividers stop short of a rounded edge**: `rule-inset-b`, `rule-inset-head` (tables do it
  for you), or the block's own padding.
- **Radii step down as they nest**: block `rounded-block` (24) → inner `rounded-inner` (16)
  → controls `rounded-lg`/`rounded-md` (12 and under).
- Floating things (dialog, menu, tooltip, sticky save bar): `bg-popover` + `shadow-overlay`.
- Tint a surface with `color-mix(in oklab, …)`, never `oklch` (hue interpolation shifts).

## 2. Colour

Colour encodes **position relative to the knowledge frontier**. Use the tokens and nothing
else; `check:color` only sees what is in `src/index.css`.

| Token | Meaning |
|---|---|
| `--settled` | behind you, done (grey) |
| `--attention` (text) / `--attention-fill` (fill) | **act here** — exactly **one per screen** |
| dimmed / dashed | ahead, not reachable yet |
| `--destructive` | damage (delete, remove, failed) |
| `--evaluation`, `--tutor` | the two optional functions, only where something **outside** their screen names them (a door, a tab, a button that opens them) |
| `--arm-naive/rag/system` | the study's three arms: bars and rows only, order fixed |
| `--qr` / `--qr-foreground` | a QR code: dark on light in both themes |

- **Text ink** is `--primary` (and `text-foreground`); a **filled control** is `bg-ink
  text-ink-foreground` or `bg-attention-fill text-attention-fill-foreground`. Never
  `bg-primary` under a label: in dark it is a white block.
- A border or a mark that must read in both themes uses `--primary` (the ink of a word),
  not `--ink`.
- Buttons: `default` (ink fill, the screen's main ordinary action), `attention` (the one
  frontier action), `outline`, `ghost`, `secondary`, `destructive`, `tutor` (opens the tutor
  from outside it), `link`.

## 3. Blocks

```tsx
<Card>
  <CardHeader>
    <CardTitle>Título</CardTitle>
    <CardDescription>Una frase de qué es.</CardDescription>
  </CardHeader>
  <CardContent>…</CardContent>
</Card>
```

- **Padding 20 px** (`p-5`) on every block. Only the list of sections and the week strip
  pad 8 px (`p-2`), because their rows are tiles that sink.
- **Head**: title `text-heading`, **no icon**; the sentence **4 px** under it
  (`CardDescription`, full width, no `max-w-*`); the content **16 px** under the head. Do not
  override `CardHeader`'s padding (`pb-2`, `pb-3` are forbidden). A head with no content
  closes the block at 20 px by itself.
- A hand-built block uses the same measures: `surface space-y-4 p-5`, title `h3.text-heading`,
  lead in a `space-y-1` group with the title.
- The block's one action sits **on the title's line**, right.
- **Blocks are 28 px apart** everywhere (`space-y-7`, `gap-7`), vertically and side by side.
- **Two blocks in the same row are the same height** (grid `items-stretch`, child `h-full`) —
  unless their contents are lists of different length that the user wants at their own
  height (`/raw`'s two origins: `items-start`).
- A group of blocks inside a section may carry a **title on the ground**: `text-heading`,
  its sentence under it, its action on the right, **16 px** above its first block.
- An **empty** block or list says so in **one sentence** (`text-small text-muted-foreground`)
  where the content would be. No well, no dashed frame. `EmptyState` (dashed) is only for a
  whole tab or screen with nothing in it yet.
- A notice inside a block is `Alert` with its tone.

## 4. Tables and lists of rows

### 4.1 Tables (`src/components/ui/table.tsx`)

```tsx
<Card className="p-5">
  <Table minWidth="0">
    <THead><tr><TH>Nombre</TH><TH align="num">Total</TH><TH className="w-28" /></tr></THead>
    <TBody>{rows.map((r) => <TR key={r.id} className="group h-11">…</TR>)}</TBody>
  </Table>
</Card>
```

- A table sits **flat in a block with the block's 20 px padding**. `Table` reaches 12 px into
  that padding, so the first column's text starts where the block's title does. Never wrap a
  table in a `.well`, a bordered div, or `-mx-*` of your own.
- Head: `TH` captions (micro, uppercase) with the inset rule. Numbers `align="num"`.
- Rows: one-line rows `h-11` (44 px). Multi-line rows grow; their cells `align-top`.
- A row that unfolds something under it is `joined` (no rule) and the unfolded row holds a
  `.well` (`TD colSpan … pb-3 pt-0` → `div.well p-3/p-4`).
- **Ticking rows**: the select-all `Checkbox` is the head's first cell (`TH w-10 pr-0`); when
  something is ticked, `TableBulk` takes the place of the next caption's text, in its cell:
  the count on that caption's line and in its face, and the bulk gestures (`size="sm"
  className="-my-1.5 h-7"`) at the row's end, so nothing moves. The other captions keep their
  cells (`THead` hides their text): never replace them with one cell spanning their columns,
  since the columns take their widths from them.
- A name column that must take the free width: `TH className="w-full"`, its `TD` `max-w-0`
  with a `truncate` inside; or `table-fixed` with fixed widths on the other columns.
- Markdown tables inside model-written content are content, not data tables: leave them.

### 4.2 Lists without columns (`.rows`)

- `<ul className="rows">` in a block: rows parted by a rule; the first and last rows lie on
  the block's padding.
- **The list sets its density, never its rows.** Do not put `py-*` on a `.rows` child.
  Densities: default (14 px), `rows-tight` (8 px, one line of text a row), `rows-flush`
  (0, where each row is a control that pads itself — a row that opens, a box that ticks).
- A list that **scrolls** inside its block is a `.well` (`well thin-scroll max-h-… overflow-y-auto px-2 py-1 rows rows-flush`).
- A long list that does not need to scroll shows its first rows and «Ver los N restantes».

### 4.3 People

- One way everywhere: **name first** (`font-medium`), **username after** in the code face,
  muted, then the badges — `PersonName` (`src/components/ui/person.tsx`).
- Lists of people in «Clase» use `PeopleTable` / `PersonRow` (`features/class/PersonRow.tsx`).

### 4.4 Row gestures

```tsx
<TD className="py-1.5">
  <RowGestures always={<Button size="sm" variant="ghost" className="h-7">Gestionar</Button>}>
    <RowAction label="Quitar a Ana" title="Quitar" icon={<UserMinus />} onClick={…} danger />
  </RowGestures>
</TD>
```

- Gestures are **28 px icon buttons** (`RowAction`, always with an `aria-label` naming the
  row and a `title`) at the row's end, in a column of fixed width.
- They show on **hover or focus** (`RowGestures`; the row needs `className="group"`), and
  keep their room when hidden so columns never move.
- The gesture that **opens** something — «Gestionar», «Ver N ejercicios», the
  conversations, copying where copying is the list's job — goes in `always`, visible.
- A gesture that a row does not offer keeps its place (`invisible`), so the gestures of
  every row line up.
- Destructive gestures: `danger` (red on hover) and a `useConfirm` question first.

## 5. Lists of sections (`src/features/admin/Sections.tsx`)

- Every tab or screen made of parts is `Sections`: the list of sections beside the section
  open, under `SectionHeader`.
- **Every row**: a **16 px mark**, the **name**, **one line of detail** (a count or a state in
  a word). The mark is a lucide icon at `size-4`; where the list is an **order** (the
  steps, the units) it is `NumberMark`. Never a coloured square, never no mark.
- The detail line is drawn even while it loads (pass `undefined`, the row keeps 64 px).
  Colour it only when it calls for somebody (`text-attention`, `text-destructive`).
- Groups: `group` caption on the first row of a kind; `separated` for a row of another
  weight; `pending` for unsaved changes.
- A search over the list goes in `before`, as `SearchInput`.
- `SectionHeader`: title (`font-display font-expanded text-title`), optional `hint`, the
  section's one `action` on the title's line (the line is 36 px tall either way), and the
  `description` under both, across the whole width.

## 6. Controls

### 6.1 Heights on a line

| Where | Height | How |
|---|---|---|
| a toolbar (search, filters, export, a form line) | **36 px** | `Input`, `Select`, `SearchInput`, `Button` default size, `ChoicePill`, `size="icon"` |
| a row of a table or list, a card's action line | **28 px** | `RowAction` (`icon-sm`), `Button size="sm" className="h-7"` |
| a caption row over a list (the graph's) | 32 px | `SearchInput compact`, `Button size="sm"` |

Never mix heights on one line. Labels over a line of controls (`Label`) sit at one height
because the controls do.

### 6.2 Fields

- Every field has a label: `<Label htmlFor>` + id, or `aria-label` (`check:ui` enforces it).
- Search is **always** `SearchInput` (magnifier inside, `type="search"`).
- Shortcuts beside a field (dates: «En 1 día»…) are `Button variant="outline"` at the
  field's height, `gap-2`.
- A reset beside a field is `size="icon"` (36 px), `ghost`.

## 7. Choices and tabs

### 7.1 One of a few words → `ChoicePill` (`src/components/ui/choice.tsx`)

```tsx
<div role="radiogroup" aria-label={…} className="flex flex-wrap gap-2" {...radios.group}>
  {options.map((o) => (
    <ChoicePill key={o} {...radios.radio(o)} chosen={o === value} onClick={() => set(o)}>{label(o)}</ChoicePill>
  ))}
</div>
```

Keyboard from `useRadioGroup` (`components/ui/radio.ts`). Never a filled button for the
chosen one, never a pill without the square.

### 7.2 One of a few options that need a sentence → choice card

`className={cn(CARD_CHOICE, "flex items-start gap-3 p-3", chosen && CARD_CHOSEN)}` with
`<ChoiceMark chosen={chosen} className="mt-1.5" />` before the title. `.raised`; the chosen
one pressed in. The generate form's fixed-height cards are `CHOICE_CARD` (same base).

### 7.3 Tabs

- `Tabs` (`components/ui/tabs.tsx`) or `TabStrip` (when the tabs own panels with ids). Both
  are the **sunk pill**; never an underline.
- **One exception**: the two parts of step 3 are chosen from a block of two choice cards
  (§7.2) at the top of the step (`features/bank/BankStep.tsx`, `PartPicker`; the user's
  request, 2026-10-08), because each card says where its part stands — a state badge and a
  sentence — which a pill has no room for. They are still tabs to a screen reader.
- A count beside a tab label: a quiet figure (`nums text-small text-muted-foreground`).
- A filter over a list («Activos 4 / Desactivados 0») is `Tabs` too.

## 8. Type

Archivo only (Literata only in the tutorial). Six steps, every line a whole number of pixels:

| Class | Use |
|---|---|
| `font-display font-expanded text-display` | a screen's `h1` |
| `font-display font-expanded text-title` | a section's `h2` (`SectionHeader`) and a stage's `h1` |
| `text-heading` | a block's title, a group title on the ground |
| `text-body` | text |
| `text-small` | secondary text, descriptions, cells |
| `text-micro font-condensed uppercase text-muted-foreground` | **every** small caption: eyebrows, table heads, field labels, list captions. Nothing else is a caption (`check:ui` keeps it rare) |

- No raw Tailwind sizes (`text-xs`, `text-sm`…), no `text-[12px]`, no `tracking-wide`.
- Identifiers (usernames, slugs, setting keys, models) in `font-mono` at the size of the text
  around them, never `text-micro` (it is bold and spaced).
- Figures compared down a column: `nums`.

## 9. Icons and screen headers

- lucide icons. 16 px (`size-4`) in rows, marks and buttons (buttons size them for you);
  14 px inside `icon-sm` buttons (automatic).
- **No icon in a block's title.** Icons belong to marks of lists, buttons and doors.
- A screen header: `h1` (display), its (i) `InfoHint` if needed, and `GuideLink` to its guide
  section under it. An (i) and visible text never say the same thing.
- A stage header: kicker «Fase de construcción · Paso N de 3», the title in the display face
  at `text-title`, the lead, `GuideLink`, and `StageGate.WayOn` on the right. A step drawn in
  parts (step 3) is headed by the part on screen: «Fase de construcción · Paso 3 de 3 · Parte
  N de 2» over the part's name (`StageHeader`'s `part`).

## 10. Copy, language and behaviour that the look depends on

- Spanish is the source catalogue (`src/lib/i18n/es.ts`), English typed against it. A key
  read only by `src/evaluation/` or `src/tutor/` lives in that folder's catalogue.
- Vocabulary for teachers: «asignatura», «Temario», «Tipos de ejercicio», «Banco de
  ejercicios», «ejercicio(s) generado(s)». The app never speaks of itself in the first person.
- No time estimates anywhere. A queued job is not a running one.
- Fold, never drop; never fold the only copy of something.
- A behaviour change is not finished until its guide section says so (`features/guide/`).

## 11. Where each primitive lives

| Need | Use |
|---|---|
| block | `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardContent` (`components/ui/card.tsx`) |
| section list + header | `Sections`, `SectionHeader`, `NumberMark` (`features/admin/Sections.tsx`) |
| table | `Table`, `THead`, `TBody`, `TR` (`joined`), `TH`, `TD`, `TableBulk`, `RowGestures`, `RowAction` (`components/ui/table.tsx`) |
| person | `PersonName` (`components/ui/person.tsx`); class lists `PeopleTable`, `PersonRow` |
| links just made | `LinkTable`, `CopyLink`, `CopyButton` (`features/admin/CopyLink.tsx`) |
| fields | `Input`, `SearchInput`, `Select`, `Textarea`, `Label` (`components/ui/input.tsx`) |
| choices | `ChoicePill`, `ChoiceMark`, `CARD_CHOICE`, `CARD_CHOSEN` (`components/ui/choice.tsx`), `useRadioGroup` |
| tabs | `Tabs` (`components/ui/tabs.tsx`), `TabStrip` (`components/TabStrip.tsx`) |
| states | `Badge`, `Alert`, `EmptyState`, `LoadError`, `Skeleton`, `Spinner`, `Progress`, `Switch`, `Checkbox` (`components/ui/`) |
| dialogs | `Dialog`, `useConfirm` |
| a document beside its transcription | `DocumentReader` (`features/raw/`): two columns that scroll page to page, `OriginalPane` and `TextPane` (`features/raw/reader/`) |
| the tutor's reply and its map | `Reply` (`tutor/`): explanation, `ConceptMap` (a graph of `ConceptChip`s with lines traced over them, in a well, never Mermaid), then the question with `QuestionMark` beside it |
| ruled list | `.rows` (+ `rows-tight` / `rows-flush`) in `src/index.css` |
