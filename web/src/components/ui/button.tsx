import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-body font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        // The ultramarine is the one colour this palette spends on "act here", and it
        // belongs to frontier actions — going to the stage that is holding the chain up,
        // approving a draft, launching the taggability review — never to an ordinary one;
        // the moment it is used for "save" it stops meaning anything.
        //
        // The foreground is the ground's own hue at 262, not the 70 it carried until now:
        // that literal was the marigold's, left behind when the material changed, and it
        // sits outside `index.css` where `check:color` cannot see it. The file's own
        // convention is that a foreground matches its ground — `--destructive-foreground`
        // is 25, the red's.
        attention:
          "bg-attention text-attention-foreground hover:bg-[color-mix(in_oklch,var(--attention)_88%,var(--attention-foreground))]",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline: "border border-border bg-transparent hover:bg-accent hover:text-accent-foreground",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-small",
        lg: "h-10 rounded-md px-6",
        // The one move a screen leads to — "Continuar al Paso N", "Comenzar construcción":
        // a size for a button that is the decision, not one of several controls.
        xl: "h-12 rounded-md px-7 text-heading [&_svg]:size-5",
        icon: "h-9 w-9",
        "icon-sm": "h-7 w-7 [&_svg]:size-3.5",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return <button className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}

export { buttonVariants };
