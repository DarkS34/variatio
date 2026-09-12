import { Check, Play, Scale, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Alert, PhaseBar, Skeleton } from "@/components/ui/misc";
import { StatusMark } from "@/components/ui/status";
import { STATUS, type StatusKey } from "@/lib/status";
import { ARM_META } from "@/evaluation/arms";
import {
  USES,
  STEPS,
  nextStepOf,
  stepNumber,
  stepNumberOf,
} from "@/lib/steps";
import { useT, type Translate } from "@/lib/i18n";
import { useBuildPhases } from "@/state/queries";
import { Block, Detail, Facts, Paragraph, Rows, SectionHead, Steps } from "../blocks";

const STATE_ORDER: StatusKey[] = ["approved", "draft", "stale", "building", "missing", "blocked"];

const STATE_HINTS: Record<StatusKey, string> = {
  approved:
    "Cerrado y dado por bueno. Se cierra al continuar al paso siguiente; corregirlo después lo vuelve a abrir con el primer cambio que guardes.",
  draft: "Construido y todavía sin cerrar. Se puede mirar y corregir; lo que viene detrás sigue esperando.",
  stale:
    "Algo de lo que depende cambió después de construirlo o cerrarlo: el paso de arriba, o los documentos que lee. La pantalla dice qué cambió; si fueron los documentos, ofrece volver a construirlo con los que hay ahora. En cualquier caso se vuelve a cerrar continuando.",
  building:
    "La pantalla dice cuál de tres cosas pasa: se construye por primera vez y no hay nada que reemplazar; se trabaja sobre lo que ya hay, que sigue guardado y solo deja de verse; o el trabajo sigue en cola y todavía no ha empezado, y entonces no hay barra.",
  missing: "Todavía no existe. La pantalla enseña la cabecera y un único botón, grande y en el centro: comenzar la construcción.",
  blocked: "No es «no está hecho», es «no te toca todavía»: falta cerrar algo de lo que depende.",
};

const ARM_ORDER = ["naive", "rag", "system"] as const;

/**
 * The graph builder's real plan, read from the API as the panel reads it.
 *
 * The guide reads the application's own sources rather than repeating them, so there is no
 * hand-written fallback here either: with no plan, a skeleton. A copy kept by hand falls
 * behind — drawing a phase at 10 % when it weighs a third, or omitting one altogether.
 */
function BuildPlanBar() {
  const phases = useBuildPhases("knowledge_graph");
  if (!phases.length) return <Skeleton className="h-1.5 w-full" />;
  return <PhaseBar phases={phases} percent={58} activeKey="clean" />;
}

/**
 * One of the two doors of the testing phase, drawn as the bar draws it: an icon and no
 * number, because the two have no order between them.
 */
function Pill({
  icon: Icon,
  label,
  tone,
}: {
  icon: LucideIcon;
  label: string;
  tone?: "evaluation";
}) {
  return (
    <span
      className={
        tone === "evaluation"
          ? "flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-small font-medium text-evaluation ring-1 ring-inset ring-[color-mix(in_oklch,var(--evaluation)_30%,transparent)] bg-[color-mix(in_oklch,var(--evaluation)_9%,transparent)]"
          : "flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-small font-medium"
      }
    >
      <Icon className="size-4" />
      {label}
    </span>
  );
}

function Start() {
  const tr = useT();
  const { t } = tr;
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.start")} title={t("guide.sec.start")}>
        <p>
          <strong>Variatio</strong> genera <strong>ejercicios de aprendizaje</strong> —ejercicios,
          problemas, tareas de evaluación— anclados al temario de una asignatura. No escribe sobre un concepto
          en abstracto: parte de los cuatro pasos con los que describes tu asignatura y produce ejercicios
          que respetan lo que el alumno ya ha visto y lo que todavía no.
        </p>
      </SectionHead>

      <Block title="El recorrido, de un vistazo">
        {/* The bar above, drawn here: the steps come from `STEPS` and the two doors from
            `USES`, so this figure cannot promise an order the navigation does not have. */}
        <div className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-card p-4 sm:p-6">
          <div className="space-y-1.5">
            <p className="font-condensed text-micro uppercase text-muted-foreground">
              {t("nav.phase.build")}
            </p>
            <div className="flex flex-wrap items-center gap-3">
              {STEPS.map((step, index) => (
                <div key={step.path} className="flex items-center gap-2">
                  <span className="nums flex h-6 min-w-6 shrink-0 items-center justify-center bg-primary px-1 font-condensed text-small font-semibold text-primary-foreground">
                    {stepNumber(index)}
                  </span>
                  <span className="text-body font-medium">{t(step.labelKey)}</span>
                </div>
              ))}
            </div>
          </div>
          <span aria-hidden className="mx-1 h-6 w-px bg-border" />
          <div className="space-y-1.5">
            <p className="font-condensed text-micro uppercase text-muted-foreground">
              {t("nav.phase.test")}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              {USES.map((door) => (
                <Pill
                  key={door.key}
                  icon={door.key === "generate" ? Play : Scale}
                  label={t(door.labelKey)}
                  tone={door.evaluation ? "evaluation" : undefined}
                />
              ))}
            </div>
          </div>
        </div>
        <Paragraph>
          Es exactamente la barra de arriba, y son dos fases con nombre. La{" "}
          <strong>{t("nav.phase.build").toLowerCase()}</strong> son cuatro pasos numerados{" "}
          <strong>{stepNumber(0)}</strong> a <strong>{stepNumber(3)}</strong> porque son un solo
          trabajo, <em>preparar la asignatura</em>, y se hacen en ese orden: cada uno necesita
          el anterior cerrado. Cada uno lleva debajo una palabra diciendo dónde estás:{" "}
          <em>{t("nav.state.done")}</em>, <em>{t("nav.state.now").toLowerCase()}</em> o{" "}
          <em>{t("nav.state.later").toLowerCase()}</em>. Cuando los cuatro están hechos, la
          fase se pliega en una sola píldora que dice «{t("nav.build.folded")}»: pulsarla
          vuelve a mostrar los pasos, y el navegador lo recuerda.
        </Paragraph>
        <Paragraph>
          La <strong>{t("nav.phase.test").toLowerCase()}</strong> son dos cosas que puedes
          hacer con la asignatura construida, y por eso no llevan número: ninguna va antes que
          la otra y ninguna necesita a la otra. Las dos se encienden a la vez, cuando la
          construcción está cerrada; hasta entonces están medio apagadas, dicen «
          {t("nav.state.later").toLowerCase()}» y no responden al pulsarlas.
          «{t("nav.create")}» es aquello para lo que existe la construcción. «{t("nav.compare")}»
          va aparte en color: no produce material para tu asignatura, sirve para medir el
          sistema.
        </Paragraph>
      </Block>

      <Rows
        items={[
          {
            key: "perfil",
            head: `${stepNumberOf("exemplars_profile")} · ${t("artifact.profile")}`,
            body: "Qué formas tienen tus ejercicios: qué partes lleva cada tipo, cuál es su nivel de dificultad y cómo se redactan.",
          },
          {
            key: "temario",
            head: `${stepNumberOf("knowledge_graph")} · ${t("artifact.graph")}`,
            body: "El temario de la asignatura: sus conceptos, agrupados en unidades y unidos por lo que hace falta saber antes de cada cosa.",
          },
          {
            key: "banco",
            head: `${stepNumberOf("exemplars_bank")} · ${t("artifact.bank")}`,
            body: "Tus ejercicios recogidos uno a uno de los documentos, con los conceptos del temario que practica cada uno.",
          },
        ]}
      />

      <Alert tone="info" title="Los tipos de ejercicio van antes que el temario">
        <p>
          Un temario se puede construir sin nada más, pero la revisión de qué conceptos sirven de
          etiqueta necesita los <em>tipos de ejercicio ya cerrados</em>: se juzga contra las
          formas de ejercicio que pones tú. Por eso el Paso{" "}
          {stepNumberOf("exemplars_profile")} va delante del{" "}
          {stepNumberOf("knowledge_graph")}, y no al revés.
        </p>
      </Alert>

      <Block title="Cómo se empieza">
        <Steps
          items={[
            <>
              Ponte en una <strong>asignatura</strong>. Si aún no tienes ninguna, se te
              ofrece crear la tuya nada más entrar; si tienes varias, se cambia en el selector
              de arriba a la izquierda. Todo lo demás vive dentro de una.
            </>,
            <>
              <strong>Paso {stepNumber(0)}</strong> — en «{t("nav.step.raw")}» sube los apuntes
              de la asignatura y los ejercicios que ya tienes. Con un par de temas basta: cada
              documento se lee entero, así que cuanto más subas, más se tarda.
            </>,
            <>
              En esa misma pantalla, «{t("transcribe.startAll")}» adelanta la lectura de los
              documentos. No es obligatoria —si no la haces, cada construcción lee lo suyo por
              el camino—, pero es el trabajo mecánico que abre los tres pasos siguientes. Y es
              donde puedes leer y corregir a mano una página que haya salido mal.
            </>,
            <>
              <strong>Paso {stepNumber(1)}</strong> — construye los{" "}
              <strong>{t("nav.step.profile").toLowerCase()}</strong>, míralos, corrige lo que no
              encaje y continúa.
            </>,
            <>
              <strong>Paso {stepNumber(2)}</strong> — lanza <strong>el temario</strong>. Es el
              trabajo más caro del recorrido: puedes cerrar la pestaña, el servidor sigue. Al
              terminar encadena por su cuenta las descripciones de cada concepto y la revisión de
              cuáles sirven de etiqueta.
            </>,
            <>
              <strong>Paso {stepNumber(3)}</strong> — recoge tus ejercicios y repasa el{" "}
              <strong>{t("nav.step.bank").toLowerCase()}</strong>: si el concepto que se le ha
              puesto a cada uno es el que de verdad practica.
            </>,
            <>
              Con los cuatro cerrados se abren «{t("nav.create")}» y «{t("nav.compare")}».
            </>,
          ]}
        />
      </Block>

      <Block title="Cada pantalla trae aquí su propia página">
        <Paragraph>
          Bajo el título de las pantallas importantes hay un enlace «{t("guide.linkTo", {
            section: t("guide.sec.graph"),
          })}» que abre exactamente la sección que las explica. No hace falta acordarse de
          cómo se llama: se lee desde donde estabas y se vuelve con el botón de atrás.
        </Paragraph>
      </Block>

      <Detail title="¿Qué quiere decir «cerrar» un paso?">
        <p>
          No hay ningún botón que se llame «aprobar». Un paso se cierra{" "}
          <strong>al continuar al siguiente</strong>: el botón «
          {t("stage.continue", { n: stepNumber(2) })}» del final de la pantalla guarda primero
          lo que tengas sin guardar y da por bueno lo que hay. Si esa escritura se rechaza, no
          se cierra nada y no se avanza.
        </p>
        <p>
          Cerrar un paso es lo que desbloquea el siguiente, y cerrar los tres que construyen
          algo es lo que abre «{t("nav.create")}». Lo que se da por bueno es el fichero{" "}
          <em>tal como está</em>, así que un paso cerrado se abre en modo lectura como
          cualquier otro. Corregirlo no necesita ningún botón aparte: «
          {t("stage.curate.start")}» lo desbloquea igual, y el primer cambio que guardes lo
          vuelve a abrir — habrá que cerrarlo otra vez continuando.
        </p>
        <p>
          Lo que <em>no</em> forma parte de ese fichero —la descripción de cada concepto— se puede
          seguir corrigiendo con el paso cerrado, porque vive aparte y no caduca nada.
        </p>
      </Detail>
    </div>
  );
}

