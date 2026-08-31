import { useId } from "react";

import type { Language } from "@/lib/i18n";
import { cn } from "@/lib/utils";

/**
 * The flag of an interface language, drawn rather than written.
 *
 * It is an emblem and not a colour of the palette, which is why it is the one drawing in
 * the application that paints in values of its own: what it identifies is a language, and
 * a flag repainted in ink is a flag nobody recognises. Everything around it stays
 * achromatic, so the rule it looks like an exception to — colour is evidence — is the
 * reason it is allowed to be coloured at all.
 *
 * Emoji were the obvious alternative and are not usable here: Chrome on Windows draws no
 * flag at all, only the two regional letters, so the field would show «ES» and «GB» on the
 * platform most likely to be reading it.
 *
 * Both flags are drawn into the SAME 3:2 box, which stretches the Union Flag out of its
 * own 2:1. That is what every flag icon set does and what keeps two adjacent buttons the
 * same width; the alternative is one button's emblem a quarter wider than its neighbour's.
 */
export function LanguageFlag({
  language,
  className,
}: {
  language: Language;
  className?: string;
}) {
  // The counterchange of the Union Flag is a clip path, and a clip path is addressed by
  // id: two flags on one page sharing one id is one flag clipped by the other's shape.
  const clip = useId();
  return (
    <svg
      viewBox="0 0 60 40"
      aria-hidden
      focusable="false"
      className={cn("h-[0.875rem] w-[1.3125rem] shrink-0", className)}
    >
      {language === "es" ? (
        <>
          <rect width="60" height="40" fill="#AA151B" />
          <rect y="10" width="60" height="20" fill="#F1BF00" />
        </>
      ) : (
        // The construction is the flag's own, at its own 60x30, stretched by the group:
        // the diagonals are counterchanged against the cross, and drawing that by hand at
        // 60x40 means recomputing every offset for a shape that is defined at 2:1.
        <g transform="scale(1 1.3333)">
          <clipPath id={clip}>
            <path d="M30,15 h30 v15 z v15 h-30 z h-30 v-15 z v-15 h30 z" />
          </clipPath>
          <rect width="60" height="30" fill="#012169" />
          <path d="M0,0 L60,30 M60,0 L0,30" stroke="#FFFFFF" strokeWidth="6" />
          <path
            d="M0,0 L60,30 M60,0 L0,30"
            clipPath={`url(#${clip})`}
            stroke="#C8102E"
            strokeWidth="4"
          />
          <path d="M30,0 v30 M0,15 h60" stroke="#FFFFFF" strokeWidth="10" />
          <path d="M30,0 v30 M0,15 h60" stroke="#C8102E" strokeWidth="6" />
        </g>
      )}
    </svg>
  );
}
