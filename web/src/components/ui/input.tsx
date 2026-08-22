import type { InputHTMLAttributes, LabelHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

// The vertical padding is NOT shared. It used to be `py-2` here, on all three, while the
// two fixed-height controls also declared `h-9`: 36 px minus 2 of border minus 16 of
// padding leaves 18 px for a `text-body` line that needs 20, so every input and every select
// in the app clipped its own text by a pixel top and bottom — and the h-8 selects of the
// admin panel, with 14 px of room, clipped it by six. Height and padding are one decision
// and belong to whichever component fixes the height; only the textarea, which fixes none,
// keeps padding as its way of making room.
const field =
  "flex w-full rounded-md border border-input bg-background px-3 text-body shadow-none transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(field, "h-9 py-1", className)} {...props} />;
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(field, "min-h-20 resize-y py-2 leading-relaxed", className)}
      {...props}
    />
  );
}

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cn(field, "h-9 cursor-pointer py-1 pr-8", className)} {...props} />;
}

export function Label({ className, ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={cn("text-micro font-condensed uppercase text-muted-foreground", className)}
      {...props}
    />
  );
}