function Workspace() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.start")} title={t("guide.sec.workspace")}>
        <p>
          Una <strong>asignatura</strong> se prepara entera y por separado: sus documentos, los
          cuatro pasos del recorrido y todo lo que se ha generado con ella. Nada cruza de una a
          otra. Si una misma asignatura se da con dos formatos de ejercicio muy distintos, también
          son dos.
        </p>
      </SectionHead>

      <Facts
        items={[
          { label: "Dónde se cambia", value: "El selector de arriba a la izquierda, junto a la marca." },
          { label: "Quién puede crear una", value: "Cualquier cuenta, y queda como su propietaria." },
          { label: "Si no tienes ninguna", value: "Se te ofrece crearla nada más entrar. No hay ninguna por defecto." },
          { label: "Qué se lleva al cambiar", value: "Nada. Cada asignatura tiene lo suyo, incluida su caché." },
          {
            label: "Qué se decide al crearla",
            value: "El idioma de los prompts. Después ya no se puede cambiar.",
          },
        ]}
      />

      <Block title="Entrar sin ninguna es normal">
        <Paragraph>
          No hay una asignatura inicial en la que caiga quien no tiene otra: una cuenta recién
          creada, o a la que todavía no le han dado acceso a nada, entra y se encuentra la
          oferta de crear la suya. Basta con su nombre. Las dos salidas son igual de válidas:
          créala tú y serás su propietario, o espera a que quien administra te dé acceso a una
          que ya existe.
        </Paragraph>
        <Paragraph>
          Mientras tanto la aplicación no se queda bloqueada: esta guía, «{t("account.title")}» y
          —si administras la instalación— «{t("admin.title")}» funcionan sin ninguna
          asignatura. Lo que espera es todo lo que lee una instancia: los cuatro pasos, «
          {t("nav.create")}» y «{t("nav.compare")}».
        </Paragraph>
      </Block>

      <Block title="El idioma de los prompts se elige al crear la asignatura">
        <Paragraph>
          Al crear una asignatura eliges en qué idioma se le habla al modelo durante toda la
          construcción de esa instancia. <strong>No se puede cambiar después</strong>, y no es
          una restricción caprichosa: las etiquetas de las relaciones se escriben dentro del
          propio grafo y el cargador indexa por ellas, así que el idioma queda cocido en los
          artefactos desde la primera construcción. El formulario de creación lo dice ahí
          mismo.
        </Paragraph>
        <Paragraph>
          No tiene por qué coincidir con el idioma en el que tú lees la aplicación: preparar
          en español una instancia cuyos prompts van en inglés es un caso previsto, y es
          justo para eso que son dos ajustes distintos.
        </Paragraph>
      </Block>

      <Block title="Una pestaña, una asignatura">
        <Paragraph>
          La asignatura activa se guarda en tu cuenta y sobrevive a cerrar sesión; la que estás{" "}
          <em>mirando</em> la guarda la pestaña. Puedes tener dos asignaturas abiertas en dos
          pestañas del mismo navegador sin que se pisen. Al cambiar de asignatura la pantalla se
          vacía de lo que estabas viendo: los trabajos y el progreso pertenecen a la instancia
          que dejas.
        </Paragraph>
      </Block>

      <Block title="El contexto de la asignatura">
        <Paragraph>
          Es la prosa que dice de qué va esta instancia —materia, nivel, idioma de instrucción,
          convenciones— y entra en <em>todas</em> las llamadas al modelo. No se escribe a mano:
          lo sintetizan la construcción del temario y la de los tipos de ejercicio, cada una con
          lo que sabe de la asignatura. Se lee en «{t("account.title")} → {t("tabs.workspaces")}»,
          debajo de cada una, con los tres datos sueltos que van al lado del
          párrafo — {t("context.fact.subject").toLowerCase()},{" "}
          {t("context.fact.level").toLowerCase()} e {t("context.fact.language").toLowerCase()}—,
          que se leen por separado y dicen lo mismo que él.
        </Paragraph>
        <Alert tone="info" title={`«${t("context.draft")}» frente a «${t("context.curated")}»`}>
          <p>
            El distintivo dice de dónde sale el texto que estás leyendo: «{t("context.curated")}»
            si alguien lo escribió en su día, «{t("context.draft")}» si es la síntesis de la
            última construcción. Cada construcción escribe un borrador nuevo sin tocar lo que ya
            hay, así que lo que se escribió a mano nunca se sobreescribe solo.
          </p>
        </Alert>
      </Block>

      <Block title="Lo que ya has dado en clase">
        <Paragraph>
          Al pedir un ejercicio puedes decir hasta dónde ha llegado la clase. Es lo que acota
          el andamiaje: en un concepto ya dado el ejercicio puede apoyarse; de uno que aún no se ha
          visto, no puede depender. Se elige <em>en el propio encargo</em>, en la misma pregunta
          en la que eliges qué practicar y justo encima de ella, y vale para esa tanda — no se
          guarda en la asignatura.
        </Paragraph>
        <Paragraph>
          Marcar un concepto marca también todo lo que va antes de él: en el selector esos
          prerrequisitos aparecen señalados, cuentan como dados y no hace falta buscarlos uno a
          uno. Es la misma señal que ves al elegir qué practicar.
        </Paragraph>
        <Alert tone="info" title="Sin marcar nada no significa «nada impartido»">
          <p>
            Nadie ha dicho hasta dónde ha llegado la clase, así que lo que va después de lo
            pedido no está prohibido: el ejercicio puede apoyarse en ello como andamiaje, y lo
            único que se le exige es que practique lo que elegiste y no algo posterior. Con el
            currículo marcado, en cambio, lo que queda fuera de él sí está prohibido, y basta
            con que aparezca para que el sistema pida otro intento.
          </p>
        </Alert>
      </Block>

    </div>
  );
}

function Raw() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.prepare")} title={t("guide.sec.raw")}>
        <p>
          Los documentos de los que sale todo lo demás, y el primer paso del recorrido —{" "}
          <strong>«{t("nav.step.raw")}»</strong> en la barra de arriba,{" "}
          <code className="font-mono text-small">/raw</code>. Es el único sitio en el que hace
          falta que busques archivos en tu equipo: los otros tres pasos trabajan sobre lo que
          dejes aquí.
        </p>
        <p>
          <strong>Con un par de temas basta.</strong> Cada documento se lee entero, así que
          cuanto más subas más se tarda, y para ver si esto sirve para tu asignatura no hace
          falta el curso completo.
        </p>
      </SectionHead>

      <Facts
        items={[
          {
            label: "Qué se hace aquí",
            value: "Subir tus documentos, y opcionalmente adelantar su lectura y corregir a mano lo que salga mal.",
          },
          {
            label: "Qué cuesta leerlos",
            value: "Una llamada al modelo por página, en los dos orígenes por igual.",
          },
          {
            label: "Cuándo está hecho",
            value: "En cuanto los dos orígenes tienen documentos. Leerlos no es un requisito.",
          },
        ]}
      />

      <Block title="Los dos orígenes">
        <Rows
          items={[
            {
              key: "corpus",
              head: t("raw.slot.corpus"),
              body: t("raw.slot.corpus.purpose"),
            },
            {
              key: "exemplars",
              head: t("raw.slot.exemplars"),
              body: t("raw.slot.exemplars.purpose"),
            },
          ]}
        />
        <Paragraph>
          Bajo el título de cada tarjeta va esa misma frase, diciendo qué hay que soltar ahí y
          para qué se usa. Un origen vacío no dibuja una lista vacía: la tarjeta entera se
          convierte en la zona donde soltar los ficheros, que es lo único que hay que hacer ahí.
        </Paragraph>
        <Paragraph>
          Una vez hay documentos, cada uno es <strong>una fila</strong>: su nombre, cómo va su
          lectura y los dos botones que actúan sobre él —abrirlo para corregir sus páginas, o
          quitarlo del origen—.
        </Paragraph>
      </Block>

      <Alert tone="info" title="Leerlos ahora adelanta trabajo; nunca es un requisito">
        <p>
          Pasar los documentos a texto es lo primero que hace <em>cada</em> construcción, y es
          trabajo mecánico: hacerlo aquí una vez lo saca del principio de los tres pasos
          siguientes. Si construyes sin haberlos leído, la construcción lo hace por su cuenta y
          nadie te lo impide — <strong>nada se rechaza jamás por falta de lectura</strong>.
        </p>
        <p>
          Por eso, mientras queden documentos sin leer, el propio paso «{t("nav.step.raw")}» de
          la barra de arriba lo dice al pasar el cursor, y lo dice contando: cuántos quedan y
          que puedes construir igualmente. Es una indicación de por dónde empezar, no un
          candado.
        </p>
      </Alert>

      <Block title="Un solo botón, y lo lanza todo">
        <Paragraph>
          «{t("transcribe.startAll")}» está en el bloque de arriba de la pantalla —el mismo
          bloque, con el mismo botón grande, con el que arranca cada paso— y es el único que
          hay: lanza de una vez los orígenes que tengan algo que hacer. Por dentro son{" "}
          <strong>dos trabajos</strong>, uno por origen, así que en la cola se ven dos y hay que
          detener los dos si te arrepientes.
        </Paragraph>
      </Block>

      <Block title="Un documento que ya se ha leído aquí llega leído">
        <Paragraph>
          Un documento se identifica por su contenido, no por su nombre ni por la asignatura en
          la que esté. Si subes uno que esta instalación ya ha leído —el mismo boletín en dos
          asignaturas, o el mismo fichero otra vez con otro nombre—, sus páginas se copian en el
          momento de subirlo y la fila aparece ya al día, sin gastar ni una llamada al modelo.
        </Paragraph>
        <Paragraph>
          Solo ocurre cuando coincide todo: el contenido del fichero y los ajustes con los que se
          leyó. Si algo de eso ha cambiado desde entonces, el documento sale «{"pendiente"}» y se
          lee como cualquier otro. Las páginas se <strong>copian</strong>, así que corregir una
          aquí no toca la de la otra asignatura.
        </Paragraph>
      </Block>

      <Block title="Cómo va cada documento">
        <Rows
          items={[
            {
              key: "done",
              head: (
                <span className="flex items-center gap-1.5 text-small text-muted-foreground">
                  <Check aria-hidden className="size-4 text-settled" />
                  {t("transcribe.state.done")}
                </span>
              ),
              body: "Sus páginas están escritas y siguen valiendo. Las construcciones las reutilizan tal cual, sin volver a preguntarle al modelo.",
            },
            {
              key: "pending",
              head: <Badge variant="outline">{t("transcribe.state.pending")}</Badge>,
              body: "Todavía no se ha leído. No es un problema: si tú no lo lees antes, lo leerá la construcción.",
            },
            {
              key: "stale",
              head: <Badge variant="attention">{t("transcribe.state.stale")}</Badge>,
              body: "Se leyó, pero algo de lo que dependía ha cambiado. La fila dice qué: el propio documento, la ruta de lectura, el modelo, la resolución de render, el OCR o el prompt.",
            },
            {
              key: "failed",
              head: <Badge variant="danger">{t("transcribe.failedCount", { n: "N" })}</Badge>,
              body: "Va junto al estado, no en su lugar: un documento puede estar leído y al día y aun así tener páginas que el modelo no supo descifrar. Ese distintivo es el único aviso de que ahí falta texto, y se arregla abriendo el documento.",
            },
          ]}
        />
        <Paragraph>
          El motivo va en la fila del documento y no escondido en un recuento: «2 hay que releerlos» dice
          el estado y se calla justo la mitad sobre la que se actúa. Un estado sin motivo no es
          un estado, y lo que hay debajo es una lista de páginas que la siguiente construcción
          iba a rehacer en silencio.
        </Paragraph>
        <Paragraph>
          Cuando un origen queda al día, su tarjeta entera se tiñe del azul de su marca y el
          tick pasa a ser un círculo relleno. Y cuando los dos lo están, al final de la
          pantalla aparece el mismo bloque con el que se cierra cada paso: «
          {t("stage.continue", { n: stepNumber(1) })}».
        </Paragraph>
      </Block>

      <Alert tone="settled" title="Detenerla no pierde nada">
        <p>
          Las páginas se escriben documento a documento, así que una lectura cancelada
          conserva todo lo que ya había salido y al relanzarla sigue por donde iba. El botón lo
          dice ahí mismo, porque uno que pudiera estar tirando trabajo a la basura es un botón
          que nadie pulsa.
        </p>
      </Alert>

      <Block title="Corregir una página a mano">
        <Steps
          items={[
            <>
              Pasa el cursor por la fila del documento y pulsa el lápiz. Se abre con el índice de
              páginas a la izquierda y el markdown de la que elijas a la derecha.
            </>,
            <>
              Edita y guarda. También puedes <strong>insertar</strong> una página en blanco
              justo después de la que estás viendo, o <strong>borrarla</strong>: las dos cosas
              renumeran las siguientes, y la pantalla lo dice antes de hacerlo.
            </>,
            <>
              Salir con cambios sin guardar pregunta antes de descartarlos, igual que cambiar de
              página.
            </>,
          ]}
        />
        <Paragraph>
          De las páginas solo se señalan dos, que son las únicas que necesitan a una persona:
        </Paragraph>
        <Rows
          items={[
            {
              key: "failed",
              head: <Badge variant="danger">{t("doc.mark.failed")}</Badge>,
              body: t("doc.failedPage"),
            },
            {
              key: "empty",
              head: <Badge variant="attention">{t("doc.mark.empty")}</Badge>,
              body: t("doc.emptyPage"),
            },
          ]}
        />
        <Detail title="Por qué gana lo que corriges a mano">
          <p>
            Las construcciones siguientes leen estas páginas del disco en lugar de volver a
            preguntarle al modelo, así que una corrección tuya{" "}
            <strong>gana sobre lo que dijo el modelo y sobrevive a todas las construcciones que
            vengan</strong>. Editar tampoco marca el documento como caducado: lo único que se
            descarta son las dos costuras que rodean la página que has tocado, porque se
            decidieron sobre un texto que ya no está.
          </p>
          <p>
            No se puede borrar la última página que queda. Un documento con cero páginas se lee
            como «{t("transcribe.state.pending")}», y la siguiente construcción reharía en
            silencio todo lo corregido.
          </p>
          <p>
            Mientras un origen se lee puedes revisar y corregir los documentos que ya han
            salido. El único que no se deja abrir es el que se está reescribiendo en ese
            instante: su fila lo dice con un indicador de actividad y con «
            {t("transcribe.transcribing")}» en lugar de su estado.
          </p>
        </Detail>
      </Block>

      <Detail title="Los dos orígenes van por la misma ruta, y cuesta lo que cuesta">
        <p>
          Apuntes y ejercicios se leen con el mismo algoritmo: se dibuja cada página y se
          le pide al modelo que la copie carácter a carácter, sin completar y sin corregir. Una
          llamada por página, sin excepciones, porque la imagen de la página es la fuente
          honesta — una tabla partida en dos hojas, un bloque de código con su sangría o una
          fórmula sobreviven así y no de otra manera.
        </p>
        <p>
          A cada unión entre dos páginas le sigue una segunda llamada, mucho más corta, que
          decide solo <em>cómo</em> se pegan: si la frase continúa, qué separador va en medio y
          cuántas líneas de cabecera repetida hay que tirar. No reescribe nada — de eso depende
          que el «copia carácter a carácter» siga valiendo. Por eso la barra de progreso avanza
          primero por páginas y después por costuras dentro del mismo documento.
        </p>
        <p>
          Un archivo de Word o de PowerPoint no tiene página que dibujar: declara su propia
          estructura y se lee como texto directamente, en segundos. Lo que ese camino no ve son
          las <em>imágenes</em> — y en un cuaderno de ejercicios ahí suelen estar las fórmulas
          y la «salida esperada» de un programa —, así que cada imagen se le enseña al modelo por
          separado, con las mismas reglas que una figura en una página: una fórmula vuelve como
          fórmula, una captura de código como código, y solo lo que no se puede copiar se anota
          como figura. Cada imagen se recuerda por su contenido, de modo que el logotipo que se
          repite en todos los documentos se lee una sola vez. Una imagen en un formato que no se
          puede abrir (los metarchivos WMF y EMF de Office, si la instalación no tiene
          LibreOffice) deja una marca visible en su sitio y una insignia en la fila del documento.
        </p>
        <p>
          La consecuencia se ve en la barra por fases que se explica en «
          {t("guide.sec.runs")}»: la lectura de los apuntes es hoy el tramo más ancho de la
          construcción del temario. Sacarla de ahí, y poder mirarla mientras tanto, es exactamente
          para lo que existe esta pantalla.
        </p>
      </Detail>
    </div>
  );
}

