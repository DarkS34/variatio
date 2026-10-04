import "../i18n";

import type { ReactNode } from "react";

import { Alert } from "@/components/ui/misc";
import {
  Block,
  Detail,
  Facts,
  Paragraph,
  Rows,
  SectionHead,
  Steps,
} from "@/features/guide/blocks";
import { useT } from "@/lib/i18n";

import { ARM_META } from "../arms";

/**
 * The guide's section on the evaluation, and the evaluation's part of how a building step
 * closes, in Spanish.
 *
 * Here and not in `features/guide/es/`, because it is the evaluation's: the guide's
 * registry (`features/guide/sections.tsx`) loads it only for an account the evaluation is
 * open to. Prose per language like the rest of the guide, and `scripts/check-i18n.mjs`
 * checks that both languages answer for the section.
 */

const ARM_ORDER = ["naive", "rag", "system"] as const;

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
              body: "Donde abre la pantalla. Eliges de qué concepto y de qué tipo quieres el ejercicio: es el mismo formulario de «Generar ejercicios», sin dos controles —cuántos ejercicios y si el modelo delibera—, porque una comparación es siempre uno por versión. El modelo que escribe las dos propuestas locales no se elige aquí: lo fija quien administra en «Administración → Evaluaciones», y la comercial usa el suyo.",
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
              una se desplaza por dentro. El botón coral «{t("reveal.read")}» de su cabecera la
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

/**
 * The questionnaire at the foot of a building step, as the guide's «Cómo se cierra este
 * paso» tells it: the common guide draws this only for an account the questionnaire is
 * asked of (`useAsksStageReview`), since nobody else has the questionnaire on screen.
 */
export function StageReviewGuide() {
  const { t } = useT();
  return (
    <>
      <Paragraph>
        Antes de la oferta de corregir, al pie de lo construido, está «
        {t("stageReview.openTitle")}». Despliega debajo un cuestionario corto: cinco
        afirmaciones, y para cada una dices cuánto estás de acuerdo, del 1 («totalmente en
        desacuerdo») al 5 («totalmente de acuerdo»). Son las mismas cinco ideas en los tres
        pasos. Puedes dejarlo a medias y volver, porque media respuesta también es un dato, y
        en cuanto guardas puedes cerrarlo sin perder nada. Está ahí aunque el paso anterior se
        haya vuelto a abrir: lo que se valora es lo que hay construido. Valorar es opcional,
        como corregir.
      </Paragraph>
      <Detail title="Qué se guarda de la valoración">
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
    </>
  );
}

export const BODIES: Record<string, () => ReactNode> = {
  evaluate: Evaluate,
};
