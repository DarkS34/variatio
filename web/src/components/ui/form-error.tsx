/** A form's error, as the alert the screen reads out; nothing while there is none. */
export function FormError({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof Error ? error.message : String(error);
  return (
    <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-body text-destructive">
      {message}
    </p>
  );
}
