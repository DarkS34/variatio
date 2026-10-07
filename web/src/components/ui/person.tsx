import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * A person as every list writes one (user's request, 2026-10-07): the name first, then the
 * username in the code face, then the badges — on one line, the name truncated before the rest.
 */
export function PersonName({
  name,
  username,
  muted = false,
  badges,
}: {
  name: string;
  username?: string | null;
  muted?: boolean;
  badges?: ReactNode;
}) {
  return (
    <span className="flex min-w-0 items-center gap-2">
      <span className={cn("truncate text-body font-medium", muted ? "text-muted-foreground" : "text-foreground")} title={name}>
        {name}
      </span>
      {username ? <span className="hidden shrink-0 font-mono text-muted-foreground sm:inline">{username}</span> : null}
      {badges}
    </span>
  );
}
