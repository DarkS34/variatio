import type { CatalogueOf } from "@/lib/i18n";

/**
 * The landing's strings: the public page at `/` that presents the system to a visitor.
 *
 * Only `src/landing/` reads them, so they travel with its code: `./index.ts` registers them
 * with `lib/i18n` when the landing is loaded. The names the application already has — the
 * steps, the door — are read from the core's catalogue, so the page and the application
 * never call one thing two ways.
 */
export const es = {
  // HEADER ---------------------------------------------------------------------------------
  "landing.nav.label": "Secciones",
  "landing.nav.how": "Cómo funciona",
  "landing.nav.demo": "Demo",
  "landing.login": "Entrar",
  "landing.language": "Idioma",
  "landing.home": "Variatio, inicio",

  // HERO -----------------------------------------------------------------------------------
  "landing.hero.kicker": "Para docentes",
  "landing.hero.title": "Tus apuntes, convertidos en ejercicios nuevos.",
  "landing.hero.lead":
    "Variatio lee tus apuntes y tus ejercicios. Después crea ejercicios nuevos sobre lo que tu clase ya ha visto.",
  "landing.hero.demo": "Probar la demo",
  "landing.hero.fact1": "Modelos abiertos",
  "landing.hero.fact2": "Cualquier asignatura",
  "landing.hero.fact3": "Acceso por invitación",

  // THE HERO'S EXAMPLE ---------------------------------------------------------------------
  // Invented, by the user's request (2026-10-13): real-looking content in three subjects
  // far apart, so the picture says without a word that the subject is the teacher's.
  // `\u00a0` keeps a figure with its unit, and `n = 452` whole, on a narrow screen.
  "landing.example.label": "Ejemplo: de los apuntes a un ejercicio nuevo",
  "landing.example.subjects": "Asignatura del ejemplo",
  "landing.example.notes": "Tus apuntes",
  "landing.example.syllabus": "Temario",
  "landing.example.known": "Ya visto",
  "landing.example.target": "A practicar",
  "landing.example.exercise": "Ejercicio nuevo",

  "landing.example.programming.subject": "Programación",
  "landing.example.programming.file": "Tema 5 · Recursividad.pdf",
  "landing.example.programming.notes":
    "Una función recursiva se llama a sí misma. Cada llamada resuelve un caso más pequeño, hasta llegar al caso base.",
  "landing.example.programming.known1": "Funciones",
  "landing.example.programming.known2": "Pila de llamadas",
  "landing.example.programming.target": "Recursividad",
  "landing.example.programming.type": "Problema",
  "landing.example.programming.level": "Nivel medio",
  "landing.example.programming.statement":
    "Escribe una función recursiva que sume las cifras de un número natural. Indica el caso base y sigue las llamadas para n\u00a0=\u00a0452.",

  "landing.example.pharmacology.subject": "Enfermería",
  "landing.example.pharmacology.file": "Unidad 3 · Cálculo de dosis.pdf",
  "landing.example.pharmacology.notes":
    "La dosis de muchos fármacos depende del peso del paciente. Después se convierte en el volumen que hay que administrar.",
  "landing.example.pharmacology.known1": "Unidades de medida",
  "landing.example.pharmacology.known2": "Concentración",
  "landing.example.pharmacology.target": "Cálculo de dosis",
  "landing.example.pharmacology.type": "Problema",
  "landing.example.pharmacology.level": "Nivel básico",
  "landing.example.pharmacology.statement":
    "Un niño de 18\u00a0kg necesita 15\u00a0mg/kg de paracetamol. El jarabe contiene 100\u00a0mg/ml. ¿Cuántos\u00a0ml hay que administrar?",

  "landing.example.language.subject": "Lengua",
  "landing.example.language.file": "Tema 7 · La oración compuesta.docx",
  "landing.example.language.notes":
    "La subordinada adjetiva funciona como un adjetivo: complementa a un sustantivo, que se llama antecedente.",
  "landing.example.language.known1": "Adjetivo",
  "landing.example.language.known2": "Oración compuesta",
  "landing.example.language.target": "Subordinada adjetiva",
  "landing.example.language.type": "Análisis",
  "landing.example.language.level": "Nivel básico",
  "landing.example.language.statement":
    "Subraya la subordinada adjetiva y señala su antecedente: “Los libros que me prestaste están en la mesa”.",

  // HOW ------------------------------------------------------------------------------------
  "landing.how.title": "Prepara la asignatura una vez. Genera cuando quieras.",
  "landing.how.lead": "Una asignatura preparada sirve para toda tu clase: invitas a tus alumnos con un enlace.",
  "landing.how.step1Title": "Sube tus documentos",
  "landing.how.step1Body": "Tus apuntes y tus ejercicios, en PDF, Word o PowerPoint.",
  "landing.how.step2Title": "Revisa el temario",
  "landing.how.step2Body": "Variatio ordena los conceptos y sus prerrequisitos. Tú corriges lo necesario.",
  "landing.how.step3Title": "Genera ejercicios",
  "landing.how.step3Body":
    "Eliges concepto, nivel y cantidad. Los ejercicios imitan a los tuyos y no practican lo que viene después.",

  // DEMO -----------------------------------------------------------------------------------
  "landing.demo.title": "Pruébalo sin cuenta.",
  "landing.demo.lead": "La aplicación real, a pantalla completa, con una asignatura de ejemplo.",
  "landing.demo.point1": "Recorre los tres pasos de preparación.",
  "landing.demo.point2": "Genera ejercicios y encuéntralos guardados.",
  "landing.demo.point3": "Nada es real: puedes reiniciarla cuando quieras.",
  "landing.demo.open": "Abrir la demo",
  "landing.demo.openGenerate": "Empezar en «Generar ejercicios»",
  "landing.demo.window": "Demo interactiva",
  "landing.demo.sample": "Datos de ejemplo",
  "landing.demo.reset": "Reiniciar",
  "landing.demo.skip": "Ir a «Generar ejercicios»",
  "landing.demo.frame": "Demostración de Variatio",
  "landing.demoPage.back": "Portada",
  "landing.demoPage.arriving": "Cargando los documentos de ejemplo…",
  "landing.demoPage.samples": "Añadir documentos de ejemplo",
  "landing.demoPage.samplesHint": "En la aplicación subirías tus propios documentos. Aquí no se sube nada.",
  "landing.demo.subject": "Lorem ipsum I",
  "landing.demo.teacher": "Docente de ejemplo",

  // JOIN -----------------------------------------------------------------------------------
  "landing.join.title": "¿Tienes una invitación?",
  "landing.join.body":
    "Variatio funciona por invitación. Abre el enlace que te enviaron y crea tu cuenta en un paso.",
  "landing.join.account": "¿Ya tienes cuenta?",

  // FOOTER ---------------------------------------------------------------------------------
  "landing.footer.licence": "Licencia PolyForm Noncommercial 1.0.0",
} as const;

export type Catalogue = CatalogueOf<typeof es>;
