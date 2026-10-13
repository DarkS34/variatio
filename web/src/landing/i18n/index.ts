import { registerCatalogue } from "@/lib/i18n";

import { es } from "./es";

/**
 * Register the landing's strings with the interface's catalogues.
 *
 * Imported first by the landing's screen, the one module of the landing that core loads
 * lazily, so the Spanish entries are here before it renders and the reader's language is
 * on its way.
 */
registerCatalogue("landing", es, {
  en: () => import("./en").then((module) => module.en),
});
