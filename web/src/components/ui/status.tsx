import { Lock } from "lucide-react";

import { STATUS, statusKey, type Tone } from "@/lib/status";
import type { ArtifactStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const TONE_CLASS: Record<Tone, string> = {
  settled: "text-settled",
  attention: "text-attention",
  primary: "text-primary",
  muted: "text-muted-foreground",
};

export function StatusMark({
  status,
  blocked = false,
  size = "sm",
  className,
}: {
  status: ArtifactStatus;
  blocked?: boolean;
  size?: "sm" | "md";
  className?: string;
}) {
  const key = statusKey(status, blocked);
  const meta = STATUS[key];
  const box = size === "sm" ? "size-2.5" : "size-3.5";
  const tone = TONE_CLASS[meta.tone];

  if (meta.shape === "lock") {
    return <Lock role="img" aria-label={meta.label} className={cn(box, tone, "shrink-0", className)} />;
  }

  // An SVG rather than a div with a border: "broken ring" and "ring with a sweep" are not
  // drawable with border-radius, and having all six in one coordinate system is what makes
  // them read as a family instead of as six unrelated icons.
  return (
    <svg
      viewBox="0 0 12 12"
      role="img"
      aria-label={meta.label}
      className={cn(box, tone, "shrink-0", className)}
    >
      {meta.shape === "disc" ? <circle cx="6" cy="6" r="4.5" fill="currentColor" /> : null}

      {meta.shape === "ring" ? (
        <circle cx="6" cy="6" r="4" fill="none" stroke="currentColor" strokeWidth="2" />
      ) : null}

      {meta.shape === "broken" ? (
        <circle
          cx="6"
          cy="6"
          r="4"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeDasharray="6.3 4.2"
          transform="rotate(-45 6 6)"
        />
      ) : null}

      {meta.shape === "sweep" ? (
        <>
          <circle cx="6" cy="6" r="4" fill="none" stroke="currentColor" strokeWidth="2" opacity="0.3" />
          <circle
            cx="6"
            cy="6"
            r="4"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeDasharray="7 18"
          >
            <animateTransform
              attributeName="transform"
              type="rotate"
              from="0 6 6"
              to="360 6 6"
              dur="1.4s"
              repeatCount="indefinite"
            />
          </circle>
        </>
      ) : null}

      {meta.shape === "dash" ? (
        <line x1="2" y1="6" x2="10" y2="6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      ) : null}
    </svg>
  );
}
