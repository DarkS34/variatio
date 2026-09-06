import { useState } from "react";

import { useLanguage, type Language } from "@/lib/i18n";

/**
 * The prompt language a create form offers, following the interface until somebody picks.
 *
 * Both create forms used to seed their state with `useState(useLanguage())`, which freezes
 * the value at the FIRST render. On the login path that render happens while the locale
 * store still holds the pre-session default, so the form kept `en` while the page around it
 * had already turned Spanish: measured, `<html lang>` read `es` and the pressed button read
 * "English", and only a reload agreed with itself.
 *
 * That is the most expensive default in the application to get wrong, because the prompt
 * language is chosen at creation and never after — the form's own help text says so. So the
 * choice is held as "not chosen yet" and the interface language is read live until there is
 * one, which keeps the intent (default to what the person reads) without the freeze.
 */
export function usePromptLanguage(): [Language, (language: Language) => void] {
  const ui = useLanguage();
  const [chosen, choose] = useState<Language | null>(null);
  return [chosen ?? ui, choose];
}
