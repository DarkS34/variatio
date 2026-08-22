import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// The type scale is six custom sizes (`text-body`, `text-small`, …), and tailwind-merge
// only knows the stock ones: anything else under `text-*` it files as a COLOUR, so
// `cn("text-primary-foreground", "text-small")` kept the size and dropped the colour —
// every small primary button was dark ink on dark green. Declaring the scale here is
// what lets the two coexist.
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [{ text: ["display", "title", "heading", "body", "small", "micro"] }],
    },
  },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
