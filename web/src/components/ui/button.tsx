import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes, Ref } from "react";

import { cn } from "@/lib/utils";

import { DOOR_TONE } from "./tone";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-body font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        // The ink as a FILL (`--ink`), not the ink as text (`--primary`): in dark the text ink
        // is a pale sea, and a control filled with it was a white block.
        default: "bg-ink text-ink-foreground hover:bg-[color-mix(in_oklab,var(--ink)_88%,var(--ink-foreground))]",
        // The coral is the one colour this palette spends on "act here", and it belongs to
        // frontier actions — going to the stage that is holding the chain up, approving a
        // draft, launching the taggability review — never to an ordinary one; the moment it
        // is used for "save" it stops meaning anything. Painted with the FILL coral and its
        // dark label (`--attention-fill`); `--attention` is the deeper coral text reads in.
        attention:
          "bg-attention-fill text-attention-fill-foreground hover:bg-[color-mix(in_oklab,var(--attention-fill)_90%,var(--attention-fill-foreground))]",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        // The tutor's own colour, for a control outside its screen that opens it — «Trabajar
        // con el tutor». Its door's colour as text (`DOOR_TONE`) inside an inset ring, never a
        // fill: it sits on every saved exercise, and filled it was the loudest thing on the
        // screen, competing with the one action the screen asks for. The ring is the
        // button's own — a door in the bar is a word, a button needs an edge. Never inside
        // the tutor's screen, where "act here" stays the attention's.
        tutor: `${DOOR_TONE.tutor.face} ${DOOR_TONE.tutor.hover} ring-1 ring-inset ring-[color-mix(in_oklab,var(--tutor)_45%,transparent)]`,
        // A hairline and no material: a small control is flat. At `lg`/`xl` the same button
        // stands out of its block instead (`compoundVariants` below).
        outline: "border border-border bg-transparent hover:bg-accent hover:text-accent-foreground",
        // The chosen tint as a ground: on the clay a `--secondary` fill is the clay itself.
        secondary: "bg-sunk text-secondary-foreground hover:bg-accent",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-small",
        lg: "h-10 rounded-lg px-6",
        // The one move a screen leads to — "Continuar al Paso N", "Comenzar construcción":
        // a size for a button that is the decision, not one of several controls.
        xl: "h-12 rounded-inner px-7 text-heading [&_svg]:size-5",
        icon: "h-9 w-9",
        "icon-sm": "h-7 w-7 [&_svg]:size-3.5",
      },
    },
    // The screen's decision is the one control with depth: the coral drops a shadow of its
    // own colour, and a large secondary button stands out of its block (`.raised`) in place
    // of the hairline. Everything smaller stays flat.
    compoundVariants: [
      { variant: "attention", size: ["lg", "xl"], class: "shadow-act" },
      { variant: "outline", size: ["lg", "xl"], class: "raised border-transparent hover:bg-card" },
    ],
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /** Reaches the `<button>` itself, as a radio group's keyboard needs (`ui/radio.ts`). */
  ref?: Ref<HTMLButtonElement>;
}

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return <button className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}

export { buttonVariants };