/**
 * How each of the three building steps ends. The same block in all three sections because
 * it is the same task: the only difference is the questions, which the server writes.
 */
function Verdict({ artifact }: { artifact: string }) {
  const { t } = useT();
  const next = nextStepOf(artifact);
  return (
    <Block title="Cómo se cierra este paso">
      <Paragraph>
        El paso se abre <strong>en modo lectura</strong>: se mira, no se toca. Ver y corregir
        son dos cosas distintas, y por eso están en dos momentos distintos. Al final de la
        pantalla, y no al entrar, hay tres cosas seguidas: la valoración, la oferta de
        corregir y el paso siguiente.
      </Paragraph>
      <Steps
        items={[
          <>
            <strong>Mira lo que hay arriba.</strong> No hace falta leerlo entero: lo que se
            pregunta después es si te suena a tu asignatura.
          </>,
          <>
            <strong>«{t("stageReview.openTitle")}»</strong>, el botón del final, despliega
            debajo un cuestionario corto: cinco afirmaciones, y para cada una dices cuánto
            estás de acuerdo, del 1 («totalmente en desacuerdo») al 5 («totalmente de
            acuerdo»). Son las mismas cinco ideas en los tres pasos. Puedes dejarlo a medias
            y volver, porque media respuesta también es un dato, y en cuanto guardas puedes
            cerrarlo sin perder nada. Está ahí aunque el paso anterior se haya vuelto a
            abrir: lo que se valora es lo que hay construido.
          </>,
          <>
            <strong>«{t("stage.curate.start")}»</strong> desbloquea la edición de lo que hay
            arriba. Mientras corriges, una barra fija al borde de abajo dice cómo van los
            cambios y lleva «{t("stage.curate.save")}» y «{t("stage.curate.stop")}».
          </>,
          <>
            <strong>
              «
              {next.number === null
                ? t("stage.continueGenerate")
                : t("stage.continue", { n: next.number })}
              »
            </strong>{" "}
            cierra el paso y te lleva a lo que viene después. Antes de cerrarlo guarda lo que tuvieras
            pendiente, y si esa escritura se rechaza no cierra ni avanza: te lo dice y te
            deja donde estabas.
          </>,
        ]}
      />
      <Paragraph>
        Corregir es opcional y valorar también: puedes continuar sin haber hecho ninguna de
        las dos. Lo que no se puede es avanzar sin cerrar, porque el paso siguiente necesita
        que este esté dado por bueno.
      </Paragraph>
      <Detail title="Qué se guarda exactamente">
        <p>
          Tus respuestas, con la <em>versión concreta</em> que juzgaste. Si vuelves a
          construir el paso y lo valoras otra vez, no se sobrescribe: son dos datos, porque
          «salió mal» y «lo rehíce y salió bien» son dos cosas distintas. Volver a contestar
          sobre lo mismo sí corrige tu respuesta anterior.
        </p>
        <p>
          Se guarda también <strong>si corregiste antes de valorar</strong>. No es
          vigilancia: es una variable del estudio, porque no es lo mismo la nota de quien ha
          curado el resultado a mano que la de quien lo juzga tal como salió, y sin
          distinguirlas las dos se mezclan en el mismo promedio.
        </p>
        <p>
          Son cinco afirmaciones en cada paso, todas sobre la misma escala de acuerdo, y
          siguen el mismo orden en los tres: que todo lo que hay es tuyo, que no falta nada,
          que lo que ese paso tiene que hacer lo hace —las partes de cada tipo, el orden del
          temario, el concepto de cada ejercicio—, que lo podrías usar tal cual, y que en
          conjunto ha salido bien. Están redactadas para que estar de acuerdo sea siempre la
          buena noticia, así que el número es la nota: 5 es lo mejor. Las dos últimas son
          idénticas en los tres, y son las que permiten comparar un paso con otro. Al final
          hay una caja opcional para lo que no quepa en la escala.
        </p>
        <p>
          Es lo único que se te pide a cambio de usar esto, y es lo que se está midiendo:
          sin ello no hay forma de saber si el sistema prepara bien una asignatura o solo lo
          parece.
        </p>
      </Detail>
    </Block>
  );
}

function Profile() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.prepare")} title={t("guide.sec.profile")}>
        <p>
          Qué formas tienen los ejercicios que pones tú: una pregunta con opciones, un encargo
          de escribir código, un fallo que corregir. De cada forma se anota qué partes lleva,
          cómo se redacta y qué la hace más o menos difícil. Es la plantilla con la que se
          escriben los ejercicios nuevos.
        </p>
      </SectionHead>

      <Facts
        items={[
          {
            label: "De dónde sale",
            value: `De los documentos que dejaste en «${t("raw.slot.exemplars")}», leyendo una muestra.`,
          },
          { label: "Qué cuesta", value: "Una pasada larga sobre una muestra de tus ejercicios, no sobre todos." },
          {
            label: "Qué desbloquea",
            value: "Recoger tus ejercicios, y decidir qué conceptos del temario sirven de etiqueta.",
          },
        ]}
      />

      <Block title="Cómo se hace">
        <Steps
          items={[
            <>
              En el Paso {stepNumber(0)} sube a «{t("raw.slot.exemplars")}» uno o varios
              documentos con ejercicios reales de la asignatura. Sin material, el botón de
              construir está apagado y dice por qué.
            </>,
            <>
              Pulsa «{t("build.start")}», el botón grande del centro de la pantalla. Sale una{" "}
              <strong>primera versión</strong>, no un resultado final, y no se ofrece
              reconstruirla: una segunda pasada sobre los mismos documentos no da otra cosa.
            </>,
            <>
              Lee cada <strong>tipo de ejercicio</strong> —la tira de arriba los elige uno a
              uno—: qué es, cuándo un ejercicio suyo es básico, intermedio o avanzado, y las
              <strong> «{t("modality.rules")}»</strong>, que son lo único que se le dice al
              modelo sobre la <em>forma</em> del ejercicio.
            </>,
            <>
              Si algo no encaja, «{t("stage.curate.start")}» al final de la pantalla desbloquea
              la edición. Solo entonces aparecen «{t("modality.add")}» y las partes de cada
              tipo, que es la pregunta más técnica de todo el recorrido y no la que se hace al
              entrar.
            </>,
            <>
              Valora el paso y continúa. Al continuar, lo que tengas sin guardar se guarda y el
              paso se cierra.
            </>,
          ]}
        />
        <Paragraph>
          No hay una pestaña con el fichero en crudo. Lo que escribe los cambios es «
          {t("stage.curate.save")}», en la barra fija de abajo, y también «continuar». Esa
          misma barra dice si hay algo sin guardar y, cuando el fichero no <em>carga</em>, la
          frase del validador — mientras no cargue no se puede guardar, que es lo que impide
          dejar la asignatura con una plantilla rota.
        </Paragraph>
      </Block>

      <Block title="Los tipos de ejercicio, y por qué se notan en todas partes">
        <Paragraph>{t("modality.whatAre.body")}</Paragraph>
        <Paragraph>
          Por eso el tipo de ejercicio reaparece luego como columna y como filtro en tus
          ejercicios, y como primera pregunta al pedir uno nuevo. Con un solo tipo declarado no
          se dibuja ninguno de los dos: un desplegable de una única opción no elige nada.
        </Paragraph>
      </Block>

      <Block title="El nivel de dificultad, que lo llevan todos">
        <Paragraph>
          Todos los tipos de ejercicio llevan un <strong>nivel de dificultad</strong>, y no es
          una parte más: no se añade, no se quita y no se le cambia el nombre. Vive arriba, en
          «{t("modality.identity")}», justo debajo de la descripción del tipo — al mirar, los
          tres peldaños se ven con lo que dice el criterio de cada uno debajo; al corregir, se
          convierte en una caja de texto.
        </Paragraph>
        <Paragraph>
          Los <strong>tres niveles son los mismos en todos los tipos</strong>. Eso es lo que
          hace que «avanzado» signifique lo mismo en una pregunta de test y en un ejercicio de
          programación, y que se pueda filtrar por él una lista con tipos mezclados. Lo que
          cambia de un tipo a otro es <em>qué hace</em> que un ejercicio caiga en cada nivel, y
          eso es lo único que escribes tú.
        </Paragraph>
        <Rows
          items={[
            {
              key: "senales",
              head: "Escríbelo con señales que se vean",
              body: "Qué pide el ejercicio, cuántos pasos hay que encadenar, cuántas cosas hay que combinar, si la respuesta se lee directamente o hay que sacarla. «Es difícil para un principiante» no se puede comprobar mirando un ejercicio, así que no clasifica nada.",
            },
            {
              key: "escala",
              head: "La escala se mide contra tus ejercicios",
              body: "«Básico» es lo más sencillo que tu asignatura pide de verdad en ese tipo, y «avanzado» lo más exigente que llega a pedir. Un criterio copiado de otra asignatura deja todo tu material en «básico», y entonces el nivel no dice nada.",
            },
            {
              key: "reparto",
              head: "Compruébalo repartiendo",
              body: "Mira unos cuantos ejercicios tuyos de ese tipo y aplícales el criterio. Si te caen todos en el mismo nivel, el criterio no separa: aféinalo hasta que reparta.",
            },
            {
              key: "concepto",
              head: "No es de qué va, ni cuánto ocupa",
              body: "Un enunciado largo no es un ejercicio difícil, y uno de la última unidad no lo es por estar al final. De qué va cada ejercicio ya se anota aparte, contra el temario.",
            },
            {
              key: "quien-lo-lee",
              head: "Lo lee alguien que está eligiendo",
              body: "Al pedir un ejercicio nuevo verás los tres niveles con su criterio al lado y elegirás uno. Por eso el criterio se escribe nivel a nivel, cada uno con un ejemplo tuyo y con dónde está la frontera con el de al lado: «básico (reconocimiento)» no le dice nada a quien tiene que elegir.",
            },
          ]}
        />
      </Block>

      <Block title="Qué tiene cada parte de un tipo">
        <Paragraph>
          Esto solo se ve <strong>mientras corriges</strong>: el bloque{" "}
          {t("modality.fieldsOf", { name: "…" })} aparece bajo las dos tarjetas de arriba en
          cuanto pulsas «{t("stage.curate.start")}», y no antes. Es lo más técnico que se
          pregunta en todo el recorrido, y la pantalla no abre por ahí.
        </Paragraph>
        <Rows
          items={[
            {
              key: "tipo",
              head: t("field.type.label"),
              body: "Texto, número, lista o una enumeración cerrada de valores. Si eliges una enumeración, debajo aparece la lista de valores permitidos.",
            },
            {
              key: "obligatorio",
              head: t("field.required.label"),
              body: t("field.required.hint"),
            },
            {
              key: "descripcion",
              head: t("field.description.label"),
              body: t("field.description.hint"),
            },
            {
              key: "primario",
              head: t("field.primary.badge"),
              body: "El que lleva el enunciado. Es el texto con el que se empareja el ejercicio con los conceptos del temario, y solo puede serlo una parte de tipo texto.",
            },
          ]}
        />
      </Block>

      <Alert tone="danger" title="Tocarlo después de recoger tus ejercicios lo invalida">
        <p>
          Tus ejercicios se recogieron con estas partes. Si cambias las de un tipo, el Paso{" "}
          {stepNumberOf("exemplars_bank")} pasa a «{t(STATUS.stale.labelKey)}» y hay que volver
          a recogerlos.
        </p>
      </Alert>

      <Detail title="Esta primera versión no es estable, y conviene saberlo">
        <p>
          Los tipos se deducen de una muestra de tus ejercicios, y dos pasadas sobre el mismo
          material han llegado a producir conjuntos de partes <em>distintos</em>. Trátalo como
          un punto de partida: la versión que das por buena es tuya, no suya.
        </p>
      </Detail>
      <Verdict artifact="exemplars_profile" />
    </div>
  );
}

