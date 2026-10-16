import { registerCatalogue } from "@/lib/i18n";

import { es } from "./es";

/**
 * Register the evaluation's strings with the interface's catalogues.
 *
 * Imported first by every module of the evaluation that core loads lazily — the screen, the
 * stage questionnaire's slot, the administrator's tab, the guide's two trees and the
 * tutorial's two slides — so the Spanish entries are here before any of them renders, and the
 * reader's language is on its way.
 */
registerCatalogue("evaluation", es, {
  en: () => import("./en").then((module) => module.en),
});
