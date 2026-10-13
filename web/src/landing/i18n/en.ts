import type { Catalogue } from "./es";

// Typed against `es`, as the core's `en` is, so a key that exists there and not here is a
// build error rather than a string that silently comes back in Spanish.
export const en: Catalogue = {
  // HEADER ---------------------------------------------------------------------------------
  "landing.nav.label": "Sections",
  "landing.nav.how": "How it works",
  "landing.nav.demo": "Demo",
  "landing.login": "Log in",
  "landing.language": "Language",
  "landing.home": "Variatio, home",

  // HERO -----------------------------------------------------------------------------------
  "landing.hero.kicker": "For teachers",
  "landing.hero.title": "Your notes, turned into new exercises.",
  "landing.hero.lead":
    "Variatio reads your notes and your exercises. Then it writes new exercises on what your class has already covered.",
  "landing.hero.demo": "Try the demo",
  "landing.hero.fact1": "Open models",
  "landing.hero.fact2": "Any subject",
  "landing.hero.fact3": "By invitation",

  // THE HERO'S EXAMPLE ---------------------------------------------------------------------
  "landing.example.label": "Example: from your notes to a new exercise",
  "landing.example.subjects": "Subject of the example",
  "landing.example.notes": "Your notes",
  "landing.example.syllabus": "Syllabus",
  "landing.example.known": "Already covered",
  "landing.example.target": "To practise",
  "landing.example.exercise": "New exercise",

  "landing.example.programming.subject": "Programming",
  "landing.example.programming.file": "Unit 5 · Recursion.pdf",
  "landing.example.programming.notes":
    "A recursive function calls itself. Each call solves a smaller case, until it reaches the base case.",
  "landing.example.programming.known1": "Functions",
  "landing.example.programming.known2": "Call stack",
  "landing.example.programming.target": "Recursion",
  "landing.example.programming.type": "Problem",
  "landing.example.programming.level": "Medium level",
  "landing.example.programming.statement":
    "Write a recursive function that adds up the digits of a natural number. State the base case and trace the calls for n\u00a0=\u00a0452.",

  "landing.example.pharmacology.subject": "Nursing",
  "landing.example.pharmacology.file": "Unit 3 · Dose calculation.pdf",
  "landing.example.pharmacology.notes":
    "The dose of many drugs depends on the patient's weight. It is then converted into the volume to give.",
  "landing.example.pharmacology.known1": "Units of measure",
  "landing.example.pharmacology.known2": "Concentration",
  "landing.example.pharmacology.target": "Dose calculation",
  "landing.example.pharmacology.type": "Problem",
  "landing.example.pharmacology.level": "Basic level",
  "landing.example.pharmacology.statement":
    "A child weighing 18\u00a0kg needs 15\u00a0mg/kg of paracetamol. The syrup contains 100\u00a0mg/ml. How many\u00a0ml should be given?",

  "landing.example.language.subject": "Grammar",
  "landing.example.language.file": "Unit 7 · Complex sentences.docx",
  "landing.example.language.notes":
    "A relative clause works like an adjective: it modifies a noun, which is called its antecedent.",
  "landing.example.language.known1": "Adjective",
  "landing.example.language.known2": "Complex sentence",
  "landing.example.language.target": "Relative clause",
  "landing.example.language.type": "Analysis",
  "landing.example.language.level": "Basic level",
  "landing.example.language.statement":
    "Underline the relative clause and name its antecedent: “The books that you lent me are on the table.”",

  // HOW ------------------------------------------------------------------------------------
  "landing.how.title": "Prepare the subject once. Generate whenever you want.",
  "landing.how.lead": "One prepared subject serves your whole class: you invite your students with a link.",
  "landing.how.step1Title": "Upload your documents",
  "landing.how.step1Body": "Your notes and your exercises, as PDF, Word or PowerPoint.",
  "landing.how.step2Title": "Review the syllabus",
  "landing.how.step2Body": "Variatio orders the concepts and their prerequisites. You correct what needs it.",
  "landing.how.step3Title": "Generate exercises",
  "landing.how.step3Body":
    "You choose concept, level and how many. The exercises imitate yours and never practise what comes later.",

  // DEMO -----------------------------------------------------------------------------------
  "landing.demo.title": "Try it without an account.",
  "landing.demo.lead": "The real application, full screen, with a sample subject.",
  "landing.demo.point1": "Walk through the three preparation steps.",
  "landing.demo.point2": "Generate exercises and find them saved.",
  "landing.demo.point3": "Nothing is real: restart it whenever you want.",
  "landing.demo.open": "Open the demo",
  "landing.demo.openGenerate": "Start at “Generate exercises”",
  "landing.demo.window": "Interactive demo",
  "landing.demo.sample": "Sample data",
  "landing.demo.reset": "Restart",
  "landing.demo.skip": "Go to “Generate exercises”",
  "landing.demo.frame": "Demonstration of Variatio",
  "landing.demoPage.back": "Home",
  "landing.demoPage.arriving": "Loading the sample documents…",
  "landing.demoPage.samples": "Add sample documents",
  "landing.demoPage.samplesHint": "In the application you would upload your own documents. Nothing is uploaded here.",
  "landing.demo.subject": "Lorem ipsum I",
  "landing.demo.teacher": "Sample teacher",

  // JOIN -----------------------------------------------------------------------------------
  "landing.join.title": "Have an invitation?",
  "landing.join.body": "Variatio works by invitation. Open the link you were sent and create your account in one step.",
  "landing.join.account": "Already have an account?",

  // FOOTER ---------------------------------------------------------------------------------
  "landing.footer.licence": "PolyForm Noncommercial 1.0.0 licence",
};
