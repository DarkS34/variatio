import type { ReactNode } from "react";

export function EmptyState({
  icon,
  title,
  titleAs: Title = "p",
  action,
  children,
}: {
  icon?: ReactNode;
  title: string;
  /** What element the title is. A `p` by default, because an empty state normally sits
   *  UNDER the screen's own heading and a second `h1` there would claim to be the page.
   *  `h1` is for the one screen that is nothing but its empty state — `NoWorkspace`, where
   *  the alternative is a page with no heading at all for a screen reader. */
  titleAs?: "p" | "h1";
  /** What to do so that it stops being empty. An empty screen with no action is a hole;
   *  with one it is where the work starts. Optional on purpose — some holes genuinely have
   *  no action, a search with no results being the obvious one, and forcing a button there
   *  would mean inventing one. */
  action?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border p-12 text-center">
      {icon ? <div className="text-muted-foreground [&_svg]:size-8">{icon}</div> : null}
      <Title className="font-display font-expanded text-title">{title}</Title>
      {children ? <div className="max-w-md text-muted-foreground">{children}</div> : null}
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  );
}
