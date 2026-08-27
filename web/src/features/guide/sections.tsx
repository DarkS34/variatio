import {
  Activity,
  Compass,
  FileText,
  Layers,
  Library,
  LifeBuoy,
  Network,
  Play,
  Scale,
  Send,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Alert, PhaseBar } from "@/components/ui/misc";
import { Rail, type RailStop } from "@/components/ui/rail";
import { StatusMark } from "@/components/ui/status";
import { STATUS, type StatusKey } from "@/lib/status";
import { ARM_META } from "@/study/arms";
import { Block, Detail, Facts, Paragraph, Rows, SectionHead, Steps } from "./blocks";
import { useT } from "@/lib/i18n";

export interface GuideSection {
  slug: string;
  label: string;
  group: string;
  icon: LucideIcon;
  body: () => ReactNode;
}

const CHAIN: RailStop[] = [
  { key: "perfil", label: "Perfil", status: "approved" },
  { key: "grafo", label: "Grafo", status: "approved" },
  { key: "banco", label: "Banco", status: "approved" },
];

const STATE_ORDER: StatusKey[] = ["approved", "draft", "stale", "building", "missing", "blocked"];

const STATE_HINTS: Record<StatusKey, string> = {
  approved: "Cerrado y contado como bueno. Es lo que desbloquea la etapa siguiente.",
  draft: "Construido pero sin revisar. Se puede editar; todavía no cuenta.",
  stale:
    "Algo de lo que depende cambió después de aprobarlo. Hay que reconstruir o volver a aprobar.",
  building:
    "Hay un trabajo escribiéndolo ahora mismo. Lo anterior queda oculto hasta que termine.",
  missing: "Todavía no existe. La pantalla enseña la cabecera y un único botón: construir.",
  blocked: "No es «no está hecho», es «no te toca todavía»: falta aprobar algo de lo que depende.",
};

const BUILD_PLAN = [
  { key: "convert", label: "Conversión del corpus", weight: 11 },
  { key: "extract", label: "Extracción", weight: 8 },
  { key: "clean", label: "Limpieza y fusión", weight: 25 },
  { key: "domains", label: "Dominios", weight: 9 },
  { key: "link", label: "Enlazado", weight: 26 },
  { key: "curate", label: "Curación", weight: 1 },
];

const ARM_ORDER = ["naive", "rag", "system"] as const;

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