function Graph() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.prepare")} title={t("guide.sec.graph")}>
        <p>
          El temario de tu asignatura: sus conceptos, agrupados en unidades y unidos por lo
          que hace falta saber antes de cada cosa. Todo lo que se etiquete y se escriba después
          sale de aquí: ni el modelo ni tú podéis usar un concepto que no esté en el temario.
        </p>
      </SectionHead>

      <Facts
        items={[
          {
            label: "De dónde sale",
            value: `De los documentos que dejaste en «${t("raw.slot.corpus")}», leídos enteros.`,
          },
          {
            label: "Qué cuesta",
            value:
              "Es el trabajo más caro del recorrido: una llamada por página de tus apuntes y unas cuantas que razonan sobre la lista entera.",
          },
          {
            label: "Qué desbloquea",
            value: "Poner a tus ejercicios los conceptos del temario, decir hasta dónde ha llegado la clase, y pedir ejercicios nuevos.",
          },
        ]}
      />

      <Block title="Una lista, y un mapa debajo">
        <Paragraph>
          Lo primero que ves es el temario: las unidades en el orden en que se dan, plegadas.
          Ábrelas, o busca y se abren solas las que tengan resultados. Cada fila lleva el concepto
          y si <strong>{t("kg.taggable").toLowerCase()}</strong> —«{t("common.yes")}» o «
          {t("common.no")}»—; al pulsarla se abre su ficha <em>al lado de la lista</em>, con su
          unidad, su descripción y sus relaciones. Mientras solo estás mirando eso es una
          lectura, que es justo lo que se pide aquí: abrir un concepto y ver si lo que dice de él
          es tu asignatura.
        </Paragraph>
        <Paragraph>
          Al pulsar «{t("stage.curate.start")}», al final de la pantalla, esa misma ficha se
          vuelve editable —el nombre, la unidad y las relaciones— y en la lista aparecen los
          botones de añadir unidad y añadir concepto, y el «{t("kg.taggable").toLowerCase()}» de
          cada fila pasa de ser un «{t("common.yes")}» a ser un interruptor.
        </Paragraph>
        <Paragraph>
          El grafo de conocimiento va a la derecha de la lista, y la ficha del concepto elegido
          se abre entre los dos, así que un clic en la lista o en el grafo responde al lado
          de ambos. {t("kg.mapDescription")} Con el botón de ampliar se abre a pantalla completa{" "}
          <em>con la ficha al lado</em>, para poder cambiar lo que elijas sin volver atrás.
        </Paragraph>
        <Paragraph>
          Al elegir un concepto aparece, debajo de las tres columnas y a todo lo ancho, un
          bloque con sus relaciones dibujadas: una banda horizontal por tipo de relación, con
          el concepto en la misma columna en todas. La de «tiene como prerrequisito» es el orden
          de aprendizaje —a la izquierda lo que hace falta saber antes, hasta los conceptos de
          partida; a la derecha lo que se apoya en él— y en las demás cada flecha se lee como
          la frase «izquierda VERBO derecha». Es la forma rápida de ver si el orden tiene
          sentido para un concepto concreto sin leer el grafo entero; pulsando un concepto de
          una banda la ficha pasa a ese.
        </Paragraph>
        <Paragraph>
          El lienzo tiene dos disposiciones: <strong>«{t("canvas.layout.force")}»</strong>, que
          agrupa cada concepto junto a aquellos con los que se relaciona, y{" "}
          <strong>«{t("canvas.layout.curriculum")}»</strong>, que ordena por niveles de
          prerrequisito. Cambiar de una a otra no reconstruye nada: los nodos se desplazan hasta
          su nueva posición. Un nivel es una <em>banda</em> y no una fila, porque un temario real
          reparte los prerrequisitos de forma muy desigual; si hay menos de tres niveles el
          propio lienzo lo dice, porque eso es un dato sobre el temario y no una vista rota.
        </Paragraph>
      </Block>

      <Block title="La construcción no acaba con el temario">
        <Paragraph>
          En cuanto el temario está escrito se encadenan solas otras dos cosas, y la pantalla
          lo dice mientras pasan. No bloquean nada de lo que hay debajo: puedes ir leyendo los
          conceptos mientras terminan.
        </Paragraph>
        <Steps
          items={[
            <>
              <p className="font-medium">Las descripciones de cada concepto</p>
              <p className="text-small text-muted-foreground">
                La prosa que describe cada concepto, escrita contra los párrafos de tus apuntes de
                los que salió. <strong>Es el texto con el que se compara, no el nombre.</strong>{" "}
                Se corrigen en la ficha del concepto, que es donde se están leyendo — y es lo único
                que se puede seguir corrigiendo con el paso cerrado, porque vive aparte y no
                caduca nada.
              </p>
            </>,
            <>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                Qué conceptos sirven de etiqueta
                <Badge variant="attention">
                  necesita el Paso {stepNumberOf("exemplars_profile")} cerrado
                </Badge>
              </p>
              <p className="text-small text-muted-foreground">
                Los que valdrían para cualquier ejercicio —«codificación», «diseño»— se marcan
                como que NO sirven de etiqueta: siguen existiendo y siguen funcionando a través
                de sus relaciones, simplemente dejan de poder ser el concepto de un ejercicio. Ante
                la duda se excluye: una etiqueta vaga contamina todos tus ejercicios. Se juzga
                contra los tipos de ejercicio del paso anterior, y por eso ese paso va antes.
              </p>
            </>,
          ]}
        />
        <Paragraph>
          El botón que vuelve a lanzar esa revisión está arriba a la derecha y{" "}
          <strong>solo aparece mientras corriges</strong>: es algo que se le hace al temario, no
          algo que se mire. Con el paso ya cerrado se ve, pero se niega y dice por qué.
        </Paragraph>
      </Block>

      <Block title="Curar el temario a mano">
        <Paragraph>
          Con «{t("stage.curate.start")}» pulsado se puede renombrar lo que quedó torcido,
          borrar lo que no es un concepto de la materia, mover conceptos de unidad y arreglar
          relaciones. Renombrar un concepto arrastra consigo el trozo de tus apuntes del que salió;
          borrarlo lo suelta. Marcar o desmarcar «{t("kg.taggable").toLowerCase()}» no mueve la
          fila de sitio: se queda donde estaba, debajo de la mano que la pulsó.
        </Paragraph>
      </Block>

      <div className="space-y-2">
        <Detail title="Por qué no se empareja por el nombre del concepto">
          <p>
            Un nombre es una etiqueta de dos palabras y no dice nada de qué se practica al
            usarlo. Con lo que se compara es con la <em>descripción</em>, fundida con lo que
            tienen en común tus ejercicios que ya llevan ese concepto.
          </p>
          <p>
            Por eso una descripción mal escrita se paga cada vez que se pone un concepto a un
            ejercicio y cada vez que se escribe uno nuevo, y por eso conviene leerlas.
          </p>
        </Detail>

        <Detail title="Lo que se da por sabido y lo que se prohíbe">
          <p>
            Alrededor de los conceptos que pides, se sacan del temario dos listas y se le dan al
            modelo:
          </p>
          <Rows
            items={[
              {
                key: "sabido",
                head: <span className="text-settled">{t("form.given")}</span>,
                body: "Lo que hace falta saber antes del concepto pedido y además ha dado ya la clase. El ejercicio puede apoyarse en ello, pero no puede convertirlo en la dificultad. Va con su descripción, no con su nombre a secas.",
              },
              {
                key: "prohibido",
                head: <span className="text-destructive">{t("form.forbidden")}</span>,
                body: "Lo que va después del concepto pedido y la clase todavía no ha visto. No puede aparecer.",
              },
            ]}
          />
          <p>
            Las dos recorren el temario entero y no un salto, y se acotan con lo que digas que
            ha dado la clase. Al pedir un ejercicio se dibujan antes de lanzar, para que veas
            exactamente con qué va a contar el modelo.
          </p>
        </Detail>
      </div>
      <Verdict artifact="knowledge_graph" />
    </div>
  );
}

function Bank() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.prepare")} title={t("guide.sec.bank")}>
        <p>
          Tus ejercicios recogidos uno a uno de los documentos, cada uno con los conceptos del
          temario que practica. Lo que se repasa aquí es <strong>ese emparejamiento</strong>:
          si el concepto que se le ha puesto a cada ejercicio es el que de verdad practica.
        </p>
        <p>
          Importa porque son los ejemplos que acompañan a cada ejercicio nuevo: de aquí sale el
          «así se escriben los ejercicios en esta asignatura» que el modelo imita, y se eligen
          por el concepto que lleva cada uno.
        </p>
      </SectionHead>

      <Facts
        items={[
          {
            label: "De dónde sale",
            value: `De los documentos de «${t("raw.slot.exemplars")}», recorridos uno detrás de otro.`,
          },
          { label: "Qué cuesta", value: "Crece con el número de documentos: se recorren todos, enteros." },
          {
            label: "Si lo cancelas",
            value: "Se pierde la pasada entera, pero lo que ya tenías se queda tal cual: se reemplaza sólo al terminar.",
          },
        ]}
      />

      <Alert tone="info" title="Recoger y etiquetar son un solo trabajo">
        <p>
          A cada documento se le ponen los conceptos según sale, así que al terminar ya está todo
          etiquetado: no hay un paso intermedio que lanzar. Lo que queda es corregir lo que
          salió mal, y para eso hay tres controles distintos.
        </p>
      </Alert>

      <Block title="La tira de medidores dice dos cosas distintas">
        <Rows
          items={[
            {
              key: "etiquetados",
              head: t("bank.taggedItems"),
              body: "Cuántos de tus ejercicios llevan al menos un concepto. Es el trabajo de corrección que queda por delante. Sólo aparece mientras falte alguno: con todos etiquetados no hay nada que mirar ahí.",
            },
            {
              key: "cobertura",
              head: t("bank.conceptsWithExample"),
              body: t("bank.coverageBody"),
            },
          ]}
        />
        <Paragraph>
          Los dos miran en direcciones opuestas y conviene no confundirlos: uno cuenta{" "}
          <em>ejercicios sin concepto</em>, el otro <em>conceptos sin ejercicio</em>. Se puede tenerlo
          todo etiquetado y medio temario sin un solo ejemplo que imitar.
        </Paragraph>
      </Block>

      <Block title="Se revisa por sospecha, no de arriba abajo">
        <Steps
          items={[
            <>
              Primero, los que <strong>se quedaron sin concepto</strong>. La tira de medidores de
              arriba los cuenta y «{t("bank.seeUntagged", { n: "N" })}» los filtra.
            </>,
            <>
              Después, los que llevan <strong>un solo concepto</strong> o uno que no encaja: todas
              las filas miden lo mismo y la columna de conceptos se lee de un vistazo, que es donde
              el emparejamiento se equivoca sin avisar. Pulsa una fila para leer el ejercicio
              entero.
            </>,
            <>
              Si hay que corregir, «{t("stage.curate.start")}» al final de la pantalla: entonces
              cada ejercicio se puede editar y se puede cambiar a mano su <strong>concepto
              principal</strong>, que es el que decide con qué se compara después.
            </>,
          ]}
        />
      </Block>

      <Block title="Las tres formas de volver a poner conceptos, que no hacen lo mismo">
        <Paragraph>
          Las tres <strong>solo aparecen mientras corriges</strong>: son lo único de esta
          pantalla que escribe. Lo que dicen no se pierde al ocultarlas — cuántos ejercicios
          están sin concepto lo sigue diciendo el medidor, y «{t("bank.seeUntagged", { n: "N" })}»
          es un filtro y sigue ahí.
        </Paragraph>
        <Rows
          items={[
            {
              key: "pendientes",
              head: <>«{t("bank.retagUntagged", { n: "N" })}»</>,
              body: "Se lanza sobre exactamente los ejercicios que se quedaron sin concepto, nunca sobre todos. Está en la tira de medidores, al lado del número sobre el que actúa.",
            },
            {
              key: "todo",
              head: <>«{t("bank.retagAll")}»</>,
              body: "Todos, desde cero. Sobrescribe los conceptos actuales, incluidos los que hayas corregido a mano, y por eso pide confirmación antes de lanzarse.",
            },
            {
              key: "seleccion",
              head: <>«{t("bank.retagSelected")}»</>,
              body: "Solo los ejercicios marcados a mano, aunque ya tuvieran concepto. Vive al pie de la tabla, porque es contextual: pertenece a las filas y no a los totales.",
            },
          ]}
        />
      </Block>

      <Block title="Encontrar un ejercicio concreto">
        <Paragraph>
          Sobre la tabla hay cinco filtros que se combinan: una <strong>búsqueda</strong> por
          texto del enunciado o por id, el <strong>tipo de ejercicio</strong> —los del Paso{" "}
          {stepNumberOf("exemplars_profile")}, cada uno con cuántos ejercicios tuyos tiene—, el{" "}
          <strong>documento de origen</strong>, el <strong>nivel</strong> —los tres peldaños, cada
          uno con su cuenta— y, al final de la fila, el interruptor de{" "}
          <strong>«{t("bank.untagged")}»</strong>, que es el único de los cinco que no habla de
          cómo es un ejercicio sino del trabajo que queda. Con un solo tipo declarado ese
          desplegable no aparece: un menú con una única opción no filtra nada.
        </Paragraph>
        <Paragraph>
          Las cuentas de esos menús son sobre <em>todos</em> tus ejercicios y no se mueven con
          los demás filtros: dicen qué hay ahí dentro, no qué acabas de preguntar. No hay
          control de orden: la lista va en el orden en que se recogieron. El nivel se{" "}
          <em>filtra</em> y no se ordena, porque con tres peldaños ordenar solo agrupa, y lo que
          se pregunta de verdad es «enséñame los avanzados».
        </Paragraph>
        <Paragraph>
          Cada página son <strong>siete ejercicios</strong>, y todas las filas cerradas miden lo
          mismo: el enunciado se corta a dos líneas y se dibujan como mucho tres conceptos, con un
          «+N» que los nombra al pasar el cursor. Una tabla cuyas filas crecen con lo largo que
          sea cada enunciado no se puede leer por columnas, que es como se busca lo que está mal.
        </Paragraph>
      </Block>

      <Detail title="Reintentar tiene sentido: el emparejamiento mejora entre pasadas">
        <p>
          Cada ejercicio bien etiquetado tira de su concepto hacia donde de verdad está, así que lo
          que aprende una pasada lo aprovecha la siguiente. Un ejercicio que hoy no encuentra
          concepto puede encontrarlo mañana sin que hayas tocado nada.
        </p>
        <p>
          Por eso los que se quedaron fuera se vuelven a intentar en cada pasada, en vez de
          quedar marcados como imposibles.
        </p>
      </Detail>
      <Verdict artifact="exemplars_bank" />
    </div>
  );
}

