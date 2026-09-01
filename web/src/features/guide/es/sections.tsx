import { Play, Scale, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Alert, PhaseBar, Skeleton } from "@/components/ui/misc";
import { StatusMark } from "@/components/ui/status";
import { STATUS, type StatusKey } from "@/lib/status";
import { ARM_META } from "@/study/arms";
import { STEPS } from "@/lib/steps";
import { useT, type Translate } from "@/lib/i18n";
import { useBuildPhases } from "@/state/queries";
import { Block, Detail, Facts, Paragraph, Rows, SectionHead, Steps } from "../blocks";

const STATE_ORDER: StatusKey[] = ["approved", "draft", "stale", "building", "missing", "blocked"];

const STATE_HINTS: Record<StatusKey, string> = {
  approved: "Cerrado y contado como bueno. Es lo que desbloquea la etapa siguiente.",
  draft: "Construido pero sin revisar. Se puede editar; todavía no cuenta.",
  stale:
    "Algo de lo que depende cambió después de aprobarlo. Hay que reconstruir o volver a aprobar.",
  building:
    "La pantalla dice cuál de tres cosas pasa: se construye por primera vez y no hay nada que reemplazar; se trabaja sobre lo que ya hay, que sigue guardado y solo deja de verse; o el trabajo sigue en cola y todavía no ha empezado, y entonces no hay barra.",
  missing: "Todavía no existe. La pantalla enseña la cabecera y un único botón: construir.",
  blocked: "No es «no está hecho», es «no te toca todavía»: falta aprobar algo de lo que depende.",
};

const ARM_ORDER = ["naive", "rag", "system"] as const;

/**
 * El plan real del constructor del temario, leído de la API como lo lee el panel.
 *
 * Estuvo copiado a mano en este fichero y se quedó atrás: dibujaba la conversión al 10 %
 * cuando pesa un tercio, y no dibujaba la fase de contexto en absoluto. La guía lee las
 * fuentes de la aplicación en vez de repetirlas, así que aquí tampoco hay respaldo escrito
 * a mano: sin plan, un esqueleto.
 */
function BuildPlanBar() {
  const phases = useBuildPhases("knowledge_graph");
  if (!phases.length) return <Skeleton className="h-1.5 w-full" />;
  return <PhaseBar phases={phases} percent={58} activeKey="clean" />;
}