function Empezar() {
  return (
    <div className="space-y-6">
      <SectionHead eyebrow="Primeros pasos" title="Qué es y cómo se recorre">
        <p>
          <strong>Variatio</strong> genera <strong>ítems de aprendizaje</strong> —ejercicios,
          problemas, tareas de evaluación— anclados al temario de una asignatura. No escribe sobre un tema
          en abstracto: parte de tres artefactos que describen tu asignatura y produce variantes
          que respetan lo que el alumno ya ha visto y lo que todavía no.
        </p>
      </SectionHead>

      <Block title="El recorrido, de un vistazo">
        <div className="flex flex-wrap items-end gap-4 rounded-lg border border-border bg-card p-4 sm:gap-6 sm:p-6">
          <div className="flex flex-col items-center gap-2">
            <Pill icon={Activity} label="Panel" />
            <span className="text-small text-muted-foreground">observar</span>
          </div>

          <span aria-hidden className="w-px self-stretch bg-border" />

          <div className="flex w-full min-w-0 flex-1 flex-col items-center gap-2 sm:w-auto sm:min-w-[20rem]">
            <Rail stops={CHAIN} className="max-w-[26rem]" />
            <span className="text-small text-muted-foreground">
              preparar la instancia, en este orden
            </span>
          </div>

          <span aria-hidden className="w-px self-stretch bg-border" />

          <div className="flex flex-col items-center gap-2">
            <div className="flex gap-1.5">
              <Pill icon={Play} label="Generar" />
              <Pill icon={Scale} label="Evaluar" tone="study" />
            </div>
            <span className="text-small text-muted-foreground">usar lo preparado</span>
          </div>
        </div>
        <Paragraph>
          Es exactamente la barra de arriba. La línea entre las tres etapas del centro no es
          adorno: significa dependencia, y se dibuja punteada mientras lo de detrás no esté
          resuelto.
        </Paragraph>
      </Block>

      <Rows
        items={[
          {
            key: "perfil",
            head: "Perfil de ejemplares",
            body: "Qué es un ítem aquí: sus campos, sus tipos y las guías que el modelo sigue.",
          },
          {
            key: "grafo",
            head: "Grafo de conocimiento",
            body: "El vocabulario: conceptos, dominios y las relaciones entre ellos.",
          },
          {
            key: "banco",
            head: "Banco de ejemplares",
            body: "Ítems reales de tu asignatura, ya etiquetados con conceptos del grafo.",
          },
        ]}
      />

      <Alert tone="info" title="Se empieza por el perfil, no por el grafo">
        <p>
          Un grafo se puede construir sin nada más, pero su revisión de etiquetabilidad necesita
          el perfil <em>aprobado</em>. Empezar por el grafo es empezar por una etapa que no
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
              Desde el <strong>Panel</strong>, sube el material en bruto: los documentos con
              ejercicios de ejemplo y el corpus de teoría.
            </>,
            <>
              Construye el <strong>perfil</strong>, revísalo campo a campo y apruébalo. Son
              minutos.
            </>,
            <>
              Lanza el <strong>grafo</strong>. Es el trabajo más caro de la cadena —horas—:
              puedes cerrar la pestaña, el servidor sigue.
            </>,
            <>
              Revisa la <strong>etiquetabilidad</strong> y las <strong>descripciones</strong> del
              grafo, y apruébalo.
            </>,
            <>
              Extrae el <strong>banco</strong>, repasa los ítems que se quedaron sin concepto y
              apruébalo.
            </>,
            <>Con las tres aprobadas se abren «Generar» y «Evaluar».</>,
          ]}
        />
      </Block>

      <Detail title="¿Por qué hay que aprobar cada etapa?">
        <p>
          Lo que se aprueba es el <em>hash del fichero</em>. Mientras una etapa está aprobada, su
          pantalla no ofrece ningún control que reescriba el artefacto: para volver a editarlo
          hay que pulsar «Reabrir». Aprobar es lo que desbloquea la etapa siguiente y, con las
          tres, la generación.
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
  return (
    <div className="space-y-6">
      <SectionHead eyebrow="Primeros pasos" title="El workspace y la asignatura">
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

      <Block title="Una pestaña, un workspace">
        <Paragraph>
          El workspace activo se guarda en tu cuenta y sobrevive a cerrar sesión; el que estás{" "}
          <em>mirando</em> lo guarda la pestaña. Puedes tener dos asignaturas abiertas en dos
          pestañas del mismo navegador sin que se pisen. Al cambiar de workspace la pantalla se
          vacía de lo que estabas viendo: los trabajos, el registro y el progreso pertenecen a la
          instancia que dejas.
        </Paragraph>
      </Block>

      <Block title="El contexto de la asignatura">
        <Paragraph>
          Es la prosa que dice de qué va esta instancia —materia, nivel, idioma de instrucción,
          convenciones— y entra en <em>todas</em> las llamadas al modelo. Se lee y se edita en el{" "}
          <strong>Panel</strong>, en su propia tarjeta: no es una etapa de la cadena y por eso no
          está en la barra.
        </Paragraph>
        <Alert tone="attention" title="«Borrador sin leer»">
          <p>
            Cada construcción escribe un borrador nuevo del contexto sin tocar el tuyo. Si la
            tarjeta lo señala, hay una síntesis nueva esperando a que la leas: ábrela, quédate
            con lo que mejore y descarta el resto. Tu texto curado nunca se sobreescribe solo.
          </p>
        </Alert>
      </Block>

      <Block title="El currículo">
        <Paragraph>
          Los conceptos que el curso <em>ya ha impartido</em>. Se edita en la pestaña «Currículo»
          del grafo y es lo que acota el andamiaje de cada generación: de un concepto impartido
          el ejercicio puede apoyarse; de uno que aún no se ha dado, no puede depender.
        </Paragraph>
        <Alert tone="info" title="Vacío no significa «nada impartido»: significa «sin restricción»">
          <p>
            Leerlo al pie de la letra prohibiría el temario entero, que es justo el estado en el
            que arranca una instancia nueva. Vaciarlo a propósito sí se guarda como una decisión,
            con su fecha.
          </p>
        </Alert>
      </Block>

      <Detail title="«Cerrar prerrequisitos al guardar»">
        <p>
          Al guardar el currículo puedes pedir que se añadan también los prerrequisitos de lo que
          has marcado. Se aplica <em>al guardar</em> y queda escrito en el fichero: no es una
          regla que se aplique al leerlo, así que el currículo siempre significa exactamente lo
          que pone.
        </p>
        <p>
          Si el grafo cambia y algún concepto guardado desaparece, la pantalla te lo dice por su
          nombre en vez de dejarlo caer en silencio.
        </p>
      </Detail>
    </div>
  );
}