function Generate() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.use")} title={t("guide.sec.generate")}>
        <p>
          La primera puerta de la <strong>{t("nav.phase.test").toLowerCase()}</strong>, y
          aquello para lo que existe la construcción: un encargo, una tanda de ejercicios nuevos. El formulario es un
          acordeón — se responde de arriba abajo y cada pregunta se cierra en una línea al
          contestarla, así que volver a cambiar los conceptos cuesta un clic y ningún scroll.
        </p>
        <p>
          Lo <strong>numerado es el encargo</strong>: como mucho cuatro preguntas, y dos de
          ellas solo aparecen si tu asignatura las necesita. El texto libre no lleva número y
          vive plegado en «{t("form.instructions.title")}», debajo.
        </p>
      </SectionHead>

      <Block title="Las preguntas numeradas, en el orden en que se hacen">
        <Steps
          items={[
            <>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                {t("form.type.title")}
                <Badge variant="outline">solo con varios tipos de ejercicio</Badge>
              </p>
              <p className="text-small text-muted-foreground">
                {t("form.type.hint")} Con un solo tipo declarado, esta pregunta no se hace.
              </p>
            </>,
            <>
              <p className="font-medium">{t("form.practise.title")}</p>
              <p className="text-small text-muted-foreground">
                {t("form.practise.hint")} Solo se ofrecen los conceptos{" "}
                <strong>{t("kg.taggable").toLowerCase()}</strong>: aquí se elige de qué va el
                ejercicio, y para eso un concepto genérico no vale.
              </p>
            </>,
            <>
              <p className="font-medium">{t("form.difficulty.title")}</p>
              <p className="text-small text-muted-foreground">
                Los tres niveles del tipo que hayas elegido, cada uno con debajo el criterio que
                escribiste en el Paso {stepNumberOf("exemplars_profile")}, y «
                {t("decision.any")}» para no fijarlo. Es la misma escala en todos los tipos, así
                que pedir «avanzado» quiere decir lo mismo aquí que en la lista de tus
                ejercicios.
              </p>
            </>,
            <>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                {t("form.decisions.titleMany")}
                <Badge variant="outline">solo si algún tipo deja algo a tu criterio</Badge>
              </p>
              <p className="text-small text-muted-foreground">
                {t("form.decisions.hint")}
              </p>
            </>,
          ]}
        />
      </Block>

      <Block title={`Lo opcional, plegado en «${t("form.instructions.title")}»`}>
        <Paragraph>
          Debajo de las preguntas numeradas hay una divulgación que dice de un vistazo si hay
          algo escrito dentro. No es obligatoria, y por eso no ocupa un número: el orden de la
          pantalla es primero lo que hay que contestar y después lo que se puede añadir.
        </Paragraph>
        <Rows
          items={[
            {
              key: "instructions",
              head: t("form.instructions.title"),
              body: (
                <>
                  {t("form.instructions.hint")} Hay un tope de 600 caracteres que la propia caja
                  va contando, y lo que escribas pasa por dos filtros antes de llegar al modelo.
                </>
              ),
            },
          ]}
        />
      </Block>

      <Block title="Antes de lanzar, lo que el temario va a decirle al modelo">
        <Paragraph>
          Bajo los conceptos elegidos aparece «{t("form.graphSays")}» con las dos listas que se le
          van a dar: «{t("form.given")}» y «{t("form.forbidden")}». Salen del temario y de lo que
          hayas dicho que ha dado la clase, y se ven <em>antes</em> de gastar nada.
        </Paragraph>
        <Paragraph>
          Ahí mismo se avisa de <strong>los conceptos sin ejemplo</strong>: si algún concepto elegido no
          tiene ningún ejercicio tuyo —o ninguno del tipo pedido—, la tanda se escribe sin
          ejemplo que imitar y la calidad suele bajar. Por defecto la lista solo ofrece conceptos que
          tus ejercicios puedan ilustrar —tampoco los prerrequisitos que no tengan ejemplo— y el
          pie dice cuántos se está dejando fuera; «Todos los conceptos», en
          la cabecera del selector, saca el temario entero, con los conceptos sin ejemplo
          marcados en punteado.
        </Paragraph>
      </Block>

      <Block title="Qué le pasa a lo que escribes en el texto libre">
        <Rows
          items={[
            {
              key: "guardrail",
              head: "1 · Guardarraíl",
              body: "Una comprobación fija bloquea las órdenes de anular instrucciones («olvida lo anterior…»), y después un modelo juez decide si hay algo dañino o un intento de saltarse las restricciones del ejercicio.",
            },
            {
              key: "admisibilidad",
              head: "2 · Admisibilidad",
              body: "Decide si lo que pides es de esta caja o de algo que ya has decidido más arriba: los conceptos, el tipo de ejercicio, las partes del ejercicio o la propia asignatura. Si lo es, te dice qué control lo decide.",
            },
          ]}
        />
        <Alert tone="settled" title="Si el juez no puede contestar, tu petición pasa">
          <p>
            Motor caído, respuesta ilegible o veredicto que no se sostiene: los tres dejan seguir
            el encargo y lo dicen en el registro. Una pantalla que bloquea cuando su juez está
            caído bloquea todo.
          </p>
        </Alert>
      </Block>

      <Block title="Qué modelo lo escribe">
        <Paragraph>
          Lo eliges tú, entre los que la instalación ofrece. Quien la administra fija esa
          lista en «Configuración → Modelos generadores»; tú ves una ficha por modelo con lo
          que cuesta cada uno —uno contesta en segundos, otro tarda minutos y delibera— y el
          primero de la lista viene marcado. Si sólo se ofrece uno no se te pregunta nada.
        </Paragraph>
        <Paragraph>
          Se elige <em>antes</em> que el esfuerzo y no después, porque cuántos niveles hay y
          cuál conviene evitar es cosa del modelo. Hay modelos que contestan igual pongas el
          nivel que pongas: en esos no se dibuja la barra, y quién es quién también lo declara
          quien administra. El modelo queda guardado con cada ejercicio, así que en
          «{t("menu.savedVariants")}» puedes comparar dos enunciados sabiendo qué escribió
          cada uno.
        </Paragraph>
      </Block>

      <Block title="Razonamiento y esfuerzo">
        <Paragraph>
          El interruptor decide si el modelo delibera antes de contestar; la barra de al lado,
          cuánto. Un esfuerzo alto en el modelo local multiplica el tiempo por varias veces sin
          mejorar necesariamente el enunciado, y la propia pantalla te avisa cuando el modelo que
          va a atender el encargo es de los que se descontrolan por arriba.
        </Paragraph>
      </Block>

      <Block title="Mientras corre">
        <Paragraph>
          Al lanzar, el formulario se pliega a una línea con el resumen del encargo y sobre los
          resultados aparece una tira: el nombre del trabajo, su estado, el tiempo que lleva y —
          si está esperando turno— «{t("queue.queuedAhead", { n: "N" })}» <em>en lugar</em> de la
          barra. El botón de cancelar vive ahí, y solo ahí.
        </Paragraph>
        <Paragraph>
          El resto se pliega detrás de «{t("run.detail")}», en esa misma tira: los pasos, el
          texto según se escribe, los ejercicios tuyos que se le han enseñado al modelo y los
          detalles técnicos de la llamada. Es el único sitio donde se ven esas tres cosas. Se
          abre solo mientras el trabajo corre y se cierra al terminar, salvo que lo toques tú.
        </Paragraph>
      </Block>

      <Block title="Lo que ves al terminar">
        <Rows
          items={[
            {
              key: "guardada",
              head: <Badge variant="settled">{t("result.saved")}</Badge>,
              body: (
                <>
                  Cada ejercicio se guarda en «{t("menu.savedVariants")}» <em>en cuanto valida</em>,
                  con su encargo entero. Un lote cancelado a la tercera conserva tres.
                </>
              ),
            },
            {
              key: "senales",
              head: <Badge variant="attention">2 señales</Badge>,
              body: (
                <>
                  Lo que se puede comprobar sin juzgar el ejercicio: si nombra algo que la clase
                  aún no ha visto, si se parece demasiado a un ejemplo o a otro de la misma
                  tanda, y si al releerlo se le reconoce el concepto que pediste. Las dos primeras
                  hacen que se <em>vuelva a intentar</em> antes de dártelo; lo que llega marcado
                  es lo que siguió sin salir limpio, y entonces{" "}
                  <strong>es una señal para quien lee, no un rechazo</strong>.
                </>
              ),
            },
            {
              key: "reintentada",
              head: <Badge variant="outline">{t("result.retried", { n: "N" })}</Badge>,
              body: "Cuántas veces hubo que repetir la llamada por esas dos señales. No dice que el ejercicio esté mal: dice lo que costó.",
            },
          ]}
        />
        <Paragraph>
          Un ejercicio sin nada que señalar no lleva esa caja: sólo se dibuja cuando hay algo
          que mirar.
        </Paragraph>
      </Block>

      <Block title="Y después">
        <Rows
          items={[
            {
              key: "variar",
              head: <>«{t("generate.vary")}»</>,
              body: "Reabre el formulario con todo relleno y deja los resultados a la vista hasta que lanzas otra tanda. Cambia lo que quieras —o no cambies nada, si lo que buscas es otro lote del mismo encargo— y vuelve a lanzar.",
            },
            {
              key: "cero",
              head: <>«{t("generate.startOver")}»</>,
              body: "Reabre el formulario vacío, para un encargo que no tiene nada que ver con el anterior.",
            },
            {
              key: "exportar",
              head: <>«{t("generate.export")}»</>,
              body: "Un menú con tres salidas para el lote entero: copiar el JSON, descargarlo, o descargarlo como Markdown.",
            },
            {
              key: "como-esta",
              head: <>«{t("generations.moreLikeThis")}»</>,
              body: (
                <>
                  Está en «{t("nav.myVariants")}» y recupera el encargo de un ejercicio
                  concreto, aunque sea de otro día.
                </>
              ),
            },
          ]}
        />
      </Block>
    </div>
  );
}

