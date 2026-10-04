import { registerCatalogue } from "@/lib/i18n";

import { es } from "./es";

/**
 * Register the tutor's strings with the interface's catalogues.
 *
 * Imported first by every module of the tutor that core loads lazily — the screen, the
 * administrator's reading of the conversations and the guide's two trees — so the Spanish
 * entries are here before any of them renders, and the reader's language is on its way.
 */
registerCatalogue("tutor", es, {
  en: () => import("./en").then((module) => module.en),
});