function Perfil() {
  return (
    <div className="space-y-6">
      <SectionHead eyebrow="Preparar la instancia · etapa 1" title="Perfil de ejemplares">
        <p>
          Define qué es un ítem: sus campos, sus tipos y las guías que el modelo sigue al
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
          { label: "Cuánto tarda", value: "Minutos. Una pasada larga sobre la muestra." },
          {
            label: "Qué desbloquea",
            value: "La extracción del banco y la revisión de etiquetabilidad del grafo.",
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
              Repasa cada campo: su nombre, su tipo, la guía de extracción, la guía de generación
              y quién decide su valor.
            </>,
            <>
              Repasa las <strong>reglas generales de generación</strong>: son las que gobiernan
              cómo se escribe un ítem entero.
            </>,
            <>Aprueba. La etapa se cierra y la pantalla deja de ofrecer nada que la reescriba.</>,
          ]}
        />
      </Block>

      <Block title="Qué tiene un campo">
        <Rows
          items={[
            { key: "tipo", head: "Tipo", body: "Texto, número, lista o una enumeración cerrada de valores." },
            {
              key: "extraccion",
              head: "Guía de extracción",
              body: "Cómo reconocer ese campo dentro de un documento en bruto.",
            },
            {
              key: "generacion",
              head: "Guía de generación",
              body: "Cómo escribirlo al generar. Se escribe a mano: lo que el constructor propone son reglas generales, no una por campo.",
            },
            {
              key: "decidido",
              head: "Decidido por",
              body: "El modelo, o tú. Los que decides tú aparecen como controles en el formulario de generación.",
            },
            {
              key: "primario",
              head: "Campo primario",
              body: "El que lleva el enunciado. Es el que se convierte en vector para emparejar con conceptos.",
            },
          ]}
        />
      </Block>

      <Alert tone="danger" title="Tocarlo después de extraer el banco lo invalida">
        <p>
          Los ítems del banco se extrajeron contra el esquema anterior. Si cambias los campos, el
          banco pasa a «Obsoleto» y hay que volver a extraerlo.
        </p>
      </Alert>

      <Detail title="El borrador no es estable, y conviene saberlo">
        <p>
          El constructor infiere el perfil de una muestra del corpus y ha producido conjuntos de
          campos <em>distintos</em> en dos pasadas sobre el mismo material. Trátalo como un punto
          de partida: la versión que apruebas es tuya, no suya.
        </p>
        <p>Si vuelves a construirlo, compáralo antes de sustituir el que ya tenías.</p>
      </Detail>
    </div>
  );
}