function Evaluate() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.use")} title={t("guide.sec.evaluate")}>
        <p>
          El mismo encargo resuelto por dos arquitecturas distintas y presentado{" "}
          <strong>a ciegas</strong>, para que elijas sin saber cuál es cuál. Una de las dos es
          siempre este sistema; la otra se sortea en cada sesión entre las dos alternativas —
          un modelo comercial, o una búsqueda por similitud sobre tus documentos —. Es la
          parte del sistema que sirve para medirlo, no para producir material.
        </p>
        <p>
          Tú pides la comparación y tú la juzgas: eliges de qué concepto quieres el ejercicio,
          se preparan las dos versiones y las lees cuando estén.
        </p>
      </SectionHead>

      <Facts
        items={[
          {
            label: "Qué se te pide",
            value: "Leer dos propuestas, una pregunta por tarjeta y una elección.",
          },
          {
            label: "Qué produce",
            value: "Una sesión guardada con las dos propuestas y tu juicio.",
          },
          {
            label: "Qué necesitas",
            value: "Los cuatro pasos cerrados: las dos versiones se escriben con tu asignatura.",
          },
        ]}
      />

      <Block title="Las dos pestañas">
        <Rows
          items={[
            {
              key: "encargo",
              head: t("eval.tab.compose"),
              body: "Donde abre la pantalla. Eliges de qué concepto y de qué tipo quieres el ejercicio: es el mismo formulario de «Generación de ejercicios», sin dos controles —cuántos ejercicios y si el modelo delibera—, porque una comparación es siempre uno por versión. El modelo que escribe las dos propuestas locales no se elige aquí: lo fija quien administra en «Configuración → Evaluación», y la comercial usa el suyo.",
            },
            {
              key: "sesiones",
              head: t("eval.tab.history"),
              body: "Tu histórico. Puedes releer cualquier sesión ya cerrada, con la revelación incluida.",
            },
          ]}
        />
        <Paragraph>
          Mientras una comparación está abierta las pestañas desaparecen, y con ellas el detalle
          técnico: diría de qué arquitectura sale cada propuesta antes de que la leas. Se vuelve a
          la lista con el botón de la cabecera. Al salir de la pantalla y volver, se abre en el
          formulario: una comparación ya terminada se relee desde «{t("eval.tab.history")}».
        </Paragraph>
      </Block>

      <Block title="Cómo va una comparación">
        <Steps
          items={[
            <>
              Aparecen las dos propuestas, sin etiquetar y en un orden que es solo tuyo.
              Encima, en una línea, el encargo: el tipo de ejercicio, los conceptos, el nivel si
              se fijó uno y, si se sorteó, el escenario en el que se ambientan las dos. Si en
              «Instrucciones adicionales» ya dijiste de qué va el ejercicio, no se sortea ninguno:
              tus palabras llegan a las dos propuestas tal cual. Sea cual sea, es el mismo para
              las dos, así que no delata nada. Tampoco se dice cuál de las dos alternativas le
              ha tocado a esta sesión.
            </>,
            <>
              Las dos tarjetas son cajas de la misma altura, corta o larga la propuesta, y cada
              una se desplaza por dentro. El botón azul «{t("reveal.read")}» de su cabecera la
              abre entera, a tamaño de lectura y con la pregunta al pie; ← y → pasan de una a
              otra.
            </>,
            <>
              <strong>Respondes una pregunta por tarjeta</strong>: si la pondrías en clase —
              o, si eres alumno, si te serviría para practicar. Un clic, primera impresión, sin
              darle vueltas.
            </>,
            <>
              <strong>Eliges una</strong>. La barra de elección queda fija al pie de la ventana;
              no se activa hasta que has respondido a las dos, y siempre puedes decir que
              ninguna te convence.
            </>,
            <>
              Solo entonces se revela qué arquitectura escribió cada una: una columna por
              propuesta, con lo que respondiste sobre ella, el modelo y el tiempo, y un
              «{t("reveal.read")}» que la abre entera junto con de dónde salió.
            </>,
            <>
              Con ella se destapan también <strong>los conceptos de cada propuesta</strong>,
              leídos con el mismo etiquetador que el banco, y una línea que dice si el
              ejercicio se ha metido en algo que va después en el temario. La regla es la
              misma para las dos y es la que el sistema lleva en su prompt, solo que
              únicamente una de las dos la conoce. Con currículo, cuenta cualquier mención
              de lo que la clase no ha dado; sin él, solo cuenta que la propuesta practique
              un concepto posterior a lo pedido.
            </>,
            <>
              Si te apetece, afinas la del sistema en cuatro escalas, con su ejercicio al lado.
              Es <strong>opcional</strong>: la comparación ya quedó registrada al elegir.
            </>,
            <>
              Debajo, «{t("eval.orderAnother")}» cierra la sesión y te deja en el formulario,
              listo para pedir la siguiente. Si alguien te ha dejado comparaciones en la cola,
              ese mismo botón abre la que viene.
            </>,
          ]}
        />
      </Block>

      <Alert tone="settled" title="Todo lo que se mide va antes de la revelación">
        <p>
          Una puntuación dada después de saber qué es cada cosa es una puntuación sobre un
          nombre, no sobre un ejercicio. Por eso la pregunta por tarjeta y la elección van
          antes, y la revelación es lo último: es la recompensa por terminar, no una puerta
          delante de más trabajo.
        </p>
      </Alert>

      <Block title="Si no es de lo tuyo, dilo">
        <Paragraph>
          Abajo a la derecha hay un enlace discreto:{" "}
          <strong>«No tengo criterio para juzgar esto»</strong>. Los evaluadores vienen de
          asignaturas y cursos distintos, así que encontrarte con un ejercicio que no te toca
          es normal y no es un fallo tuyo.
        </Paragraph>
        <Paragraph>
          Saltarla es la respuesta correcta y queda registrada como tal:{" "}
          <strong>no cuenta como preferencia</strong> ni ensucia ningún promedio. Contestar
          por compromiso sí lo haría, y no habría forma de saberlo después.
        </Paragraph>
      </Block>

      <Alert tone="settled" title="No verás el marcador acumulado">
        <p>
          Enseñarte el resultado de lo que estás a punto de juzgar es invitarte a compensarlo. Tus
          sesiones son tuyas y las puedes releer; el recuento es de quien analiza el estudio.
        </p>
      </Alert>

      <Detail title="Las tres arquitecturas, de las que cada sesión enfrenta dos">
        {ARM_ORDER.map((arm) => (
          <div key={arm} className="flex gap-3">
            <span
              aria-hidden
              className="mt-1.5 size-3 shrink-0"
              style={{ background: ARM_META[arm].colour }}
            />
            <p className="flex-1">
              <span className="font-medium text-foreground">{t(ARM_META[arm].labelKey)}</span> —{" "}
              {t(ARM_META[arm].descriptionKey)}
            </p>
          </div>
        ))}
        <p>
          Cada sesión enfrenta a este sistema con <strong>una</strong> de las otras dos, elegida
          a cara o cruz por la misma semilla que decide el orden. Así la pregunta que se
          responde es la que importa —¿escribe el sistema mejores ejercicios que esta
          alternativa?— y, sobre muchas sesiones, cada alternativa se enfrenta al sistema
          tantas veces como la otra.
        </p>
        <p>
          Cada arquitectura tiene su color fijo y siempre el mismo, en todas las sesiones y en
          todas las gráficas, para que dos sesiones separadas por meses se puedan leer juntas.
        </p>
        <p>
          El color aparece <strong>solo tras la revelación</strong>. Mientras la comparación
          es ciega, una tarjeta con color sería una tarjeta que lleva información.
        </p>
        <p>
          Qué recibe exactamente cada una está escrito, fila a fila, bajo el formulario de «
          {t("eval.tab.compose")}»: es la tabla «{t("fair.title")}», y dice quién ve los
          conceptos, quién las descripciones, quién trozos de tus documentos, quién tus
          ejercicios del banco como ejemplo, quién los prerrequisitos. {t("fair.footnote")}
        </p>
      </Detail>

      <Detail title="Por qué el orden de las tarjetas es distinto para cada persona">
        <p>
          Si dos evaluadores juzgan los mismos dos ejercicios, cada uno los ve en un orden
          propio. Compartir el orden significaría compartir también la tendencia a elegir la
          primera o la última, y entonces lo que parecería acuerdo sobre los ejercicios sería
          en parte acuerdo sobre dónde estaban colocados.
        </p>
        <p>
          Ese orden se sortea con una semilla que queda guardada con la sesión, así que meses
          después se puede reconstruir exactamente qué viste y en qué posición.
        </p>
      </Detail>

      <Detail title="Lo que no eliges tú">
        <p>
          <strong>Cuántos ejercicios se generan</strong>: siempre uno por propuesta, dos por
          sesión. Es lo que hace de la sesión la unidad de análisis.
        </p>
        <p>
          <strong>Contra cuál de las dos alternativas se compara el sistema</strong>: lo sortea
          cada sesión, y no se dice hasta la revelación. Elegirlo dejaría fuera la alternativa
          que menos apetece leer, y el estudio necesita medir las dos.
        </p>
        <p>
          <strong>Si el modelo razona antes de responder</strong>: lo sortea cada sesión, no
          tú. Elegirlo lo correlacionaría con tu ánimo y con el tiempo que tengas; sorteado,
          es una condición que se puede medir aparte después. Se aplica igual a las dos
          propuestas locales, así que nunca separa a una de la otra.
        </p>
      </Detail>
    </div>
  );
}

function Runs() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.daily")} title={t("guide.sec.runs")}>
        <p>
          Los trabajos hacen cola <strong>por motor</strong>, y cada motor tiene su sitio. En el
          local cabe uno: la GPU es una, y dos trabajos encima no harían más que intercambiarse
          pesos. En el remoto caben <strong>varios a la vez</strong>, porque allí lo que se
          reparte no es una máquina sino una cuota, y de la cuota se encarga el limitador
          llamada a llamada — así que dos personas pueden generar contra Cerebras al mismo
          tiempo sin esperarse. Un trabajo local y otro remoto nunca se esperan entre sí. Puedes
          cerrar la pestaña: el trabajo corre en el servidor y al volver lo encuentras donde
          estaba. Cada trabajo se mira <strong>en la pantalla que lo lanzó</strong>: no hay un
          sitio aparte desde el que vigilarlos todos.
        </p>
      </SectionHead>

      <Block title="Los seis estados">
        <Paragraph>
          Ningún estado se distingue solo por el color: cada uno tiene su forma, y se lee en la
          barra de arriba, bajo el nombre de cada paso. La cabecera del paso no lleva ninguna
          etiqueta: lo que un estado te pide lo dicen los avisos de la pantalla.
        </Paragraph>
        <Rows
          items={STATE_ORDER.map((key) => ({
            key,
            head: (
              <span className="flex items-center gap-3">
                <StatusMark
                  status={key === "blocked" ? "missing" : key}
                  blocked={key === "blocked"}
                  size="md"
                />
                {t(STATUS[key].labelKey)}
              </span>
            ),
            body: STATE_HINTS[key],
          }))}
        />
      </Block>

      <Block title="La barra es el plan">
        <div className="space-y-3 rounded-lg border border-border bg-card p-4">
          <BuildPlanBar />
          <Paragraph>
            Es el plan real del constructor del grafo, leído de la API y no copiado aquí. Cada
            tramo es una fase y su anchura es el <em>peso medido</em> de esa fase: por eso la
            lectura de los apuntes se lleva ella sola un tercio de la barra, el enlazado y la
            limpieza casi la mitad entre los dos, y la curación final es una raya. La que se
            mueve es la que está corriendo. No hay estimación de tiempo en ninguna parte, y es
            deliberado: cambiar de modelo cambia el coste de cada llamada por múltiplos, y una
            cifra falsa es peor que ninguna.
          </Paragraph>
        </div>
      </Block>

      <Block title="Dónde se mira">
        <Rows
          items={[
            {
              key: "etapa",
              head: <>En la pantalla del paso</>,
              body: "Mientras un paso se construye, su pantalla lleva la barra de fases: qué fase corre, cuánto pesa cada una y cuánto va hecho. Es donde se mira una construcción, y desde ahí se cancela.",
            },
            {
              key: "ejecucion",
              head: <>Al pedir ejercicios</>,
              body: "Sobre los resultados aparece una tira con el trabajo en curso: cuánto lleva, por dónde va y cómo pararlo. Se despliega para ver los pasos, lo que el modelo va escribiendo y los ejemplos que se le han enseñado.",
            },
          ]}
        />
        <Paragraph>
          El <strong>registro técnico no se ve en la aplicación</strong>: cada línea que escribe
          la tubería se guarda en el servidor, en <code>logs/</code> y dentro en la carpeta de la
          asignatura. Es material para leer junto a una traza, no para mirar mientras trabajas, y
          es lo que se pide cuando algo falla.
        </Paragraph>
        <Paragraph>
          Con el motor partido en dos mitades pueden estar corriendo <strong>dos trabajos a la
          vez</strong>, uno en cada una. Cada pantalla busca el suyo por el tipo de trabajo que
          lanzó, no «el último que se movió», que con dos carriles ya no identifica a nadie.
        </Paragraph>
      </Block>

      <Block title="«En cola» no es «en marcha»">
        <Paragraph>
          Un trabajo que espera su turno lo dice con «{t("queue.queuedAhead", { n: "N" })}» y{" "}
          <strong>no dibuja barra de progreso</strong>: una barra sobre algo que no ha empezado
          afirma que se está haciendo un trabajo que nadie está haciendo. Vale igual en la
          cabecera del paso y en el botón que lo lanzó.
        </Paragraph>
        <Paragraph>
          El número entre paréntesis cuenta trabajos, no minutos, y solo cuenta los del{" "}
          <em>mismo motor</em>: si lo tuyo es remoto y lo que hay en marcha es local, no vas
          detrás de nada. Un encargo en cola es un encargo hecho, así que el formulario se queda
          plegado y lo que se te ofrece es cancelarlo, no volver a lanzarlo.
        </Paragraph>
      </Block>

      <Alert tone="attention" title="Cancelar">
        <p>
          Cancelar corta enseguida: no hay que esperar a que el modelo termine de escribir lo
          que estuviera escribiendo, se le corta a media frase y la máquina queda libre. Lo que
          ya hubiera salido en firme se conserva.
        </p>
      </Alert>

      <Detail title="La cinta de aviso de la barra superior">
        <p>
          Cuando el motor de inferencia no responde, o cuando falta algún modelo por descargar,
          aparece una cinta bajo la barra de navegación diciendo exactamente qué se rompe y qué
          sigue funcionando: lo ya construido se sigue leyendo siempre, lo que falla es arrancar
          trabajos nuevos.
        </p>
        <p>
          Esa cinta es <em>todo</em> lo que el día a día dice sobre la máquina, y es deliberado:
          el estado del motor, qué modelos están cargados, cuánta VRAM se reparten y la cola
          entera de la instalación son propiedades de la instalación y no de tu instancia, así
          que viven en «{t("admin.tab.engine")}», dentro de «{t("admin.title")}». Aquí solo
          aparece lo que te impide trabajar.
        </p>
      </Detail>
    </div>
  );
}

