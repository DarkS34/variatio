import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { Logo } from "@/components/ui/logo";

/**
 * The shell the three unauthenticated screens share.
 *
 * They are the only part of the app rendered before a session exists, so they cannot use
 * `AppShell`: there is no pipeline to read, no stream to connect and no navigation that
 * would lead anywhere.
 */
export function AuthLayout({
  title,
  description,
  children,
  footer,
}: {
  title: string;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="flex min-h-full items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-2 font-semibold">
          <Logo className="size-5 text-primary" />
          Generador de variantes
        </div>

        <Card className="p-6">
          <h1 className="text-title">{title}</h1>
          {description ? (
            <p className="mt-1 text-body text-muted-foreground">{description}</p>
          ) : null}
          <div className="mt-5">{children}</div>
        </Card>

        {footer ? <div className="mt-4 text-center text-body">{footer}</div> : null}
      </div>
    </div>
  );
}

export function FormError({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof Error ? error.message : String(error);
  return (
    <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-body text-destructive">
      {message}
    </p>
  );
}