function Grafo() {
  return (
    <div className="space-y-6">
      <SectionHead eyebrow="Preparar la instancia · etapa 2" title="Grafo de conocimiento">
        <p>
          El vocabulario del sistema. Todo lo que se etiquete y se genere después sale de aquí:
          ni el modelo ni tú podéis usar un concepto que no esté en el grafo.
        </p>
      </SectionHead>

      <Facts
        items={[
          {
            label: "Qué produce",
            value: <code className="font-mono text-small">knowledge_graph.json</code>,
          },
          { label: "Cuánto tarda", value: "Horas. Es el trabajo más caro de toda la cadena." },
          { label: "Qué desbloquea", value: "El etiquetado del banco, el currículo y la generación." },
        ]}
      />

      <Block title="Las dos vistas">
        <Rows
          items={[
            {
              key: "temario",
              head: "Temario",
              body: "Los dominios y sus conceptos, con el lienzo del grafo al lado. Arrastra para mover, rueda para acercar, y al pulsar un nodo se selecciona también en la tabla.",
            },
            {
              key: "curriculo",
              head: "Currículo",
              body: "Qué se ha impartido ya. Aquí se marca, y desde aquí se guarda con o sin cierre de prerrequisitos.",
            },
          ]}
        />
        <Paragraph>
          El lienzo tiene dos disposiciones: <strong>fuerzas</strong>, que agrupa por vecindad, y{" "}
          <strong>currículo</strong>, que ordena por niveles de prerrequisito. Cambiar de una a
          otra no reconstruye nada: los nodos se desplazan hasta su nueva posición.
        </Paragraph>
      </Block>

      <Block title="Después de construir, tres revisiones">
        <Steps
          items={[
            <>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                Etiquetabilidad
                <Badge variant="attention">necesita el perfil aprobado</Badge>
              </p>
              <p className="text-small text-muted-foreground">
                Qué conceptos sirven de <em>etiqueta</em>. Los que valdrían para cualquier ítem
                —«codificación», «diseño»— se marcan como no etiquetables: siguen existiendo y
                siguen funcionando a través de sus relaciones, simplemente dejan de poder ser el
                tema de un ejercicio. Ante la duda se excluye: una etiqueta vaga contamina el
                corpus entero.
              </p>
            </>,
            <>
              <p className="font-medium">Descripciones</p>
              <p className="text-small text-muted-foreground">
                La prosa que describe cada concepto, escrita contra los párrafos del corpus de
                los que salió. <strong>Es el texto contra el que se compara, no el nombre.</strong>{" "}
                Se escriben solas al indexar; la pestaña es para leerlas y corregir las que no
                digan lo que tú dirías.
              </p>
            </>,
            <>
              <p className="font-medium">Curación a mano</p>
              <p className="text-small text-muted-foreground">
                Renombrar lo que quedó torcido, borrar lo que no es un concepto de la materia y
                arreglar relaciones. Renombrar arrastra consigo el anclaje al corpus; borrar lo
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
            centro de los ítems del banco que ya llevan ese concepto.
          </p>
          <p>
            Por eso una descripción mal escrita se paga en cada etiquetado y en cada generación,
            y por eso conviene leerlas.
          </p>
        </Detail>

        <Detail title="Prerrequisitos: lo que se da por sabido y lo que se prohíbe">
          <p>
            Alrededor de los conceptos que pides, el sistema deriva dos listas del grafo y las
            mete en el prompt:
          </p>
          <ul className="space-y-1">
            <li>
              <span className="font-medium text-settled">Se da por sabido</span> — prerrequisitos
              que además están en el currículo. El ejercicio puede apoyarse en ellos, pero no
              puede convertirlos en la dificultad. Van con su descripción, no con su nombre a
              secas.
            </li>
            <li>
              <span className="font-medium text-destructive">Prohibido</span> — lo que va después
              del objetivo y todavía no se ha impartido. No puede aparecer.
            </li>
          </ul>
          <p>
            Las dos listas recorren el grafo entero, no un salto: son cierres transitivos
            acotados por el currículo. En la pantalla de generación se dibujan antes de lanzar,
            para que veas exactamente con qué va a contar el modelo.
          </p>
        </Detail>
      </div>
    </div>
  );
}

function Banco() {
  return (
    <div className="space-y-6">
      <SectionHead eyebrow="Preparar la instancia · etapa 3" title="Banco de ejemplares">
        <p>
          Los ítems extraídos de tus documentos y etiquetados con conceptos del grafo. Son los
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
          { label: "Cuánto tarda", value: "Decenas de minutos, según cuántos documentos haya." },
          { label: "Se guarda", value: "Tras cada documento. Cancelar no pierde lo ya extraído." },
        ]}
      />

      <Alert tone="info" title="Extraer y etiquetar son un solo trabajo">
        <p>
          Cada documento se etiqueta según sale del extractor, así que no hay un botón de
          «etiquetar todo»: ese paso ya no existe por separado. Lo que sí hay es la corrección de
          lo que quedó mal.
        </p>
      </Alert>

      <Block title="Se revisa por sospecha, no de arriba abajo">
        <Steps
          items={[
            <>
              Primero, los que <strong>se quedaron sin concepto</strong>. La tarjeta de etiquetado
              los cuenta y «Ver los N sin concepto» los filtra.
            </>,
            <>
              Después, las decisiones <strong>ganadas por poco margen</strong>: ahí es donde el
              emparejamiento se equivoca sin avisar.
            </>,
            <>
              Corrige el <strong>concepto primario</strong> a mano donde haga falta: es el que
              decide con qué se compara ese ítem después.
            </>,
          ]}
        />
      </Block>

      <Block title="Los dos botones de re-etiquetar, que no hacen lo mismo">
        <Rows
          items={[
            {
              key: "pendientes",
              head: "«Re-etiquetar los N»",
              body: "Sin selección: se lanza sobre exactamente los ítems que se quedaron sin concepto, nunca sobre el banco entero.",
            },
            {
              key: "seleccion",
              head: "«Re-etiquetar selección»",
              body: "Con ítems marcados a mano: se re-etiquetan solo esos, aunque ya tuvieran concepto.",
            },
          ]}
        />
      </Block>

      <Detail title="Reintentar tiene sentido: el índice mejora entre pasadas">
        <p>
          Cada ítem bien etiquetado empuja el centro de su concepto hacia donde de verdad está,
          así que el índice de una pasada lo consume la siguiente. Un ítem que hoy no encuentra
          concepto puede encontrarlo mañana sin que hayas tocado nada.
        </p>
        <p>
          Por eso los rechazados se vuelven a intentar en cada pasada, en vez de quedar marcados
          como imposibles.
        </p>
      </Detail>
    </div>
  );
}