function Account() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.daily")} title={t("guide.sec.account")}>
        <p>
          Todo lo que es tuyo y no es parte de la cadena vive en «{t("account.title")}», detrás
          del icono de cuenta de arriba a la derecha — el mismo menú desde el que has llegado
          aquí, y donde está también «{t("admin.title")}». «{t("nav.myVariants")}» tiene su
          propio botón justo al lado, porque se abre a diario.
        </p>
      </SectionHead>

      <Rows
        items={[
          {
            key: "cuenta",
            head: t("tabs.account"),
            body: "Tu nombre visible, la contraseña y el idioma en el que lees la aplicación. Si la instalación tiene correo configurado aparece además una dirección opcional, que no sirve para entrar: solo para recibir el enlace de restablecer la contraseña. Sin correo configurado el campo no está, porque no habría nada que entregar ahí — el enlace se pide a quien administra.",
          },
          {
            key: "workspaces",
            head: t("tabs.workspaces"),
            body: "En qué asignaturas estás y con qué papel, y desde cuál entrar a otra. Los accesos los concede quien administra: aquí no se piden. Lo único que puedes hacer sobre ellas es eliminar una tuya — de las que eres propietario —, y al hacerlo se te dice qué desaparece y qué se queda. El nombre no se cambia desde aquí: se pone al crearla y solo lo cambia quien administra.",
          },
          {
            key: "variantes",
            head: t("tabs.variants"),
            body: "Todo lo que TÚ has generado, con el encargo que lo produjo: se puede buscar, relanzar «más como este» y borrar. Es privado: aunque compartas la asignatura con otras personas, cada quien ve solo lo suyo.",
          },
        ]}
      />

      <Block title="El idioma de la interfaz">
        <Paragraph>
          Tres botones en la pestaña «{t("tabs.account")}»: en qué idioma se te muestran las pantallas, esta
          guía y los mensajes de error. Es tuyo y de nadie más —ni siquiera quien administra lo
          toca—, y se puede cambiar cuantas veces quieras sin consecuencias: no traduce nada de
          lo ya escrito.
        </Paragraph>
        <Detail title="Tres idiomas que no son el mismo">
          <Rows
            items={[
              {
                key: "interfaz",
                head: "El de la interfaz",
                body: "Lo que TÚ lees. Vive en tu cuenta, se cambia cuando quieras y no afecta a nada más.",
              },
              {
                key: "prompts",
                head: "El de los prompts",
                body: "En el que se le HABLA AL MODELO. Vive en la asignatura, se elige al crearla y ya no se cambia: las etiquetas de las relaciones quedan escritas dentro del grafo y el cargador indexa por ellas.",
              },
              {
                key: "material",
                head: "El del material generado",
                body: "En el que se ESCRIBEN los ejercicios. No lo elige nadie: sale del contexto de la asignatura, que a su vez sale de tus apuntes.",
              },
            ]}
          />
          <p>
            Se cruzan sin problema. Puedes leer en inglés una instancia cuyos prompts van en
            español y que produce ejercicios en español, y las tres decisiones siguen siendo
            independientes.
          </p>
        </Detail>
      </Block>

      <Block title="Dos cosas que sorprenden">
        <Alert tone="info" title="El usuario no se puede cambiar">
          <p>
            Es lo que identifica todo lo que has hecho: cada ejercicio, cada sesión de evaluación y
            cada línea del registro apuntan a él. El nombre visible sí se cambia cuando quieras.
          </p>
        </Alert>
        <Alert tone="info" title="Cambiar la contraseña cierra el resto de sesiones">
          <p>
            Todas menos esta pestaña. Es lo que se quiere casi siempre que se cambia una
            contraseña, y por eso no hay una lista de sesiones abiertas que gestionar aparte.
          </p>
        </Alert>
      </Block>

      <Block title="Cómo se entra aquí">
        <Paragraph>
          No hay registro abierto. Una cuenta existe porque alguien te pasó un{" "}
          <strong>enlace de invitación de un solo uso</strong> y tú elegiste tu nombre de usuario
          al abrirlo. Ese enlace <em>es</em> la invitación: no está atado a ningún correo, así que
          no lo dejes en un sitio compartido. Al abrirlo eliges también tu contraseña —la que
          quieras, o la que te sugiera tu gestor— y dices si das clase o si estudias.
        </Paragraph>
        <Paragraph>
          La invitación puede traer ya una asignatura y un papel dentro de ella, o no traer
          ninguna: en ese caso entras igual y se te ofrece crear la tuya. Una cuenta sin
          asignatura es una cuenta normal, no una cuenta a medio hacer.
        </Paragraph>
      </Block>

      <Block title="Concepto claro, oscuro o como el sistema">
        <Paragraph>
          Tres botones en el mismo menú del avatar. Es una propiedad de la pantalla y no de la
          cuenta: se guarda por navegador, porque la misma persona lee esto en un portátil al sol
          y en un escritorio a oscuras.
        </Paragraph>
      </Block>

      <Block title={t("admin.title")}>
        <Badge variant="secondary">solo administradores</Badge>
        <Paragraph>
          La instalación vista desde fuera, en cinco pestañas: «{t("admin.tab.evaluation")}» (el
          estudio), «{t("admin.tab.accounts")}» (invitaciones, papeles, desbloqueos), «
          {t("admin.tab.workspaces")}» (espacio en disco, exportar, borrar), «
          {t("admin.tab.engine")}» y «{t("admin.tab.config")}» (todos los ajustes, cada uno con
          lo que costó medirlo y con lo que invalidará al guardarlo). Tiene sección propia aquí
          al lado: «{t("guide.sec.admin")}».
        </Paragraph>
      </Block>

      <Block title="Cerrar la instalación mientras se toca">
        <Badge variant="secondary">solo administradores</Badge>
        <Paragraph>
          Arriba del todo de «{t("admin.title")}», por encima de las pestañas y no dentro de
          ninguna, hay un interruptor de <strong>«{t("maint.title")}»</strong>. Cerrado,
          cualquier otra cuenta ve una pantalla de aviso en lugar de la aplicación —con el texto
          que se escriba ahí— y la API rechaza sus peticiones; quien administra sigue entrando,
          que es lo que permite volver a abrirla.
        </Paragraph>
        <Paragraph>
          Sirve para aplicar cambios sin que nadie se quede a medias: actualizar el servidor,
          migrar la base de datos, cambiar de motor. Mientras esté cerrada, la cabecera lo
          recuerda en rojo en todas tus pantallas, porque el riesgo real no es no enterarse: es
          olvidarse de reabrirla.
        </Paragraph>
      </Block>
    </div>
  );
}

function Admin() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.daily")} title={t("guide.sec.admin")}>
        <p>
          La instalación vista desde fuera: quién existe, dónde entra cada cual, qué pesan las
          instancias y qué está haciendo la máquina. Vive detrás del avatar, en{" "}
          <strong>«{t("admin.title")}»</strong>, y solo la ve quien administra la instalación.
        </p>
        <p>
          Son cinco pestañas, y esta sección las cubre todas. La de «
          {t("admin.tab.evaluation")}» reúne lo que ha contestado la gente, en dos bloques: las
          comparaciones a ciegas de la fase de pruebas, con sus recuentos y sus contrastes, y los
          formularios que cierran cada paso de la fase de construcción, resumidos paso a paso.
          Arriba de los dos va un solo filtro —una cuenta, un tipo de cuenta (docentes o
          alumnos) y una asignatura— que acota ambos bloques a la vez, y cada bloque descarga
          en CSV exactamente lo que muestra.
        </p>
      </SectionHead>

      <Block title={t("admin.tab.accounts")}>
        <Paragraph>
          Aquí se decide quién existe y dónde entra. <strong>No hay registro abierto</strong>, y
          es una decisión, no una carencia: una cuenta existe porque alguien abrió un enlace de
          invitación de un solo uso, o porque se creó desde la línea de órdenes. El enlace{" "}
          <em>es</em> la invitación y no va atado a ningún correo, así que se pasa a mano y no se
          deja en un sitio compartido. Quien lo abre elige su usuario, su contraseña y si da
          clase o si estudia.
        </Paragraph>
        <Paragraph>
          La invitación puede traer ya una asignatura y un permiso dentro de ella, o no traer
          ninguna. Los accesos se dan y se quitan después, cuenta por cuenta y asignatura por
          asignatura, desde esta misma tabla; son tres:
        </Paragraph>
        <Rows
          items={[
            { key: "viewer", head: t("role.viewer"), body: t("role.viewer.hint") },
            { key: "editor", head: t("role.editor"), body: t("role.editor.hint") },
            { key: "owner", head: t("role.owner"), body: t("role.owner.hint") },
          ]}
        />
        <Paragraph>Y aparte de los accesos, cada fila ofrece cuatro cosas más:</Paragraph>
        <Rows
          items={[
            {
              key: "admin",
              head: <>«{t("acc.makeAdmin")}»</>,
              body: "Quien administra entra en todas las asignaturas sin ser miembro de ninguna. No se puede quitar a uno mismo: es lo que impide que la instalación se quede sin nadie que la administre.",
            },
            {
              key: "reset",
              head: <>«{t("acc.resetLink")}»</>,
              body: "Un enlace para poner una contraseña nueva, generado aquí para pasárselo a mano: la pantalla de entrada no ofrece ninguna forma de pedirlo. Vale unos minutos y una sola vez.",
            },
            {
              key: "unlock",
              head: <>«{t("acc.badge.locked")}»</>,
              body: "Tras varios intentos fallidos, el limitador cierra el login de esa cuenta un rato. Desde aquí se abre sin esperar, y desde aquí se le cierran también todas las sesiones abiertas.",
            },
            {
              key: "perfil",
              head: <>«{t("acc.profileLabel")}»</>,
              body: "Docente o alumno. Decide con qué palabras se le pregunta al comparar propuestas y cómo agrupa el estudio sus respuestas; no da ni quita ningún permiso, y por eso se corrige aquí sin más trámite.",
            },
            {
              key: "sesiones",
              head: <>«{t("acc.seeSessions")}»</>,
              body: "Solo si esa cuenta ha evaluado algo: salta a «Evaluaciones» con el filtro ya puesto en ella.",
            },
          ]}
        />
      </Block>

      <Block title="Cerrar una cuenta: dos cosas distintas">
        <Rows
          items={[
            {
              key: "desactivar",
              head: <>«{t("acc.deactivate")}»</>,
              body: "Le cierra la puerta sin borrar nada. Deja de poder entrar y todo lo suyo sigue donde estaba, con su nombre. Es lo que se hace cuando alguien deja de participar.",
            },
            {
              key: "eliminar",
              head: <>«{t("common.delete")}»</>,
              body: "Borra la cuenta de verdad, y no se puede deshacer. Lo que produjo NO se va con ella: los ejercicios generados y las sesiones de evaluación se quedan, sin autor. Un curso preparado sobre ese material no se cae porque se dé de baja a quien lo generó, y el estudio no pierde las comparaciones que contó.",
            },
          ]}
        />
        <Paragraph>
          Ninguna de las dos se ofrece sobre tu propia fila, y «{t("acc.makeAdmin")}» tampoco:
          es lo que impide que la instalación se quede sin nadie que la administre.
        </Paragraph>
      </Block>

      <Block title={t("admin.tab.workspaces")}>
        <Paragraph>
          Todas las instancias de la instalación con sus miembros, sus ejercicios y el estado de
          su cadena. Lo que pesa cada una va repartido por papel —{t("ws.disk.raw")},{" "}
          {t("ws.disk.instance")}, {t("ws.disk.cache")} e {t("ws.disk.history")}—, que es la
          única forma de ver que lo caro casi nunca son los artefactos.
        </Paragraph>
        <Rows
          items={[
            {
              key: "cache",
              head: "Vaciar la caché",
              body: "Borra solo los vectores y el markdown convertido, que el próximo trabajo vuelve a calcular. Las descripciones de conceptos y su anclaje a tus apuntes se quedan: los escribió el modelo leyéndolos y cuestan una pasada larga.",
            },
            {
              key: "export",
              head: "Exportar",
              body: "Descarga la instancia tal como está en los ficheros —artefactos, contexto, aprobaciones y currículo— en un único JSON.",
            },
            {
              key: "borrar",
              head: "Borrar",
              body: "Borrar una asignatura desde aquí se lleva también su árbol de ficheros del disco, los documentos en bruto incluidos. El diálogo enumera lo que desaparece y hay que escribir el identificador de la instancia para confirmarlo. Sobre la única asignatura que quede no se ofrece.",
            },
          ]}
        />
        <Paragraph>
          <strong>Vaciar un paso concreto</strong> se hace desde su propio distintivo en la
          columna del recorrido: se pulsa el del paso y se confirma. No toca el historial, así
          que si te equivocas se restaura desde la pantalla de ese mismo paso.
        </Paragraph>
      </Block>

      <Block title={t("admin.tab.engine")}>
        <Paragraph>
          Es un motor con tantas mitades como tenga. Con uno solo es un panel sobre una máquina y
          no lleva ni títulos: «{t("eng.half.local")}» sin un «{t("eng.half.remote")}» al lado no
          divide nada. Con el motor partido aparecen tres secciones con su raya.
        </Paragraph>
        <Rows
          items={[
            {
              key: "local",
              head: t("eng.half.local"),
              body: (
                <>
                  {t("eng.half.localNote")}. El túnel SSH hasta la máquina de la GPU, que se
                  levanta y se para desde aquí y guarda las últimas líneas de error de ssh; los
                  modelos residentes y cómo se reparten la VRAM; y los que hay en disco, con sus
                  descargas.
                </>
              ),
            },
            {
              key: "remote",
              head: t("eng.half.remote"),
              body: (
                <>
                  {t("eng.half.remoteNote")}: medidores por minuto y por día, y bajo ellos el
                  desglose de lo gastado por fase, que se descarga en CSV.
                </>
              ),
            },
            {
              key: "process",
              head: t("eng.half.process"),
              body: (
                <>
                  {t("eng.half.processNote")}. La cola entera de la instalación, de todas las
                  asignaturas: lo que se está ejecutando, lo que espera y de quién es cada cosa.
                </>
              ),
            },
          ]}
        />
        <Detail title="Tres cosas que el panel se niega a hacer">
          <p>
            <strong>Borrar un modelo que la configuración nombra.</strong> Te dice qué ajustes lo
            piden: cámbialos antes.
          </p>
          <p>
            <strong>Meter una descarga en la cola.</strong> Descargar un modelo es red y disco,
            nunca la GPU, así que corre al lado de la cola y no detrás de una construcción de dos
            horas.
          </p>
          <p>
            <strong>Liberar la GPU o invalidar un contexto con un trabajo en curso.</strong> Sería
            quitarle los pesos de debajo a algo que está corriendo.
          </p>
        </Detail>
      </Block>

      <Block title={t("admin.tab.config")}>
        <Paragraph>
          Todos los ajustes de la instalación, cada uno con la medición que lo justifica al lado,
          repartidos en secciones con su propio índice y su <strong>buscador</strong> — que es lo
          que hace encontrable un ajuste del que solo recuerdas media palabra.
        </Paragraph>
        <Paragraph>
          Cada fila dice de dónde sale su valor —«{t("cfg.source.default")}», «
          {t("cfg.source.file")}» o «{t("cfg.source.env")}»— y lo que fija el entorno gana
          siempre: ahí el control se muestra desactivado y dice quién lo fija, en vez de dejarte
          editar algo que se va a sobrescribir. Solo lo que está «{t("cfg.source.file")}» y
          difiere del valor de fábrica ofrece volver a él.
        </Paragraph>
        <Paragraph>
          Lo que hace útil esta pantalla es que{" "}
          <strong>dice lo que va a invalidar antes de guardar</strong>, y no veinte minutos
          después. Tocar la ventana de contexto de un modelo obliga a reconstruir los contextos
          calientes; tocar el modelo de embeddings vuelve a embeber el índice de conceptos
          entero; tocar el motor reinicia la conexión. Los avisos salen en «
          {t("cfg.beforeSaving")}», junto a la lista de cambios pendientes.
        </Paragraph>
        <Paragraph>
          El razonamiento no es un interruptor global sino uno <strong>por fase</strong>, y se
          dibuja como lo que es: cuatro columnas que se leen de arriba abajo —las tres
          construcciones y la generación— y cada parada, una llamada al modelo. Bajo el nombre de
          la parada, qué modelo la atiende; el círculo dice si razona antes de contestar y,
          mientras razona, el selector de al lado fija cuánto. Tres paradas no llevan interruptor
          y lo dicen con el círculo a trazos: el guardián porque su modelo no razona, el ejercicio
          porque eso lo decide cada encargo, y la reparación porque va con gramática y con
          gramática no se puede razonar.
        </Paragraph>
      </Block>
    </div>
  );
}