function Pill({ icon: Icon, label, tone }: { icon: LucideIcon; label: string; tone?: "study" }) {
  return (
    <span
      className={
        tone === "study"
          ? "flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-small font-medium text-study ring-1 ring-inset ring-[color-mix(in_oklch,var(--study)_30%,transparent)] bg-[color-mix(in_oklch,var(--study)_9%,transparent)]"
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
          problemas, tareas de evaluación— anclados al temario de una asignatura. No escribe sobre un tema
          en abstracto: parte de los tres pasos con los que describes tu asignatura y produce variantes
          que respetan lo que el alumno ya ha visto y lo que todavía no.
        </p>
      </SectionHead>

      <Block title="El recorrido, de un vistazo">
        {/* Es la barra de arriba, dibujada aquí: cuatro pasos numerados y las dos cosas que
            se hacen con lo que producen. El raíl que había antes se fue con el panel — lo
            que codificaba, la dependencia entre etapas, lo dicen ahora los números. */}
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card p-4 sm:p-6">
          {STEPS.map((step, index) => (
            <div key={step.path} className="flex items-center gap-2">
              <span className="nums flex size-6 shrink-0 items-center justify-center bg-primary font-condensed text-small font-semibold text-primary-foreground">
                {index + 1}
              </span>
              <span className="text-body font-medium">{t(step.labelKey)}</span>
            </div>
          ))}
          <span aria-hidden className="mx-1 h-6 w-px bg-border" />
          <Pill icon={Play} label={t("nav.create")} />
          <Pill icon={Scale} label={t("nav.compare")} tone="study" />
        </div>
        <Paragraph>
          Es exactamente la barra de arriba. Los cuatro pasos se hacen en ese orden y cada uno lleva debajo una palabra diciendo dónde estás: <em>hecho</em>, <em>te toca ahora</em> o <em>después</em>. Las dos píldoras de la derecha no son pasos: son lo que se hace con lo que los pasos producen, y se abren cuando los cuatro están dados.
        </Paragraph>
      </Block>

      <Rows
        items={[
          {
            key: "perfil",
            head: t("artifact.profile"),
            body: "Qué es un ejercicio aquí: sus campos, sus tipos y las guías que el modelo sigue.",
          },
          {
            key: "temario",
            head: t("artifact.graph"),
            body: "El vocabulario: conceptos, dominios y las relaciones entre ellos.",
          },
          {
            key: "banco",
            head: t("artifact.bank"),
            body: "Ejercicios reales de tu asignatura, ya etiquetados con conceptos del temario.",
          },
        ]}
      />

      <Alert tone="info" title="Se empieza por el perfil, no por el temario">
        <p>
          Un temario se puede construir sin nada más, pero su revisión de qué conceptos sirven de etiqueta necesita
          el perfil <em>aprobado</em>. Empezar por el temario es empezar por una etapa que no
          puedes terminar.
        </p>
      </Alert>

      <Block title="La primera media hora">
        <Steps
          items={[
            <>
              Ponte en un <strong>workspace</strong>. Si aún no tienes ninguno, el panel te
              ofrece crear el tuyo; si tienes varios, se cambia en el selector de arriba a la
              izquierda. Todo lo demás vive dentro de uno.
            </>,
            <>
              Desde <strong>«{t("dash.rawData")}»</strong>, en la navegación, sube el material:
              los documentos con ejercicios de ejemplo y los apuntes de la asignatura.
            </>,
            <>
              En esa misma pantalla, lanza la <strong>transcripción</strong> de cada origen. No
              es obligatoria —si no la haces, cada construcción transcribe lo suyo por el
              camino—, pero es el trabajo mecánico que abre las tres: hecho una vez, deja de
              pagarse al principio de cada una. Y es donde puedes leer y corregir a mano una
              página que haya salido mal.
            </>,
            <>
              Construye el <strong>perfil</strong>, revísalo campo a campo y apruébalo.
            </>,
            <>
              Lanza el <strong>temario</strong>. Es el trabajo más caro de la cadena: puedes
              cerrar la pestaña, el servidor sigue.
            </>,
            <>
              Marca <strong>qué conceptos sirven de etiqueta</strong>, repasa las
              <strong> descripciones</strong> y apruébalo.
            </>,
            <>
              Extrae el <strong>banco</strong>, repasa los ejercicios que se quedaron sin concepto y
              apruébalo.
            </>,
            <>
              Con las tres aprobadas se abren «{t("nav.generate")}» y «{t("nav.evaluate")}».
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

      <Detail title="¿Por qué hay que aprobar cada etapa?">
        <p>
          Lo que se aprueba es el <em>hash del fichero</em>. Mientras una etapa está aprobada, su
          pantalla no ofrece ningún control que reescriba el artefacto: bajo el botón «
          {t("stage.reopen")}» lo dice con todas las letras —«{t("stage.locked")}»— y ese botón
          es el único camino de vuelta. Aprobar es lo que desbloquea la etapa siguiente y, con
          las tres, la generación.
        </p>
        <p>
          Lo que <em>no</em> reescribe el artefacto —las descripciones de conceptos y el
          currículo— sigue estando disponible con la etapa aprobada.
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
          Un <strong>workspace</strong> es una instancia completa: su material en bruto, sus tres
          artefactos, su caché y su currículo. Dos asignaturas son dos workspaces. Dos formatos
          de ejercicio muy distintos para la misma asignatura, también.
        </p>
      </SectionHead>

      <Facts
        items={[
          { label: "Dónde se cambia", value: "El selector de arriba a la izquierda, junto a la marca." },
          { label: "Quién puede crear uno", value: "Cualquier cuenta, y queda como su propietaria." },
          { label: "Si no tienes ninguno", value: "El panel te ofrece crearlo. No hay ninguno por defecto." },
          { label: "Qué se lleva al cambiar", value: "Nada. Cada workspace tiene lo suyo, incluida su caché." },
          {
            label: "Qué se decide al crearlo",
            value: "El idioma de los prompts. Después ya no se puede cambiar.",
          },
        ]}
      />

      <Block title="Entrar sin ninguno es normal">
        <Paragraph>
          No hay un workspace inicial en el que caiga quien no tiene otro: una cuenta recién
          creada, o a la que todavía no le han dado acceso a nada, entra y se encuentra el{" "}
          <strong>Panel</strong> pidiéndole que cree el suyo. Basta con el nombre de la
          asignatura. Las dos salidas son igual de válidas: créalo tú y serás su propietario, o
          espera a que quien administra te dé acceso a uno que ya existe.
        </Paragraph>
        <Paragraph>
          Mientras tanto la aplicación no se queda bloqueada: esta guía, «Mi perfil» y —si
          administras la instalación— «Administración» funcionan sin ningún workspace. Lo que
          espera es todo lo que lee una instancia: las tres etapas, «Generar» y «Evaluar».
        </Paragraph>
      </Block>

      <Block title="El idioma de los prompts se elige al crearlo">
        <Paragraph>
          Al crear un workspace eliges en qué idioma se le habla al modelo durante toda la
          construcción de esa instancia. <strong>No se puede cambiar después</strong>, y no es
          una restricción caprichosa: las etiquetas de las relaciones se escriben dentro del
          propio temario y el cargador indexa por ellas, así que el idioma queda cocido en los
          artefactos desde la primera construcción. El formulario de creación lo dice ahí
          mismo.
        </Paragraph>
        <Paragraph>
          No tiene por qué coincidir con el idioma en el que tú lees la aplicación: preparar
          en español una instancia cuyos prompts van en inglés es un caso previsto, y es
          justo para eso que son dos ajustes distintos.
        </Paragraph>
      </Block>

      <Block title="Una pestaña, un workspace">
        <Paragraph>
          El workspace activo se guarda en tu cuenta y sobrevive a cerrar sesión; el que estás{" "}
          <em>mirando</em> lo guarda la pestaña. Puedes tener dos asignaturas abiertas en dos
          pestañas del mismo navegador sin que se pisen. Al cambiar de workspace la pantalla se
          vacía de lo que estabas viendo: los trabajos y el progreso pertenecen a la instancia
          que dejas.
        </Paragraph>
      </Block>

      <Block title="El contexto de la asignatura">
        <Paragraph>
          Es la prosa que dice de qué va esta instancia —materia, nivel, idioma de instrucción,
          convenciones— y entra en <em>todas</em> las llamadas al modelo. Se lee y se edita en el{" "}
          <strong>Panel</strong>, en la tarjeta «{t("context.title")}»: no es una etapa de la
          cadena y por eso no está en la barra. Debajo del párrafo van tres datos sueltos —
          {t("context.fact.subject").toLowerCase()}, {t("context.fact.level").toLowerCase()} e{" "}
          {t("context.fact.language").toLowerCase()}—, que se leen por separado y deben decir lo
          mismo que él.
        </Paragraph>
        <Alert tone="attention" title={`«${t("context.draft")}» frente a «${t("context.curated")}»`}>
          <p>
            Cada construcción escribe un borrador nuevo del contexto sin tocar el tuyo, y el
            distintivo de la tarjeta dice cuál de los dos estás leyendo. Cuando hay una síntesis
            nueva esperando aparece «{t("context.adopt")}»: adoptarla{" "}
            <strong>sustituye tu texto entero</strong> por el del último borrador, así que si
            solo quieres quedarte con una parte, cópiala tú y edita. Lo que no pasa nunca es que
            se sobreescriba sola.
          </p>
        </Alert>
      </Block>

      <Block title="Lo que ya has dado en clase">
        <Paragraph>
          Al pedir un ejercicio puedes decir qué conceptos ha visto ya la clase. Es lo que acota
          el andamiaje: de un concepto impartido el ejercicio puede apoyarse; de uno que aún no
          se ha dado, no puede depender. Se elige <em>en el encargo</em>, en «Ajustes», y vale
          para esa tanda — no se guarda en la asignatura.
        </Paragraph>
        <Alert tone="info" title="Sin marcar nada no significa «nada impartido»">
          <p>
            Significa «sin restricción». Leerlo al pie de la letra prohibiría el temario entero,
            que es justo el estado en el que arranca una instancia nueva.
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
          Los documentos de los que sale todo lo demás. Tienen pantalla propia —{" "}
          <strong>«{t("nav.rawData")}»</strong> en la navegación,{" "}
          <code className="font-mono text-small">/raw</code>— y su propia píldora, delante de
          las tres etapas y separada de ellas por una raya: el material en bruto alimenta la
          cadena sin ser un paso de ella. No escribe ningún artefacto, nadie lo aprueba y por eso
          no está en el raíl.
        </p>
      </SectionHead>

      <Facts
        items={[
          {
            label: "Qué produce",
            value: "Ningún artefacto: las páginas de cada documento pasadas a markdown, guardadas una a una.",
          },
          {
            label: "Qué cuesta",
            value: "Una llamada al modelo por página, en los dos orígenes por igual.",
          },
          {
            label: "Qué desbloquea",
            value: "Nada, y es deliberado: adelanta trabajo que las construcciones harían igualmente.",
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
          Cada tarjeta lleva bajo el título la etapa a la que alimenta, con los nombres cortos de
          la barra de arriba: «{t("nav.graph")}» para los apuntes, «{t("nav.profile")}» y «
          {t("nav.bank")}» para los ejemplares. Un origen vacío no dibuja una lista vacía: la
          tarjeta entera se convierte en la zona donde soltar los ficheros, que es lo único que
          hay que hacer ahí.
        </Paragraph>
      </Block>

      <Alert tone="info" title="Transcribir adelanta trabajo; nunca es un requisito">
        <p>
          Pasar los documentos a markdown es lo primero que hace <em>cada</em> construcción, y es
          trabajo mecánico: hacerlo aquí una vez lo saca del principio de las tres. Si construyes
          sin haber transcrito, la construcción lo hace por su cuenta y nadie te lo impide —{" "}
          <strong>nada se rechaza jamás por falta de transcripción</strong>.
        </p>
        <p>
          Por eso, mientras queden documentos sin transcribir, la píldora de «{t("nav.rawData")}»
          lleva un punto y las tres etapas de la barra de arriba se ven <em>atenuadas</em>,
          diciendo por qué al pasar el cursor. Atenuado no es desactivado: siguen siendo
          pulsables y siguen construyendo. Es una indicación de por dónde empezar, no un
          candado.
        </p>
      </Alert>

      <Block title="Dos botones, y no tienen el mismo alcance">
        <Rows
          items={[
            {
              key: "todo",
              head: <>«{t("transcribe.startAll")}»</>,
              body: "En el aviso de arriba de la pantalla. Lanza de una vez los orígenes que tengan algo que hacer, y es el camino normal.",
            },
          ]}
        />
      </Block>

      <Block title="Cómo va cada documento">
        <Rows
          items={[
            {
              key: "done",
              head: <Badge variant="settled">{t("transcribe.state.done")}</Badge>,
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
              body: "Se transcribió, pero algo de lo que dependía ha cambiado. La fila dice qué: el propio documento, la ruta de transcripción, el modelo, la resolución de render, el OCR o el prompt.",
            },
            {
              key: "failed",
              head: <Badge variant="danger">{t("transcribe.failedCount", { n: "N" })}</Badge>,
              body: "Va junto al estado, no en su lugar: un documento puede estar transcrito y al día y aun así tener páginas que el modelo no supo leer. Ese distintivo es el único aviso de que ahí falta texto, y se arregla abriendo el documento.",
            },
          ]}
        />
        <Paragraph>
          El motivo va en la fila del documento y no escondido en un recuento: «2 caducados» dice
          el estado y se calla justo la mitad sobre la que se actúa. Un estado sin motivo no es
          un estado, y lo que hay debajo es una lista de páginas que la siguiente construcción
          iba a rehacer en silencio.
        </Paragraph>
      </Block>

      <Alert tone="settled" title="Detenerla no pierde nada">
        <p>
          Las páginas se escriben documento a documento, así que una transcripción cancelada
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
            Mientras un origen se transcribe puedes revisar y corregir los documentos que ya han
            salido. El único que no se deja abrir es el que se está reescribiendo en ese
            instante: su fila lo dice con un indicador de actividad y con «
            {t("transcribe.transcribing")}» en lugar de su estado.
          </p>
        </Detail>
      </Block>

      <Detail title="Los dos orígenes van por la misma ruta, y cuesta lo que cuesta">
        <p>
          Corpus y ejemplares se transcriben con el mismo algoritmo: se dibuja cada página y se
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
 * Cómo termina cada uno de los tres pasos. Es el mismo bloque en las tres secciones porque
 * es la misma tarea: la única diferencia son las preguntas, que las escribe el servidor.
 */
function Verdict() {
  return (
    <Block title="Cómo se cierra este paso">
      <Paragraph>
        A la derecha de lo que has construido hay un cuestionario corto sobre qué tal ha
        salido. Las preguntas cambian según el paso, pero dos son siempre las mismas —cuánto
        tendrías que corregir para poder usarlo, y del 1 al 5 en conjunto—, y son las que
        permiten comparar un paso con otro.
      </Paragraph>
      <Steps
        items={[
          <>
            Mira lo que hay a la izquierda. No hace falta leerlo entero: lo que se pregunta
            es si te suena a tu asignatura.
          </>,
          <>
            Contesta las preguntas y guarda. Puedes dejarlas a medias y volver: media
            respuesta también es un dato.
          </>,
          <>
            Al guardarlas aparece el paso siguiente. Corregir a mano lo de la izquierda
            sigue disponible todo el tiempo, antes y después.
          </>,
        ]}
      />
      <Detail title="Qué se guarda exactamente">
        <p>
          Tus respuestas, con la <em>versión concreta</em> que juzgaste. Si vuelves a
          construir el paso y lo valoras otra vez, no se sobrescribe: son dos datos, porque
          «salió mal» y «lo rehíce y salió bien» son dos cosas distintas. Volver a contestar
          sobre lo mismo sí corrige tu respuesta anterior.
        </p>
        <p>
          Es lo único que te pedimos a cambio de usar esto, y es lo que se está midiendo:
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
      <SectionHead eyebrow={`${t("guide.group.prepare")} · etapa 1`} title={t("guide.sec.profile")}>
        <p>
          Define qué es un ejercicio: sus campos, sus tipos y las guías que el modelo sigue al
          extraerlos y al generarlos. Es la pieza que instancia el caso de uso — cambiar de
          perfil es cambiar de tipo de material, no de asignatura.
        </p>
      </SectionHead>

      <Facts
        items={[
          {
            label: "Qué produce",
            value: <code className="font-mono text-small">exemplars_profile.json</code>,
          },
          { label: "Qué cuesta", value: "Una pasada larga sobre una muestra de tus ejercicios, no sobre todos." },
          {
            label: "Qué desbloquea",
            value: "Recoger los ejercicios y decidir qué conceptos del temario sirven de etiqueta.",
          },
        ]}
      />

      <Block title="Cómo se hace">
        <Steps
          items={[
            <>
              Sube al hueco de ejemplares en bruto uno o varios documentos con ejercicios reales
              de la asignatura. Sin material, el botón de construir está apagado y dice por qué.
            </>,
            <>
              Pulsa «Construir». Sale un <strong>borrador</strong>, no un resultado final.
            </>,
            <>
              Repasa cada <strong>tipo de ejercicio</strong>: su descripción, su{" "}
              <strong>nivel de dificultad</strong> y, dentro de ella, cada campo — su nombre, su
              tipo, si es obligatorio y qué contiene.
            </>,
            <>
              Repasa las <strong>«{t("modality.rules")}»</strong> de cada tipo de ejercicio: son lo único
              que el perfil le dice al generador sobre la <em>forma</em> del ejercicio.
            </>,
            <>Aprueba. La etapa se cierra y la pantalla deja de ofrecer nada que la reescriba.</>,
          ]}
        />
        <Paragraph>
          El perfil se edita solo por el formulario: no hay una pestaña con el JSON en crudo.
          Arriba del todo, siempre visible, está el aviso de si el perfil <em>carga</em> — y
          mientras no cargue, guardar está desactivado, que es lo que impide dejar la instancia
          con un esquema roto.
        </Paragraph>
      </Block>

      <Block title="Las tipos de ejercicio, y por qué se notan en todas partes">
        <Paragraph>{t("modality.whatAre.body")}</Paragraph>
        <Paragraph>
          Por eso la tipo de ejercicio reaparece luego como columna y como filtro en el banco, y como
          primera pregunta del formulario de generación. Un perfil con una sola tipo de ejercicio no
          dibuja ninguno de los dos: un desplegable de una única opción no elige nada.
        </Paragraph>
      </Block>

      <Block title="El nivel de dificultad, que lo llevan todos">
        <Paragraph>
          Todos los tipos de ejercicio llevan un <strong>nivel de dificultad</strong>, y no es un
          campo más: no se añade, no se quita y no se le cambia el nombre. Se edita arriba, en
          «{t("modality.identity")}», justo debajo de la descripción del tipo.
        </Paragraph>
        <Paragraph>
          Los <strong>tres niveles son los mismos en todos los tipos</strong>. Eso es lo que
          hace que «avanzado» signifique lo mismo en una pregunta de test y en un ejercicio de
          programación, que la columna del banco se pueda leer de un vistazo y que se pueda
          ordenar por ella. Lo que cambia de un tipo a otro es <em>qué hace</em> que un
          ejercicio caiga en cada nivel, y eso es lo único que escribes tú.
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
              key: "tema",
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

      <Block title="Qué tiene un campo">
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
              body: "El que lleva el enunciado. Es el que se convierte en vector para emparejar con conceptos, y solo puede serlo un campo de texto.",
            },
          ]}
        />
      </Block>

      <Alert tone="danger" title="Tocarlo después de extraer el banco lo invalida">
        <p>
          Los ejercicios del banco se extrajeron contra el esquema anterior. Si cambias los campos, el
          banco pasa a «Obsoleto» y hay que volver a extraerlo.
        </p>
      </Alert>

      <Detail title="El borrador no es estable, y conviene saberlo">
        <p>
          El perfil se infiere de una muestra de tus ejercicios, y ha producido conjuntos de
          campos <em>distintos</em> en dos pasadas sobre el mismo material. Trátalo como un punto
          de partida: la versión que apruebas es tuya, no suya.
        </p>
        <p>Si vuelves a construirlo, compáralo antes de sustituir el que ya tenías.</p>
      </Detail>
      <Verdict />
    </div>
  );
}

function Graph() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={`${t("guide.group.prepare")} · etapa 2`} title={t("guide.sec.graph")}>
        <p>
          El vocabulario del sistema. Todo lo que se etiquete y se genere después sale de aquí:
          ni el modelo ni tú podéis usar un concepto que no esté en el temario.
        </p>
      </SectionHead>

      <Facts
        items={[
          {
            label: "Qué produce",
            value: <code className="font-mono text-small">knowledge_graph.json</code>,
          },
          {
            label: "Qué cuesta",
            value:
              "Es el trabajo más caro de la cadena: una llamada por página de tus apuntes y unas cuantas que razonan sobre el inventario entero.",
          },
          { label: "Qué desbloquea", value: "El etiquetado del banco, el currículo y la generación." },
        ]}
      />

      <Block title="Una lista, y un mapa debajo">
        <Paragraph>
          Lo primero que ves es el temario: las unidades en el orden en que se dan, plegadas.
          Ábrelas, o busca y se abren solas las que tengan resultados. Cada fila lleva el tema
          y si <strong>sirve de etiqueta</strong>; al pulsarla se abre su ficha sobre la
          página, que es donde se corrige el nombre, la unidad, la descripción y las
          relaciones.
        </Paragraph>
        <Paragraph>
          El mapa va plegado bajo la lista, porque lo primero que se ve del temario tiene que
          ser el temario y no su dibujo. {t("kg.mapDescription")} Con el botón de ampliar se abre
          a pantalla completa <em>con la ficha al lado</em>, para poder cambiar lo que elijas sin
          volver atrás.
        </Paragraph>
        <Paragraph>
          El lienzo tiene dos disposiciones: <strong>«{t("canvas.layout.force")}»</strong>, que
          agrupa cada concepto junto a aquellos con los que se relaciona, y{" "}
          <strong>«{t("canvas.layout.curriculum")}»</strong>, que ordena por niveles de
          prerrequisito. Cambiar de una a otra no reconstruye nada: los nodos se desplazan hasta
          su nueva posición. Un nivel es una <em>banda</em> y no una fila, porque un temario
          real reparte los prerrequisitos de forma muy desigual; si hay menos de tres niveles el
          propio lienzo lo dice, porque eso es un dato sobre el temario y no una vista rota.
        </Paragraph>
      </Block>

      <Block title="Después de construir, tres cosas que mirar">
        <Steps
          items={[
            <>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                Etiquetabilidad
                <Badge variant="attention">necesita el perfil aprobado</Badge>
              </p>
              <p className="text-small text-muted-foreground">
                Qué conceptos sirven de <em>etiqueta</em>. Los que valdrían para cualquier ejercicio
                —«codificación», «diseño»— se marcan como que NO sirven de etiqueta: siguen existiendo y
                siguen funcionando a través de sus relaciones, simplemente dejan de poder ser el
                tema de un ejercicio. Ante la duda se excluye: una etiqueta vaga contamina el
                banco entero.
              </p>
            </>,
            <>
              <p className="font-medium">Descripciones</p>
              <p className="text-small text-muted-foreground">
                La prosa que describe cada concepto, escrita contra los párrafos de tus apuntes de
                los que salió. <strong>Es el texto contra el que se compara, no el nombre.</strong>{" "}
                Se escriben solas después de construir; se corrigen en la ficha del concepto,
                que es donde se están leyendo.
              </p>
            </>,
            <>
              <p className="font-medium">Curación a mano</p>
              <p className="text-small text-muted-foreground">
                Renombrar lo que quedó torcido, borrar lo que no es un concepto de la materia y
                arreglar relaciones. Renombrar arrastra consigo el anclaje a tus apuntes; borrar lo
                suelta.
              </p>
            </>,
          ]}
        />
      </Block>

      <div className="space-y-2">
        <Detail title="Por qué no se empareja por el nombre del concepto">
          <p>
            Un nombre es una etiqueta de dos palabras y no dice nada de qué se practica al
            usarlo. Lo que se convierte en vector es la <em>descripción</em>, fundida con el
            centro de los ejercicios del banco que ya llevan ese concepto.
          </p>
          <p>
            Por eso una descripción mal escrita se paga en cada etiquetado y en cada generación,
            y por eso conviene leerlas.
          </p>
        </Detail>

        <Detail title="Prerrequisitos: lo que se da por sabido y lo que se prohíbe">
          <p>
            Alrededor de los conceptos que pides, el sistema deriva dos listas del temario y las
            mete en el prompt:
          </p>
          <Rows
            items={[
              {
                key: "sabido",
                head: <span className="text-settled">Se da por sabido</span>,
                body: "Prerrequisitos que además están en el currículo. El ejercicio puede apoyarse en ellos, pero no puede convertirlos en la dificultad. Van con su descripción, no con su nombre a secas.",
              },
              {
                key: "prohibido",
                head: <span className="text-destructive">Prohibido</span>,
                body: "Lo que va después del objetivo y todavía no se ha impartido. No puede aparecer.",
              },
            ]}
          />
          <p>
            Las dos listas recorren el temario entero, no un salto: son cierres transitivos
            acotados por el currículo. En la pantalla de generación se dibujan antes de lanzar,
            para que veas exactamente con qué va a contar el modelo.
          </p>
        </Detail>
      </div>
      <Verdict />
    </div>
  );
}

function Bank() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={`${t("guide.group.prepare")} · etapa 3`} title={t("guide.sec.bank")}>
        <p>
          Los ejercicios extraídos de tus documentos y etiquetados con conceptos del temario. Son los
          ejemplos que acompañan a cada generación: de aquí sale el «así se escriben los
          ejercicios en esta asignatura» que el modelo imita.
        </p>
      </SectionHead>

      <Facts
        items={[
          {
            label: "Qué produce",
            value: <code className="font-mono text-small">exemplars_bank.json</code>,
          },
          { label: "Qué cuesta", value: "Crece con el número de documentos: se recorren todos, uno detrás de otro." },
          { label: "Se guarda", value: "Tras cada documento. Cancelar no pierde lo ya extraído." },
        ]}
      />

      <Alert tone="info" title="Extraer y etiquetar son un solo trabajo">
        <p>
          Cada documento se etiqueta según sale del extractor, así que al terminar la extracción
          el banco ya está etiquetado: no hay un paso intermedio que lanzar. Lo que queda es
          corregir lo que salió mal, y para eso hay tres controles distintos.
        </p>
      </Alert>

      <Block title="La tira de medidores dice dos cosas distintas">
        <Rows
          items={[
            {
              key: "etiquetados",
              head: t("bank.taggedItems"),
              body: "Cuántos ejercicios del banco llevan al menos un concepto. Es el trabajo de corrección que queda por delante, y lleva al lado los dos controles que actúan sobre ese mismo número. Sólo aparece mientras falte alguno: con el banco entero etiquetado no hay nada que mirar ahí.",
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
          <em>ejercicios sin concepto</em>, el otro <em>conceptos sin ejercicio</em>. Se puede tener el
          banco entero etiquetado y media asignatura sin un solo ejemplo que imitar.
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
              Después, los que llevan <strong>un solo concepto</strong> o uno que no encaja: la
              columna de conceptos se lee de un vistazo, y ahí es donde el emparejamiento se
              equivoca sin avisar.
            </>,
            <>
              Corrige el <strong>concepto primario</strong> a mano donde haga falta: es el que
              decide con qué se compara ese ejercicio después.
            </>,
          ]}
        />
      </Block>

      <Block title="Las tres formas de re-etiquetar, que no hacen lo mismo">
        <Rows
          items={[
            {
              key: "pendientes",
              head: <>«{t("bank.retagUntagged", { n: "N" })}»</>,
              body: "Sin selección: se lanza sobre exactamente los ejercicios que se quedaron sin concepto, nunca sobre el banco entero. Está en la tira de medidores, al lado del número sobre el que actúa.",
            },
            {
              key: "todo",
              head: <>«{t("bank.retagAll")}»</>,
              body: "El banco entero, desde cero. Sobrescribe las etiquetas actuales, incluidas las que hayas corregido a mano, y por eso pide confirmación antes de lanzarse.",
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
          texto del enunciado o por id, el <strong>tipo de ejercicio</strong> —los que declara tu
          perfil, cada uno con cuántos ejercicios tiene en todo el banco—, el{" "}
          <strong>documento de origen</strong>, el <strong>nivel</strong> —los tres peldaños, cada
          uno con su cuenta— y, al final de la fila, el interruptor de{" "}
          <strong>«{t("bank.untagged")}»</strong>. Si tu perfil declara un solo tipo de ejercicio, ese
          desplegable no aparece: un menú con una única opción no filtra nada.
        </Paragraph>
        <Paragraph>
          No hay control de orden: la tabla va en el orden en que se extrajeron los ejercicios,
          que es el de sus ids. El nivel se <em>filtra</em> y no se ordena, porque con tres
          peldaños ordenar solo agrupa, y lo que se pregunta de verdad es «enséñame los
          avanzados».
        </Paragraph>
        <Paragraph>
          Filtrar por tipo de ejercicio no ha movido nada del etiquetado por conceptos, que es el
          corazón del banco: los medidores, «{t("bank.seeUntagged", { n: "N" })}», los tres
          botones de re-etiquetar, la columna de conceptos y el selector de concepto principal
          del editor siguen exactamente donde estaban.
        </Paragraph>
      </Block>

      <Detail title="Reintentar tiene sentido: el índice mejora entre pasadas">
        <p>
          Cada ejercicio bien etiquetado empuja el centro de su concepto hacia donde de verdad está,
          así que el índice de una pasada lo consume la siguiente. Un ejercicio que hoy no encuentra
          concepto puede encontrarlo mañana sin que hayas tocado nada.
        </p>
        <p>
          Por eso los rechazados se vuelven a intentar en cada pasada, en vez de quedar marcados
          como imposibles.
        </p>
      </Detail>
      <Verdict />
    </div>
  );
}

function Generate() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.use")} title={t("guide.sec.generate")}>
        <p>
          Un encargo, un lote de variantes. El formulario es un acordeón: se responde de arriba
          abajo y cada pregunta se cierra en una línea al contestarla, así que volver a cambiar
          los conceptos cuesta un clic y ningún scroll.
        </p>
        <p>
          Son <strong>hasta cinco</strong> preguntas, no siempre cinco: dos de ellas solo
          aparecen si tu instancia las necesita, y la numeración cuenta las que se dibujan.
        </p>
      </SectionHead>

      <Block title="Las preguntas, en el orden en que se hacen">
        <Steps
          items={[
            <>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                {t("form.type.title")}
                <Badge variant="outline">solo con varias tipos de ejercicio</Badge>
              </p>
              <p className="text-small text-muted-foreground">
                {t("form.type.hint")} Si tu perfil declara una sola, esta pregunta no se hace.
              </p>
            </>,
            <>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                {t("form.taught.title")}
                <Badge variant="outline">{t("common.optional")}</Badge>
              </p>
              <p className="text-small text-muted-foreground">
                Lo que la clase ya ha dado, para <em>este</em> encargo, y llega{" "}
                <strong>apagado</strong>: sin restricción. Al encenderlo eliges a mano los
                conceptos cubiertos, y valen solo para esta tirada — no se guardan en la
                asignatura. {t("form.taught.hint")}
              </p>
            </>,
            <>
              <p className="font-medium">{t("form.practise.title")}</p>
              <p className="text-small text-muted-foreground">
                {t("form.practise.hint")} Solo se ofrecen los conceptos{" "}
                <strong>que sirven de etiqueta</strong>: aquí se elige de qué va el ejercicio, y para eso un
                concepto genérico no vale.
              </p>
            </>,
            <>
              <p className="font-medium">{t("form.difficulty.title")}</p>
              <p className="text-small text-muted-foreground">
                Los tres niveles del tipo que hayas elegido, cada uno con el criterio que
                escribiste en el Paso 2 debajo, y «{t("decision.any")}» para no fijarlo. Es
                la misma escala en todos los tipos, así que pedir «avanzado» quiere decir lo
                mismo aquí que en la columna del banco.
              </p>
            </>,
            <>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                {t("form.decisions.titleMany")}
                <Badge variant="outline">solo si el perfil deja algo a tu criterio</Badge>
              </p>
              <p className="text-small text-muted-foreground">
                {t("form.decisions.hint")}
              </p>
            </>,
            <>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                {t("form.instructions.title")}
                <Badge variant="outline">{t("common.optional")}</Badge>
              </p>
              <p className="text-small text-muted-foreground">
                Texto libre para lo que ningún control de arriba decide, con un tope de 600
                caracteres que la propia caja va contando. Pasa por dos filtros antes de entrar
                en el prompt.
              </p>
            </>,
          ]}
        />
      </Block>

      <Block title="Antes de lanzar, lo que el temario va a decirle al modelo">
        <Paragraph>
          Bajo los conceptos elegidos aparece «{t("form.graphSays")}» con las dos listas que el
          prompt va a llevar: «{t("form.given")}» y «{t("form.forbidden")}». Salen del temario y del
          currículo de esta pregunta, y se ven <em>antes</em> de gastar nada.
        </Paragraph>
        <Paragraph>
          Ahí mismo se avisa de <strong>los temas sin ejemplo</strong>: si algún concepto elegido no tiene
          ningún ejemplar en el banco —o ninguno de la tipo de ejercicio pedida—, el lote se genera sin
          ejemplo que imitar y la calidad suele bajar. Hay un interruptor para ocultar de la
          lista los conceptos sin ejemplares; apagarlo es lo que permite pedirlos a sabiendas.
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
              body: "Decide si lo que pides es de este campo o de algo que ya has decidido más arriba: los conceptos, la tipo de ejercicio, los campos del ejercicio o la propia asignatura. Si lo es, te dice qué control lo decide.",
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
          No lo eliges tú, y es a propósito: lo decide la instalación. Quien la administra lo
          fija en «Configuración → Modelos ofrecidos», y el primero de esa lista es el que
          escribe todo lo que se pide desde aquí.
        </Paragraph>
        <Paragraph>
          El nombre aparece igualmente, junto a la barra de esfuerzo, porque es a lo que se
          aplica ese esfuerzo: cuántos niveles hay, y cuál conviene evitar, es cosa del modelo.
          Y queda guardado con cada variante, así que en «{t("menu.savedVariants")}» puedes
          comparar dos enunciados sabiendo qué escribió cada uno.
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
          texto según se escribe, los ejemplares del banco que se le han dado al modelo y los
          detalles técnicos de la llamada. Se abre solo mientras el trabajo corre y se cierra al
          terminar, salvo que lo toques tú.
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
                  Cada variante se guarda en «{t("menu.savedVariants")}» <em>en cuanto valida</em>,
                  con su encargo entero. Un lote cancelado a la tercera conserva tres.
                </>
              ),
            },
            {
              key: "senales",
              head: <Badge variant="attention">2 señales</Badge>,
              body: (
                <>
                  Lo que el sistema puede comprobar sin juzgar el ejercicio: si nombra algo no
                  impartido, si se parece demasiado a un ejemplo o a otra del lote, y si el
                  etiquetador la reconoce como el concepto que pediste. Las dos primeras hacen
                  que el generador <em>vuelva a intentarlo</em> antes de darte el ejercicio; lo que
                  llega marcado es lo que siguió sin salir limpio, y entonces{" "}
                  <strong>es una señal para quien lee, no un rechazo</strong>.
                </>
              ),
            },
            {
              key: "reintentada",
              head: <Badge variant="outline">{t("result.retried", { n: "N" })}</Badge>,
              body: "Cuántas veces hubo que repetir la llamada por esas dos señales. No dice que la variante esté mal: dice lo que costó.",
            },
          ]}
        />
        <Paragraph>
          Una variante sin nada que señalar lo dice igual de claro: «{t("result.noFlags")}».
        </Paragraph>
      </Block>

      <Block title="Y después">
        <Rows
          items={[
            {
              key: "cambiar",
              head: <>«{t("generate.changeCommission")}»</>,
              body: "Reabre el formulario con todo relleno y deja los resultados a la vista hasta que lanzas otra tanda. Al reabrirlo aparece además «Empezar de cero», por si lo que quieres es otro encargo y no una variación del mismo.",
            },
            {
              key: "otras",
              head: <>«{t("generate.anotherN", { n: "N" })}»</>,
              body: "Repite el mismo encargo, lote nuevo. Con un solo ejercicio la etiqueta es «Generar otra».",
            },
            {
              key: "exportar",
              head: <>«{t("generate.export")}»</>,
              body: "Un menú con tres salidas para el lote entero: copiar el JSON, descargarlo, o descargarlo como Markdown.",
            },
            {
              key: "como-esta",
              head: <>«{t("generations.moreLikeThis")}»</>,
              body: "Está en «Mis variantes» y recupera el encargo de una variante concreta, aunque sea de otro día.",
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
          El mismo encargo resuelto por tres arquitecturas distintas y presentado{" "}
          <strong>a ciegas</strong>, para que elijas sin saber cuál es cuál. Es la parte del
          sistema que sirve para medirlo, no para producir material.
        </p>
        <p>
          Tú pides la comparación y tú la juzgas: eliges de qué tema quieres el ejercicio,
          se preparan las tres versiones y las lees cuando estén.
        </p>
      </SectionHead>

      <Facts
        items={[
          {
            label: "Qué se te pide",
            value: "Leer tres propuestas, una pregunta por tarjeta y una elección.",
          },
          {
            label: "Qué produce",
            value: "Una sesión guardada con las tres propuestas y tu juicio.",
          },
          {
            label: "Qué necesitas",
            value: "Los cuatro pasos dados: las tres versiones se escriben con tu asignatura.",
          },
        ]}
      />

      <Block title="Las dos pestañas">
        <Rows
          items={[
            {
              key: "encargo",
              head: t("eval.tab.compose"),
              body: "Donde abre la pantalla. Eliges de qué tema y de qué tipo quieres el ejercicio: es el mismo formulario de «Crear ejercicios», sin dos controles —cuántos ejercicios y si el modelo razona—, porque una comparación es siempre uno por versión.",
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
          la lista con el botón de la cabecera.
        </Paragraph>
      </Block>

      <Block title="Cómo va una comparación">
        <Steps
          items={[
            <>
              Aparecen las tres propuestas, sin etiquetar y en un orden que es solo tuyo.
            </>,
            <>
              <strong>Respondes una pregunta por tarjeta</strong>: si la pondrías en clase —
              o, si eres alumno, si te serviría para practicar. Un clic, primera impresión, sin
              darle vueltas.
            </>,
            <>
              <strong>Eliges una</strong>. El botón no se activa hasta que has respondido a
              las tres, y siempre puedes decir que ninguna te convence.
            </>,
            <>
              Solo entonces se revela qué arquitectura escribió cada una, con lo que
              respondiste sobre cada tarjeta al lado.
            </>,
            <>
              Si te apetece, afinas la del sistema en cuatro escalas. Es{" "}
              <strong>opcional</strong>: la comparación ya quedó registrada al elegir.
            </>,
            <>
              Debajo, «{t("eval.nextInQueue", { pending: "N" })}» salta directamente a la
              siguiente sin juzgar, sin pasar por la lista.
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

      <Detail title="Las tres arquitecturas que se comparan">
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
          conceptos, quién las descripciones, quién los ejemplos del banco, quién los
          prerrequisitos. {t("fair.footnote")}
        </p>
      </Detail>

      <Detail title="Por qué el orden de las tarjetas es distinto para cada persona">
        <p>
          Si dos evaluadores juzgan los mismos tres ejercicios, cada uno los ve en un orden
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
          <strong>Cuántos ejercicios se generan</strong>: siempre uno por arquitectura. Es lo que
          hace de la sesión la unidad de análisis.
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
          estaba. Lo que se está haciendo se mira desde el <strong>{t("nav.dashboard")}</strong>{" "}
          y desde el cajón de ejecución.
        </p>
      </SectionHead>

      <Block title="Los seis estados">
        <Paragraph>
          Ningún estado se distingue solo por el color: cada uno tiene su forma, y esa forma es la
          misma en la barra de arriba, en las tarjetas del panel y en la cabecera de cada etapa.
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
            Es el plan real del constructor del temario, leído de la API y no copiado aquí. Cada
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
              head: <>En la pantalla de la etapa</>,
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
          la tubería se guarda en el servidor, en <code>logs/</code> y dentro en la carpeta del
          workspace. Es material para leer junto a una traza, no para mirar mientras trabajas, y
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
          tarjeta del panel, en la cabecera de la etapa y en el botón que lo lanzó.
        </Paragraph>
        <Paragraph>
          El número entre paréntesis cuenta trabajos, no minutos, y solo cuenta los del{" "}
          <em>mismo motor</em>: si lo tuyo es remoto y lo que hay en marcha es local, no vas
          detrás de nada. Un encargo en cola es un encargo hecho, así que el formulario se queda
          plegado y lo que se te ofrece es cancelarlo, no volver a lanzarlo.
        </Paragraph>
      </Block>

      <Alert tone="attention" title="Cancelar y reconstruir">
        <p>
          Cancelar no corta a mitad de una llamada: para en el próximo punto seguro, así que puede
          tardar. Y una reconstrucción <em>esconde</em> el artefacto que va a reemplazar sin
          borrarlo —el constructor escribe al final—, por eso cancelar lo devuelve intacto y sin
          ningún paso de restauración.
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
            body: "En qué workspaces estás y con qué papel, y desde cuál entrar a otro. Los accesos los concede quien administra: aquí no se piden. Lo único que puedes hacer sobre ellos es eliminar uno tuyo — de los que eres propietario —, y al hacerlo se te dice qué desaparece y qué se queda. El nombre no se cambia desde aquí: se pone al crearlo y solo lo cambia quien administra.",
          },
          {
            key: "variantes",
            head: t("tabs.variants"),
            body: "Todo lo que has generado, con el encargo que lo produjo: se puede buscar, ver solo lo tuyo o lo de todo el workspace, relanzar «más como esta» y borrar.",
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
                body: "En el que se le HABLA AL MODELO. Vive en el workspace, se elige al crearlo y ya no se cambia: las etiquetas de las relaciones quedan escritas dentro del temario y el cargador indexa por ellas.",
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

      <Block title="Una variante puede volver al banco">
        <Paragraph>
          En «{t("tabs.variants")}», cada variante ofrece «{t("generations.promote")}»:{" "}
          {t("generations.promoteHint")}
        </Paragraph>
        <Paragraph>
          Es la forma de que lo que salga bien deje de ser un resultado suelto y pase a ser un
          ejemplo que el modelo imita la próxima vez. Lo que hay que tener presente es la
          segunda mitad de esa frase: el banco queda obsoleto y hay que volver a aprobarlo, así
          que conviene promover varias de una vez y no de una en una.
        </Paragraph>
      </Block>

      <Block title="Dos cosas que sorprenden">
        <Alert tone="info" title="El usuario no se puede cambiar">
          <p>
            Es lo que identifica todo lo que has hecho: cada variante, cada sesión de evaluación y
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
          La invitación puede traer ya un workspace y un papel dentro de él, o no traer ninguno:
          en ese caso entras igual y el panel te ofrece crear el tuyo. Una cuenta sin workspace
          es una cuenta normal, no una cuenta a medio hacer.
        </Paragraph>
      </Block>

      <Block title="Tema claro, oscuro o como el sistema">
        <Paragraph>
          Tres botones en el mismo menú del avatar. Es una propiedad de la pantalla y no de la
          cuenta: se guarda por navegador, porque la misma persona lee esto en un portátil al sol
          y en un escritorio a oscuras.
        </Paragraph>
      </Block>

      <Block title={t("admin.title")}>
        <Badge variant="secondary">solo administradores</Badge>
        <Paragraph>
          La instalación vista desde fuera, en cinco pestañas: «{t("admin.tab.study")}» (el
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
          {t("admin.tab.study")}» reúne lo que ha contestado la gente: las comparaciones que
          han hecho y las valoraciones que dejaron al terminar cada paso.
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
          La invitación puede traer ya un workspace y un permiso dentro de él, o no traer
          ninguno. Los accesos se dan y se quitan después, cuenta por cuenta y workspace por
          workspace, desde esta misma tabla; son tres:
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
              body: "Quien administra entra en todos los workspaces sin ser miembro de ninguno. No se puede quitar a uno mismo: es lo que impide que la instalación se quede sin nadie que la administre.",
            },
            {
              key: "reset",
              head: <>«{t("acc.resetLink")}»</>,
              body: "El mismo enlace que enviaría el correo de «he olvidado la contraseña», generado aquí para pasárselo a mano. Vale unos minutos y una sola vez.",
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
              body: "Borra la cuenta de verdad, y no se puede deshacer. Lo que produjo NO se va con ella: las variantes generadas y las sesiones de evaluación se quedan, sin autor. Un curso preparado sobre ese material no se cae porque se dé de baja a quien lo generó, y el estudio no pierde las comparaciones que contó.",
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
          Todas las instancias de la instalación con sus miembros, sus variantes y el estado de
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
              body: "Borrar un workspace desde aquí se lleva también su árbol de ficheros del disco, los documentos en bruto incluidos. El diálogo enumera lo que desaparece y hay que escribir el identificador de la instancia para confirmarlo. Sobre el único workspace que quede no se ofrece.",
            },
          ]}
        />
        <Paragraph>
          <strong>Vaciar una etapa concreta</strong> se hace desde su propio distintivo en la
          columna de la cadena: se pulsa el de la etapa y se confirma. No toca el historial, así
          que si te equivocas se restaura desde la pantalla del propio artefacto.
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
                  {t("eng.half.processNote")}. La cola entera de la instalación, de todos los
                  workspaces: lo que se está ejecutando, lo que espera y de quién es cada cosa.
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
          y lo dicen con el círculo a trazos: el guardián porque su modelo no razona, la variante
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
          artefactos, variantes y evaluaciones se leen igual cuando vuelva a abrirse.
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
    question: `Una etapa dice «${t(STATUS.stale.labelKey)}»`,
    answer: (
      <p>
        Algo de lo que depende cambió después de que la aprobaras. Abre la etapa: o reconstruyes
        con lo nuevo, o compruebas que sigue valiendo y la vuelves a aprobar. Mientras tanto, las
        etapas que dependen de ella quedan bloqueadas.
      </p>
    ),
  },
  {
    key: "bloqueado",
    question: `Una etapa dice «${t(STATUS.blocked.labelKey)}»`,
    answer: (
      <p>
        No es «no está hecho», es «no te toca todavía»: falta aprobar algo de lo que depende. La
        propia pantalla dice cuál, con enlace.
      </p>
    ),
  },
  {
    key: "aprobada",
    question: "Una etapa aprobada no me deja cambiar nada",
    answer: (
      <>
        <p>
          Es lo que significa aprobar. Lo que se aprueba es el fichero tal cual está, así que
          mientras la etapa esté cerrada la pantalla no ofrece ningún control que lo reescriba:
          los campos se ven, pero de solo lectura.
        </p>
        <p>
          El camino de vuelta es el botón «{t("stage.reopen")}» de la cabecera, con el aviso
          debajo diciéndolo con todas las letras: «{t("stage.locked")}». Reabrir quita la
          aprobación y nada más — no borra, no reconstruye — y volver a aprobar cuesta un clic.
        </p>
        <p>
          Dos cosas siguen funcionando con la etapa aprobada, porque no tocan el artefacto: las
          descripciones de conceptos y el currículo.
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
          tu permiso sobre la instancia es de solo lectura; la etapa anterior no está aprobada;
          el origen en bruto no tiene ningún documento; el motor no responde; o esta misma
          construcción ya está en cola. Si es la del material, el enlace del propio aviso lleva
          a subirlo.
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
    question: "Hay ejercicios del banco sin ningún concepto",
    answer: (
      <p>
        Es normal en la primera pasada. Usa «{t("bank.retagUntagged", { n: "N" })}»: se lanza
        solo sobre esos, nunca sobre el banco entero. Y tiene sentido repetir, porque el índice
        mejora con cada ejercicio bien etiquetado. Si uno sigue resistiéndose, ponle el concepto a
        mano.
      </p>
    ),
  },
  {
    key: "bloqueadas",
    question: "Mis instrucciones adicionales salen bloqueadas",
    answer: (
      <p>
        El aviso dice cuál de los dos filtros ha sido. Si es el de admisibilidad, te nombra el
        control de arriba que ya decide eso: cámbialo ahí en vez de pedirlo por escrito. Si es el
        guardarraíl, te dice bajo qué criterio.
      </p>
    ),
  },
  {
    key: "horas",
    question: "Llevo horas y no sé si está avanzando",
    answer: (
      <p>
        La construcción del temario es el trabajo más caro de la cadena. La barra por fases dice en
        cuál está y el tramo que se mueve es el que corre; el cajón de ejecución enseña el paso
        concreto. Puedes cerrar la pestaña y volver más tarde.
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
          la etapa anterior sin aprobar, el origen en bruto vacío, el motor sin responder, esa
          misma construcción ya en cola— y las dice en su propio tooltip. Que haya otro trabajo
          corriendo no está en la lista: eso se resuelve esperando turno, y el botón lo cuenta.
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