function Generar() {
  return (
    <div className="space-y-6">
      <SectionHead eyebrow="Usarla" title="Generar variantes">
        <p>
          Un encargo, un lote de variantes. El formulario son cinco preguntas: se responden de
          arriba abajo y cada una se cierra en una línea al contestarla, así que volver a cambiar
          los conceptos cuesta un clic y ningún scroll.
        </p>
      </SectionHead>

      <Block title="Las cinco preguntas">
        <Steps
          items={[
            <>
              <p className="font-medium">¿Qué tipo de ítem?</p>
              <p className="text-small text-muted-foreground">
                La modalidad, de las que declara tu perfil. Determina qué campos hay que rellenar
                después.
              </p>
            </>,
            <>
              <p className="font-medium">¿Qué se ha visto ya?</p>
              <p className="text-small text-muted-foreground">
                El currículo para <em>este</em> encargo. Llega relleno con el del workspace;
                vaciarlo aquí significa «sin restricción», solo para esta tirada.
              </p>
            </>,
            <>
              <p className="font-medium">¿Qué hay que practicar?</p>
              <p className="text-small text-muted-foreground">
                Los conceptos objetivo. Solo se ofrecen los <strong>etiquetables</strong>: aquí se
                elige de qué va el ejercicio, y para eso un concepto genérico no vale.
              </p>
            </>,
            <>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                Campos fijos
                <Badge variant="outline">opcional</Badge>
              </p>
              <p className="text-small text-muted-foreground">
                Los campos que tu perfil marca como decididos por el usuario: dificultad, formato
                de respuesta, lo que hayas declarado.
              </p>
            </>,
            <>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                Instrucciones adicionales
                <Badge variant="outline">opcional</Badge>
              </p>
              <p className="text-small text-muted-foreground">
                Texto libre para lo que ningún control de arriba decide. Pasa por dos filtros
                antes de entrar en el prompt.
              </p>
            </>,
          ]}
        />
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
              body: "Decide si lo que pides es de este campo o de algo que ya has decidido más arriba: los conceptos, la modalidad, los campos del ítem o la propia asignatura. Si lo es, te dice qué control lo decide.",
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

      <Block title="Razonamiento y esfuerzo">
        <Paragraph>
          El interruptor decide si el modelo delibera antes de contestar; la barra de al lado,
          cuánto. Un esfuerzo alto en el modelo local multiplica el tiempo por varias veces sin
          mejorar necesariamente el enunciado, y la propia pantalla te avisa cuando el modelo que
          va a atender el encargo es de los que se descontrolan por arriba.
        </Paragraph>
      </Block>

      <Block title="Lo que ves al terminar">
        <div className="space-y-3">
          <div className="flex flex-wrap items-start gap-3">
            <Badge variant="settled">guardada</Badge>
            <p className="max-w-[64ch] flex-1 text-body text-muted-foreground">
              Cada variante se guarda en «Mis variantes» <em>en cuanto valida</em>, con su encargo
              entero. Un lote cancelado a la tercera conserva tres.
            </p>
          </div>
          <div className="flex flex-wrap items-start gap-3">
            <Badge variant="attention">2 señales</Badge>
            <p className="max-w-[64ch] flex-1 text-body text-muted-foreground">
              Lo que el sistema puede comprobar sin juzgar el ejercicio: si nombra algo no
              impartido, si se parece demasiado a un ejemplo o a otra del lote, y si el
              etiquetador la reconoce como el concepto que pediste.{" "}
              <strong>Son señales para quien lee, no un rechazo.</strong>
            </p>
          </div>
        </div>
      </Block>

      <Block title="Y después">
        <Rows
          items={[
            {
              key: "cambiar",
              head: "«Cambiar el encargo»",
              body: "Reabre el formulario con todo relleno y deja los resultados a la vista hasta que lanzas otra tanda.",
            },
            { key: "otras", head: "«Generar otras N»", body: "Repite el mismo encargo, lote nuevo." },
            {
              key: "como-esta",
              head: "«Generar más como esta»",
              body: "Está en «Mis variantes» y recupera el encargo de una variante concreta, aunque sea de otro día.",
            },
          ]}
        />
      </Block>
    </div>
  );
}

function Evaluar() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow="Usarla" title="Evaluar">
        <p>
          El mismo encargo resuelto por tres arquitecturas distintas y presentado{" "}
          <strong>a ciegas</strong>, para que elijas sin saber cuál es cuál. Es la parte del
          sistema que sirve para medirlo, no para producir material.
        </p>
        <p>
          Normalmente no tendrás que preparar nada: la pantalla abre en{" "}
          <strong>lo que alguien te haya asignado</strong> y solo tienes que leer y decidir.
        </p>
      </SectionHead>

      <Facts
        items={[
          { label: "Cuánto se tarda", value: "Un par de minutos por comparación." },
          {
            label: "Qué produce",
            value: "Una sesión guardada con las tres propuestas y tu juicio.",
          },
          { label: "Qué necesitas", value: "Nada: las comparaciones ya vienen preparadas." },
        ]}
      />

      <Block title="Las tres pestañas">
        <Rows
          items={[
            {
              key: "asignadas",
              head: "Asignadas",
              body: "Lo que alguien ha preparado para ti. Es donde abre la pantalla y donde estará casi siempre tu trabajo. Arriba, la siguiente sin juzgar; debajo, las que quedan y las que ya cerraste.",
            },
            {
              key: "encargo",
              head: "Encargo propio",
              body: "Por si quieres pedir tú un ejercicio concreto. Es el mismo formulario de «Generar», sin dos controles: cuántos ítems y si el modelo razona. Si tu cuenta es de alumno, esta pestaña no aparece.",
            },
            {
              key: "sesiones",
              head: "Mis sesiones",
              body: "Tu histórico. Puedes releer cualquier sesión ya cerrada, con la revelación incluida.",
            },
          ]}
        />
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
          <strong>Cuántos ítems se generan</strong>: siempre uno por arquitectura. Es lo que
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