const problems = (
  t: Translate["t"],
): { key: string; question: string; answer: ReactNode }[] => [
  {
    key: "mantenimiento",
    question: `«${t("maintenance.title")}»`,
    answer: (
      <>
        <p>
          No es un fallo: quien administra la instalación la ha cerrado a propósito para
          aplicar cambios. El aviso dice desde cuándo, y lo tuyo sigue donde estaba —
          artefactos, ejercicios y evaluaciones se leen igual cuando vuelva a abrirse.
        </p>
        <p>
          No hay hora prevista de vuelta, y no la hay porque nadie la sabe. «
          {t("maintenance.checkAgain")}» vuelve a preguntar; la pantalla también lo hace sola
          cada pocos segundos.
        </p>
      </>
    ),
  },
  {
    key: "ollama",
    question: "«Ollama no responde en …»",
    answer: (
      <>
        <p>
          El motor de inferencia no está accesible. Lo ya construido se sigue leyendo entero; lo
          que falla es arrancar cualquier trabajo nuevo.
        </p>
        <p>
          Si la GPU está en otra máquina, mira Administración → Motor: el túnel SSH se levanta y
          se para desde ahí, y guarda las últimas líneas de error, que es donde se ve un problema
          de clave.
        </p>
      </>
    ),
  },
  {
    key: "cerebras",
    question: `«${t("cere.refusing")}»`,
    answer: (
      <>
        <p>
          Tampoco es un fallo. El motor remoto trabaja con dos cuotas —una por minuto y otra por
          día— y el aviso dice cuál se ha agotado y cuánto falta para que se libere. La del
          minuto se espera sola, sin que tengas que hacer nada; la del día no, porque dejar un
          trabajo colgado horas sin explicación es peor que rechazarlo.
        </p>
        <p>
          Las salidas son tres: esperar, cambiar el motor a «ollama», o subir el techo si la
          cuenta de verdad da para más. Las tres se hacen en Administración → Motor, donde los
          ajustes están en la columna de la derecha, al lado de los medidores que los explican.
        </p>
        <p>
          Hay un tercer caso que no es de cuota gastada sino de tamaño: una llamada que necesita
          más tokens de los que cabe la ventana entera se rechaza al momento, porque no cabe por
          más que se espere.
        </p>
        <p>
          Lo que <strong>no</strong> hace es pasarse solo al motor local. Cambiaría en silencio
          qué motor produjo un artefacto, y eso hay que poder decirlo.
        </p>
      </>
    ),
  },
  {
    key: "modelo",
    question: `Un modelo aparece como «${t("model.notInstalled")}»`,
    answer: (
      <p>
        Solo fallan los trabajos que usan ese modelo; el resto de la cadena funciona. Se descarga
        desde Administración → Motor, y la descarga corre al lado de la cola, no dentro: no tiene
        que esperar a que termine una construcción de dos horas.
      </p>
    ),
  },
  {
    key: "obsoleto",
    question: `Un paso dice «${t(STATUS.stale.labelKey)}»`,
    answer: (
      <>
        <p>
          Algo de lo que depende cambió después de que lo cerraras. Ábrelo, comprueba que sigue
          valiendo —o corrígelo— y vuélvelo a cerrar continuando al siguiente. Mientras tanto,
          los pasos que dependen de él quedan bloqueados.
        </p>
        <p>
          Si lo que cambió son los documentos —subiste más ejercicios o más apuntes después de
          construirlo, o quitaste alguno—, el aviso nombra cuáles y ofrece «
          {t("build.rebuild")}»: se lee otra vez todo lo que hay ahora y el resultado sustituye
          al actual. Las correcciones hechas a mano en ese paso se pierden; la versión anterior
          queda en el historial. Si prefieres seguir con lo que hay, cierra el paso continuando
          y el aviso desaparece hasta el próximo cambio.
        </p>
      </>
    ),
  },
  {
    key: "bloqueado",
    question: `Un paso dice «${t(STATUS.blocked.labelKey)}»`,
    answer: (
      <p>
        No es «no está hecho», es «no te toca todavía»: falta cerrar algo de lo que depende. La
        propia pantalla dice cuál, con enlace.
      </p>
    ),
  },
  {
    key: "solo-lectura",
    question: "No me deja cambiar nada",
    answer: (
      <>
        <p>
          Son dos situaciones distintas y se salen por sitios distintos. Si el paso está{" "}
          <strong>abierto</strong>, lo que pasa es que estás <em>mirándolo</em>: cada paso se
          abre en modo lectura, y la edición se desbloquea con «{t("stage.curate.start")}», al
          final de la pantalla. Nada está mal — simplemente todavía no has pedido corregir.
        </p>
        <p>
          Si el paso está <strong>cerrado</strong>, la puerta es la misma: «
          {t("stage.curate.start")}» al final de la pantalla. Lo que se dio por bueno es el
          fichero tal cual está, así que el primer cambio que guardes lo vuelve a abrir —sin
          borrar ni reconstruir nada— y volver a cerrarlo es continuar otra vez al paso
          siguiente.
        </p>
        <p>
          La descripción de un concepto se puede corregir con el paso cerrado: vive en un fichero
          aparte y no caduca nada.
        </p>
      </>
    ),
  },
  {
    key: "boton",
    question: "El botón de construir está apagado",
    answer: (
      <>
        <p>
          Pasa el cursor por encima: dice el motivo. Son cinco, y se comprueban en este orden —
          tu permiso sobre esta asignatura es de solo lectura; el paso anterior no está cerrado;
          el origen del Paso {stepNumber(0)} no tiene ningún documento; el motor no responde; o
          esta misma construcción ya está en cola. Si es la del material, el enlace del propio
          aviso lleva a subirlo.
        </p>
        <p>
          Que haya <em>otro</em> trabajo corriendo no es motivo: la construcción se pone en cola
          detrás de él y el botón dice cuántos tiene por delante.
        </p>
      </>
    ),
  },
  {
    key: "sin-concepto",
    question: "Hay ejercicios míos sin ningún concepto",
    answer: (
      <p>
        Es normal en la primera pasada. Pulsa «{t("stage.curate.start")}» y usa «
        {t("bank.retagUntagged", { n: "N" })}»: se lanza solo sobre esos, nunca sobre todos. Y
        tiene sentido repetir, porque el emparejamiento mejora con cada ejercicio bien
        etiquetado. Si uno sigue resistiéndose, ponle el concepto a mano.
      </p>
    ),
  },
  {
    key: "bloqueadas",
    question: "Mis instrucciones adicionales salen bloqueadas",
    answer: (
      <p>
        El aviso aparece bajo el propio cuadro de instrucciones y el botón de generar queda
        bloqueado hasta que las cambies. Dice cuál de los dos filtros ha sido: si es el de
        admisibilidad, te nombra el control de arriba que ya decide eso, así que cámbialo ahí en
        vez de pedirlo por escrito; si es el guardarraíl, te dice bajo qué criterio.
      </p>
    ),
  },
  {
    key: "horas",
    question: "Llevo horas y no sé si está avanzando",
    answer: (
      <p>
        La construcción del grafo es el trabajo más caro del recorrido. En su propia pantalla,
        la barra por fases dice en cuál está: el tramo que se mueve es el que corre, y debajo va
        el nombre de lo que se está haciendo ahora mismo. Puedes cerrar la pestaña y volver más
        tarde.
      </p>
    ),
  },
];

function Troubleshooting() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.daily")} title={t("guide.sec.troubleshooting")}>
        <p>
          Casi nada de lo que aparece aquí rompe nada: lo ya construido se sigue leyendo siempre.
          Lo que falla es arrancar trabajo nuevo.
        </p>
      </SectionHead>

      <div className="space-y-2">
        {problems(t).map((problem) => (
          <Detail key={problem.key} title={problem.question}>
            {problem.answer}
          </Detail>
        ))}
      </div>

      <Alert tone="info" title="Regla general: pasa el cursor por encima de lo que está apagado">
        <p>
          Ningún control desactivado se queda callado en esta aplicación. El botón de construir
          decide en un único sitio todas las razones para no ofrecerse —permiso de solo lectura,
          el paso anterior sin cerrar, el origen del Paso {stepNumber(0)} vacío, el motor sin
          responder, esa misma construcción ya en cola— y las dice en su propio tooltip. Que haya
          otro trabajo corriendo no está en la lista: eso se resuelve esperando turno, y el botón
          lo cuenta.
        </p>
      </Alert>
    </div>
  );
}

export const BODIES: Record<string, () => ReactNode> = {
  start: Start,
  workspace: Workspace,
  raw: Raw,
  profile: Profile,
  graph: Graph,
  bank: Bank,
  generate: Generate,
  evaluate: Evaluate,
  runs: Runs,
  account: Account,
  admin: Admin,
  troubleshooting: Troubleshooting,
};
