import { ChevronRight } from "lucide-react";
import { useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

export function SectionHead({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-2">
      <p className="text-micro font-condensed uppercase text-muted-foreground">{eyebrow}</p>
      <h2 className="text-title">{title}</h2>
      <div className="max-w-[74ch] space-y-2 text-body">{children}</div>
    </div>
  );
}

export function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h3 className="text-heading">{title}</h3>
      {children}
    </section>
  );
}

export function Paragraph({ children }: { children: ReactNode }) {
  return <p className="max-w-[74ch] text-body text-muted-foreground">{children}</p>;
}

export function Facts({ items }: { items: { label: string; value: ReactNode }[] }) {
  return (
    <div className="grid rounded-lg border border-border bg-card md:grid-cols-3">
      {items.map((item, index) => (
        <div
          key={item.label}
          className={cn(
            "p-4",
            index > 0 && "border-t border-border md:border-l md:border-t-0",
          )}
        >
          <p className="text-micro font-condensed uppercase text-muted-foreground">{item.label}</p>
          <div className="mt-1 text-body">{item.value}</div>
        </div>
      ))}
    </div>
  );
}

export function Steps({ items }: { items: ReactNode[] }) {
  return (
    <ol className="space-y-3">
      {items.map((item, index) => (
        <li key={index} className="flex gap-3">
          <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/12 text-small font-semibold nums text-primary">
            {index + 1}
          </span>
          <div className="max-w-[74ch] space-y-1 text-body">{item}</div>
        </li>
      ))}
    </ol>
  );
}

export function Rows({ items }: { items: { key: string; head: ReactNode; body: ReactNode }[] }) {
  return (
    <div className="divide-y divide-border rounded-lg border border-border bg-card">
      {items.map((item) => (
        <div key={item.key} className="grid gap-1 p-4 md:grid-cols-[13rem_minmax(0,1fr)] md:gap-4">
          <div className="text-body font-medium">{item.head}</div>
          <div className="text-small text-muted-foreground">{item.body}</div>
        </div>
      ))}
    </div>
  );
}

export function Detail({ title, children }: { title: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-border">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((was) => !was)}
        className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-body font-medium transition-colors hover:bg-accent"
      >
        <ChevronRight
          className={cn(
            "size-3.5 shrink-0 text-muted-foreground transition-transform",
            open && "rotate-90",
          )}
        />
        {title}
      </button>
      {open ? (
        <div className="max-w-[74ch] space-y-2 border-t border-border p-3 text-small text-muted-foreground">
          {children}
        </div>
      ) : null}
    </div>
  );
}