function Ejecucion() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow="Día a día" title="Seguir una ejecución">
        <p>
          Una GPU, un trabajo cada vez. Puedes cerrar la pestaña: el trabajo corre en el servidor
          y al volver lo encuentras donde estaba. Lo que se está haciendo se mira desde el{" "}
          <strong>Panel</strong> y desde el cajón de ejecución.
        </p>
      </SectionHead>

      <Block title="Los seis estados">
        <Paragraph>
          Ningún estado se distingue solo por el color: cada uno tiene su forma, y esa forma es la
          misma en la barra de arriba, en las tarjetas del panel y en la cabecera de cada etapa.
        </Paragraph>
        <div className="divide-y divide-border rounded-lg border border-border bg-card">
          {STATE_ORDER.map((key) => (
            <div key={key} className="flex items-center gap-4 p-3">
              <StatusMark
                status={key === "blocked" ? "missing" : key}
                blocked={key === "blocked"}
                size="md"
              />
              <span className="w-32 shrink-0 text-body font-medium">{t(STATUS[key].labelKey)}</span>
              <span className="text-small text-muted-foreground">{STATE_HINTS[key]}</span>
            </div>
          ))}
        </div>
      </Block>

      <Block title="La barra es el plan">
        <div className="space-y-3 rounded-lg border border-border bg-card p-4">
          <PhaseBar phases={BUILD_PLAN} percent={42} activeKey="clean" />
          <Paragraph>
            Cada tramo es una fase, y su anchura es el <em>peso medido</em> de esa fase: por eso
            la limpieza y el enlazado ocupan media barra y la curación final es una raya. La que
            se mueve es la que está corriendo. No hay estimación de tiempo en ninguna parte, y es
            deliberado: cambiar de modelo cambia el coste de cada llamada por múltiplos, y una
            cifra falsa es peor que ninguna.
          </Paragraph>
        </div>
      </Block>

      <Block title="Dónde se mira">
        <Rows
          items={[
            {
              key: "ejecucion",
              head: "«Ver ejecución»",
              body: "La píldora de abajo a la derecha, siempre presente. Abre el cajón por la pestaña de progreso: los pasos, la fase y lo que se está escribiendo.",
            },
            {
              key: "registro",
              head: "«Registro»",
              body: "Arriba a la derecha, con el número de líneas de la sesión. Es el mismo cajón, por la otra pestaña.",
            },
          ]}
        />
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
      </Detail>
    </div>
  );
}

