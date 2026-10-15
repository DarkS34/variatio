import "../i18n";

import type { ReactNode } from "react";

import { Block, Paragraph, Rows, SectionHead } from "@/features/guide/blocks";
import { useT } from "@/lib/i18n";

/**
 * The guide's section on the Socratic tutor, in Spanish.
 *
 * Here and not in `features/guide/es/`, because it is the tutor's: the guide's registry
 * (`features/guide/sections.tsx`) loads it only for an account the tutor is open to. Prose
 * per language like the rest of the guide, and `scripts/check-i18n.mjs` checks that both
 * languages answer for the section.
 */

function Tutor() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.use")} title={t("guide.sec.tutor")}>
        <p>
          Una de las puertas que se abren tras la construcción: una conversación con un tutor socrático, que
          guía con preguntas en vez de dar respuestas. Está en tu barra porque quien administra
          la instalación lo ha abierto a tu cuenta, y se abre con las mismas condiciones que
          «{t("nav.create")}». Está pensada para los alumnos: un alumno de la asignatura la usa
          aunque no pueda construir ni corregir nada.
        </p>
        <p>
          El tutor <strong>no da soluciones</strong>: te hace preguntas para que llegues tú a
          ellas, y lo que la asignatura explica te lo cuenta con sus propias palabras. Si
          quieres practicar, la puerta es «{t("nav.create")}».
        </p>
      </SectionHead>

      <Block title="Qué lo distingue de un chat cualquiera">
        <Paragraph>
          Cada respuesta se escribe con una ficha que el sistema prepara a partir de los
          artefactos de la asignatura. El alumno no la ve, pero decide lo que el tutor sabe en
          ese momento:
        </Paragraph>
        <Rows
          items={[
            {
              key: "focus",
              head: "El concepto del que se habla",
              body: "Sale del temario. Se fija con el primer mensaje que lo nombra con claridad y solo cambia cuando otro mensaje habla claramente de otra cosa. Un «no lo entiendo» no lo mueve, y hablar de algo que el temario pone antes tampoco. También puedes elegirlo tú en la línea «Sobre» del cuadro de escribir: entonces el tutor no deduce nada y trabaja ese concepto.",
            },
            {
              key: "notes",
              head: "Lo que explican los apuntes",
              body: "Los pasajes que el temario ancló a ese concepto y los fragmentos de los apuntes más parecidos al mensaje. El tutor parte de ellos y te los cuenta con sus palabras: no los copia, no te manda a leerlos y no te dice en qué tema o apartado están. Si quieres ver el documento, búscalo por tu cuenta.",
            },
            {
              key: "before",
              head: "Lo que hay que saber antes",
              body: "Los prerrequisitos directos del concepto. El tutor los da por sabidos: si preguntas por un concepto, trabaja ese concepto y no te lleva por los anteriores. Solo si dices que te falta algo previo te dice qué concepto repasar.",
            },
            {
              key: "map",
              head: "El mapa del concepto",
              body: "Un grafo del concepto en el orden en que se aprende: a la izquierda lo que da por sabido, en el centro el concepto y a la derecha lo que viene después. Sus demás relaciones son ramas de puntos con el nombre de la relación encima. La dibuja el sistema a partir del temario, nunca el modelo, así que no puede inventar una relación. No sale en cada respuesta: aparece la primera vez que la conversación llega a un concepto y cuando el tutor te manda a repasar algo anterior, con ese concepto marcado en coral.",
            },
            {
              key: "after",
              head: "Lo que viene después",
              body: "Los conceptos que el temario pone a continuación. El tutor no los introduce, y el sistema comprueba que no lo haga.",
            },
            {
              key: "bank",
              head: "El ejercicio que traes",
              body: "Si pegas un enunciado del banco, el tutor lo reconoce y sabe qué conceptos practica. Si te atascas, puede proponerte uno más sencillo del mismo concepto.",
            },
            {
              key: "criteria",
              head: "Los criterios de la asignatura",
              body: "Las convenciones y los errores que los apuntes señalan, redactados por el sistema y corregidos por un docente.",
            },
          ]}
        />
      </Block>

      <Block title="Lo que el sistema comprueba en cada respuesta">
        <Paragraph>
          Antes de que la leas, una respuesta pasa unas comprobaciones: tiene que hacer al
          menos una pregunta y no demasiadas, no puede llevar más de unas pocas líneas de
          código, no puede dibujar un diagrama por su cuenta, no puede copiar un pasaje de los
          apuntes, no puede mandarte a los apuntes ni a un tema, no puede introducir un concepto
          posterior y no puede sugerir lo que los criterios descartan. Si falla, el modelo
          escribe otra con el motivo; si vuelve a fallar, recibes una pregunta de reserva sobre
          el concepto. Por eso la respuesta aparece entera y no palabra a palabra.
        </Paragraph>
        <Paragraph>
          Las consultas administrativas (notas, fechas, entregas) y las preguntas ajenas a la
          asignatura reciben una respuesta fija, sin pasar por el modelo. Un mensaje que el
          guardián rechaza tampoco llega al modelo.
        </Paragraph>
      </Block>

      <Block title="Elegir de qué va el mensaje">
        <Paragraph>
          El cuadro de escribir tiene arriba una línea «{t("tutor.topic.label")}». Dice de qué
          concepto trata la conversación según el tutor. «{t("tutor.topic.choose")}» abre el
          temario: las unidades numeradas a un lado y los conceptos de la unidad al otro, con
          un buscador que encuentra un concepto por su nombre o por el de su unidad. Un clic
          elige el concepto y cierra el panel; el concepto vale para el mensaje que escribes.
        </Paragraph>
        <Paragraph>
          Con un concepto elegido y el cuadro vacío, el cuadro propone la pregunta más común,
          «{t("tutor.composer.suggestion", { name: "…" })}». La tecla Tab la escribe, y también
          el botón «{t("tutor.composer.tab")}» que aparece a su lado. Después puedes cambiarla
          o enviarla con Intro.
        </Paragraph>
        <Paragraph>
          Elegir es opcional: sin elegir, el tutor deduce el concepto de tu mensaje. Con el
          teclado no hace falta el ratón: escribe para buscar, las flechas arriba y abajo
          cambian de unidad, izquierda y derecha recorren los conceptos, Intro elige y Esc
          cierra. Con algo escrito en el buscador, arriba y abajo recorren los resultados. En una conversación nueva, la lista de unidades del centro abre el mismo
          panel por esa unidad.
        </Paragraph>
      </Block>

      <Block title="Escribir y leer">
        <Paragraph>
          Intro envía el mensaje; Mayús + Intro abre una línea nueva. La conversación tiene una
          altura fija y se desplaza dentro de su recuadro. Cuando ya trata de algo, el sistema
          le pone un título corto, que es el que ves en la lista; hasta entonces lleva su
          primera línea.
        </Paragraph>
        <Paragraph>
          Cada respuesta tiene dos partes: la explicación, en texto normal, y la pregunta con
          la que termina, al final de todo, más grande y en negrita, porque es lo que te toca
          contestar. A su lado va la marca del tutor, un signo de interrogación hecho de
          cuadrados: con el punto en coral en la pregunta que tienes abierta, y en gris en las
          que ya contestaste. Mientras el tutor escribe, esa misma marca se dibuja cuadrado a
          cuadrado.
        </Paragraph>
        <Paragraph>
          Cuando lo que se trabaja se escribe con notación matemática —una fórmula, una
          recurrencia, un coste—, el tutor la escribe como fórmula y no con palabras. En una
          pantalla estrecha, el mapa del concepto se pone de pie: lo anterior arriba, el
          concepto en medio, lo posterior debajo y las demás relaciones al final.
        </Paragraph>
      </Block>

      <Block title="La cola">
        <Paragraph>
          Cada respuesta es un trabajo de la cola, como una generación. Con el motor solo local,
          una construcción en marcha deja la conversación «en cola» hasta que termina. Puedes
          detener una respuesta que espera; el mensaje se queda marcado sin respuesta y puedes
          pedirla otra vez. Cada cuenta tiene una respuesta en camino a la vez. Mientras el
          tutor trabaja, un signo de interrogación se escribe cuadro a cuadro; en cola, el
          signo está hueco y quieto.
        </Paragraph>
      </Block>

      <Block title="El límite diario">
        <Paragraph>
          Quien administra la instalación puede limitar cuántos mensajes envía cada cuenta al
          tutor en un día. El límite suma todas tus asignaturas. Cuenta cada mensaje que entra
          en la cola, también la respuesta que pides otra vez con «{t("tutor.retry")}».
        </Paragraph>
        <Paragraph>
          Al llegar al límite, el mensaje no se envía. Encima del cuadro de escribir aparece un
          aviso que dice cuándo puedes escribir otra vez, en horas y minutos: «
          {t("tutor.limit.reached", { wait: "…" })}». El día es el de UTC, así que el límite
          se reabre a la misma hora para todos. Lo que habías escrito sigue en el cuadro.
        </Paragraph>
      </Block>

      <Block title="Quién ve qué">
        <Paragraph>
          Una conversación es de quien la tiene: nadie más de la asignatura la lee. La única
          excepción es quien administra la instalación, que puede leerlas todas desde «
          {t("admin.tab.workspaces")}», sin poder cambiarlas.
        </Paragraph>
        <Paragraph>
          Los criterios son de los docentes: la pestaña «{t("tutor.tab.criteria")}» solo
          aparece con permiso de edición. El sistema los genera con «{t("tutor.criteria.build")}
          », y se revisan y corrigen como cualquier paso de la construcción. La revisión muestra
          solo las frases, con cada unidad plegada; los conceptos y las fuentes de cada criterio
          aparecen al corregir. El método del tutor no se escribe aquí: vale en todas las
          asignaturas.
        </Paragraph>
        <Paragraph>
          Al corregir, una lista muestra los apartados y el apartado elegido se abre a su lado.
          Primero están los tres de toda la asignatura: «{t("tutor.criteria.general")}», «
          {t("tutor.criteria.terms")}» y «{t("tutor.criteria.admin.short")}». Después hay un
          apartado por cada unidad. Cada fila de la lista dice cuántos criterios tiene el
          apartado y cuántos cambios hay en él sin guardar. La barra de abajo guarda los cambios
          de todos los apartados a la vez.
        </Paragraph>
      </Block>

      <Block title={`Desde un ejercicio: «${t("tutor.fromExercise")}»`}>
        <Paragraph>
          En «{t("nav.mySubjects")}» y en la pestaña «{t("generate.tab.mine")}» de
          «{t("nav.create")}», cada ejercicio generado ofrece abrir una conversación sobre él;
          en los resultados de un lote, cada uno en cuanto se ha guardado. El botón va en el
          azul del tutor, el mismo de su puerta en la barra. El
          enunciado llega ya escrito al cuadro y el tutor empieza por los conceptos que ese
          ejercicio practica.
        </Paragraph>
      </Block>
    </div>
  );
}

export const BODIES: Record<string, () => ReactNode> = {
  tutor: Tutor,
};
