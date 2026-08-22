import { cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from "react";

import { cn } from "@/lib/utils";

interface Injected {
  id: string;
  "aria-describedby"?: string;
  "aria-invalid"?: boolean;
}

// A text placed above a control is not a label: without htmlFor you cannot click it to
// focus the field, and a screen reader announces the control unnamed. Across all of
// web/src there were <label> elements in two files, for fifteen controls.
//
// This exists as a piece, rather than as fifteen individual fixes, because fixing it by
// hand would have guaranteed that the next form is born without labels again.
export function Field({
  label,
  description,
  error,
  required,
  className,
  children,
}: {
  label: ReactNode;
  description?: ReactNode;
  error?: ReactNode;
  required?: boolean;
  className?: string;
  children: ReactElement | ((props: Injected) => ReactNode);
}) {
  const id = useId();
  const descId = `${id}-desc`;
  const errId = `${id}-err`;

  const describedBy = [description ? descId : null, error ? errId : null]
    .filter(Boolean)
    .join(" ");
  const injected: Injected = {
    id,
    "aria-describedby": describedBy || undefined,
    "aria-invalid": error ? true : undefined,
  };

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-micro font-condensed uppercase text-muted-foreground">
        {label}
        {required ? <span className="ml-1 text-destructive">*</span> : null}
      </label>

      {typeof children === "function"
        ? children(injected)
        : isValidElement(children)
          ? cloneElement(children as ReactElement<Injected>, injected)
          : children}

      {description ? (
        <p id={descId} className="text-small text-muted-foreground">
          {description}
        </p>
      ) : null}

      {error ? (
        <p id={errId} className="text-small text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  );
}