function Cuenta() {
  return (
    <div className="space-y-6">
      <SectionHead eyebrow="Día a día" title="Tu cuenta y la instalación">
        <p>
          Todo lo que es tuyo y no es parte de la cadena vive en «Mi perfil», detrás del avatar de
          arriba a la derecha — el mismo menú desde el que has llegado aquí.
        </p>
      </SectionHead>

      <Rows
        items={[
          {
            key: "cuenta",
            head: "Cuenta",
            body: "Tu nombre visible, un correo opcional y la contraseña. El correo no sirve para entrar: solo para recibir el enlace de restablecerla.",
          },
          {
            key: "variantes",
            head: "Variantes",
            body: "Todo lo que has generado, con el encargo que lo produjo. Desde aquí se relanza «más como esta».",
          },
          {
            key: "accesos",
            head: "Accesos",
            body: "En qué workspaces estás y con qué papel. Es de solo lectura: los accesos los concede quien administra.",
          },
        ]}
      />

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

      <Block title="Administración">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">solo administradores</Badge>
        </div>
        <Paragraph>
          La instalación vista desde fuera, en cinco pestañas: <strong>Evaluaciones</strong> (el
          estudio), <strong>Cuentas y accesos</strong> (invitaciones, papeles, desbloqueos),{" "}
          <strong>Workspaces</strong> (espacio en disco, exportar, borrar), <strong>Motor</strong>{" "}
          (modelos residentes, descargas, el túnel SSH a la máquina de la GPU) y{" "}
          <strong>Configuración</strong> (todos los ajustes, cada uno con lo que costó medirlo y
          con lo que invalidará al guardarlo).
        </Paragraph>
      </Block>

      <Block title="Cerrar la instalación mientras se toca">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">solo administradores</Badge>
        </div>
        <Paragraph>
          Arriba del todo de Administración hay un interruptor de <strong>mantenimiento</strong>.
          Cerrado, cualquier otra cuenta ve una pantalla de aviso en lugar de la aplicación —
          con el texto que se escriba ahí— y la API rechaza sus peticiones; quien administra
          sigue entrando, que es lo que permite volver a abrirla.
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

const PROBLEMS: { key: string; question: string; answer: ReactNode }[] = [
  {
    key: "mantenimiento",
    question: "«En mantenimiento»",
    answer: (
      <>
        <p>
          No es un fallo: quien administra la instalación la ha cerrado a propósito para
          aplicar cambios. El aviso dice desde cuándo, y lo tuyo sigue donde estaba —
          artefactos, variantes y evaluaciones se leen igual cuando vuelva a abrirse.
        </p>
        <p>
          No hay hora prevista de vuelta, y no la hay porque nadie la sabe. «Comprobar de
          nuevo» vuelve a preguntar; la pantalla también lo hace sola cada pocos segundos.
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
    key: "modelo",
    question: "Un modelo aparece como «sin instalar»",
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
    question: "Una etapa dice «Obsoleto»",
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
    question: "Una etapa dice «Bloqueado»",
    answer: (
      <p>
        No es «no está hecho», es «no te toca todavía»: falta aprobar algo de lo que depende. La
        propia pantalla dice cuál, con enlace.
      </p>
    ),
  },
  {
    key: "boton",
    question: "El botón de construir está apagado",
    answer: (
      <p>
        Pasa el cursor por encima: dice el motivo. Solo hay cuatro — falta material en bruto, ya
        hay un trabajo corriendo, el motor no responde, o la etapa anterior no está aprobada. Si
        es el primero, el enlace del propio aviso lleva al Panel a subir el material.
      </p>
    ),
  },
  {
    key: "sin-concepto",
    question: "Hay ítems del banco sin ningún concepto",
    answer: (
      <p>
        Es normal en la primera pasada. Usa «Re-etiquetar los N»: se lanza solo sobre esos, nunca
        sobre el banco entero. Y tiene sentido repetir, porque el índice mejora con cada ítem bien
        etiquetado. Si uno sigue resistiéndose, ponle el concepto a mano.
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
        La construcción del grafo tarda horas: es el trabajo más caro de la cadena. La barra por
        fases dice en cuál está y el tramo que se mueve es el que corre; el cajón de ejecución
        enseña el paso concreto. Puedes cerrar la pestaña y volver más tarde.
      </p>
    ),
  },
];

function Repartir() {
  return (
    <div className="space-y-6">
      <SectionHead eyebrow="Día a día" title="Repartir evaluaciones">
        <p>
          Cómo se prepara el trabajo que los evaluadores encuentran hecho. Vive en{" "}
          <strong>Administración → Evaluaciones</strong> y solo lo ve quien administra la
          instalación.
        </p>
        <p>
          La idea de fondo: <strong>quien reparte decide quién es capaz de juzgar qué</strong>.
          Con evaluadores de asignaturas y cursos distintos no hay ninguna regla automática que
          pueda repartir bien, porque la información que hace falta —quién da qué— no está en
          ninguna tabla.
        </p>
      </SectionHead>

      <Block title="Los tres pasos, en ese orden">
        <Steps
          items={[
            <>
              <strong>¿A quién?</strong> Eliges la persona primero, no la comparación. Así
              «¿puede juzgar esto?» es la primera pregunta y no una que se hace al final.
            </>,
            <>
              <strong>¿En cuál de sus workspaces?</strong> Solo salen los que esa persona
              puede abrir de verdad. Asignarle algo de una asignatura a la que no tiene acceso
              le pondría en la cola una entrada que da error al pulsarla.
            </>,
            <>
              <strong>¿Cuáles?</strong> Marcas las comparaciones que le tocan y las asignas.
              Las que no repartas <strong>se quedan guardadas</strong> para otra persona.
            </>,
          ]}
        />
      </Block>

      <Block title="Preparar comparaciones por adelantado">
        <Paragraph>
          En el tercer paso, «Encargar más comparaciones» abre el mismo formulario de
          «Generar» y prepara varias de una tanda. Se van haciendo una detrás de otra en la
          cola, y aparecen en la lista según terminan.
        </Paragraph>
        <Paragraph>
          Prepararlas antes es lo que hace que un profesor entre y no tenga que configurar
          nada ni esperar a la GPU. Es también lo que permite{" "}
          <strong>repartir los encargos por dominios y tipos de ejercicio a propósito</strong>{" "}
          en vez de dejar que cada evaluador pida sus dos conceptos favoritos.
        </Paragraph>
        <Alert tone="attention" title="Para encargar, hay que tener ese workspace abierto">
          <p>
            El formulario lee el grafo y los conceptos del workspace que tengas activo arriba
            del todo. Si no coincide con el que elegiste en el paso 2, el botón está
            desactivado a propósito: componer un encargo con los conceptos de una asignatura
            para ejecutarlo en otra no acabaría bien. Repartir lo que ya existe sí funciona
            desde cualquier sitio.
          </p>
        </Alert>
      </Block>

      <Block title="Dar la misma comparación a dos personas">
        <Paragraph>
          Es deliberado y es la única forma de saber si el instrumento es fiable: si dos
          personas que leen los mismos tres ejercicios coinciden, la medida se sostiene; si
          no, hay que decirlo. En la lista se ve quién tiene ya cada comparación, para poder
          construir ese solapamiento a propósito.
        </Paragraph>
        <Paragraph>
          Cada persona recibe los <strong>mismos ejercicios con un orden propio</strong>, para
          que lo que compartan sea el juicio y no la posición de las tarjetas.
        </Paragraph>
        <Paragraph>
          Hay además una casilla para repetirle una comparación a quien ya la juzgó. Eso mide
          otra cosa —si una persona es consistente consigo misma— y por eso hay que pedirlo
          expresamente.
        </Paragraph>
      </Block>

      <Block title="Docente o alumno">
        <Paragraph>
          Cada cuenta lleva un perfil de evaluador que decide{" "}
          <strong>qué pregunta se le hace</strong> sobre cada tarjeta: a un docente, si pondría
          el ejercicio en clase; a un alumno, si le serviría para practicar. Un alumno no da
          clase, así que preguntarle lo primero solo sacaría una respuesta de compromiso.
        </Paragraph>
        <Paragraph>
          Lo dice cada persona al crear su cuenta desde la invitación: el enlace no lo trae,
          porque quien invita no tiene por qué saberlo y una pregunta a mitad de una
          comparación se contesta de cualquier manera. Se corrige después desde «Cuentas y
          accesos», y ahí también se le pone perfil a una cuenta creada desde la línea de
          órdenes. Las cuentas sin perfil salen marcadas para que no se queden así: mientras
          tanto se les hacen las preguntas de docente.
        </Paragraph>
      </Block>

      <Detail title="Qué mira el panel para saber si el estudio se sostiene">
        <p>
          <strong>Si la preferencia se distingue del azar</strong>. Con tres propuestas, elegir
          a ciegas daría un 33 %. El panel acompaña cada porcentaje de su intervalo y de la
          probabilidad de haberlo visto por casualidad.
        </p>
        <p>
          <strong>Si la posición decidió algo</strong>. Cruza la letra elegida contra el orden
          que se sorteó. Si la primera tarjeta ganase demasiadas veces, el problema sería la
          colocación y no los ejercicios.
        </p>
        <p>
          <strong>Si dos evaluadores coinciden</strong>, sobre las comparaciones repartidas a
          más de una persona.
        </p>
        <p>
          <strong>Cuánto se tarda en juzgar</strong>. Una sesión cerrada en ocho segundos no da
          para leer tres enunciados, y conviene poder decirlo.
        </p>
        <p>
          <strong>Cuántas se saltaron por falta de criterio</strong>. Es un dato sobre la
          composición del panel, no un fallo de nadie.
        </p>
      </Detail>
    </div>
  );
}

function Problemas() {
  return (
    <div className="space-y-6">
      <SectionHead eyebrow="Día a día" title="Cuando algo va mal">
        <p>
          Casi nada de lo que aparece aquí rompe nada: lo ya construido se sigue leyendo siempre.
          Lo que falla es arrancar trabajo nuevo.
        </p>
      </SectionHead>

      <div className="space-y-2">
        {PROBLEMS.map((problem) => (
          <Detail key={problem.key} title={problem.question}>
            {problem.answer}
          </Detail>
        ))}
      </div>

      <Alert tone="info" title="Regla general: pasa el cursor por encima de lo que está apagado">
        <p>
          Ningún control desactivado se queda callado en esta aplicación. El botón de construir
          decide en un único sitio todas las razones para no ofrecerse —falta material, hay un
          trabajo corriendo, el motor no responde, la etapa anterior sin aprobar— y las dice en su
          propio tooltip.
        </p>
      </Alert>
    </div>
  );
}

export const GUIDE_SECTIONS: GuideSection[] = [
  {
    slug: "empezar",
    label: "Qué es y cómo se recorre",
    group: "Primeros pasos",
    icon: Compass,
    body: Empezar,
  },
  {
    slug: "workspace",
    label: "El workspace y la asignatura",
    group: "Primeros pasos",
    icon: Layers,
    body: Workspace,
  },
  {
    slug: "perfil",
    label: "Perfil de ejemplares",
    group: "Preparar la instancia",
    icon: FileText,
    body: Perfil,
  },
  {
    slug: "grafo",
    label: "Grafo de conocimiento",
    group: "Preparar la instancia",
    icon: Network,
    body: Grafo,
  },
  {
    slug: "banco",
    label: "Banco de ejemplares",
    group: "Preparar la instancia",
    icon: Library,
    body: Banco,
  },
  {
    slug: "generar",
    label: "Generar variantes",
    group: "Usarla",
    icon: Play,
    body: Generar,
  },
  {
    slug: "evaluar",
    label: "Evaluar propuestas",
    group: "Usarla",
    icon: Scale,
    body: Evaluar,
  },
  {
    slug: "ejecucion",
    label: "Seguir una ejecución",
    group: "Día a día",
    icon: Activity,
    body: Ejecucion,
  },
  {
    slug: "cuenta",
    label: "Tu cuenta y la instalación",
    group: "Día a día",
    icon: UserRound,
    body: Cuenta,
  },
  // Administrator-only, and it sits in «Día a día» rather than «Usarla» because it is not
  // something an evaluator ever does: it is the work that makes their queue exist.
  {
    slug: "repartir",
    label: "Repartir evaluaciones",
    group: "Día a día",
    icon: Send,
    body: Repartir,
  },
  {
    slug: "problemas",
    label: "Cuando algo va mal",
    group: "Día a día",
    icon: LifeBuoy,
    body: Problemas,
  },
];
