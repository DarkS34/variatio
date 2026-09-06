import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";

import { ConfirmDialog } from "./prompt";

/**
 * `window.confirm`, replaced everywhere at once.
 *
 * There were eighteen of them across the app, guarding everything from "delete a transcribed
 * page" to "delete the unit and its 28 concepts" — while deleting a workspace
 * opened a considered dialog that asks you to type the slug. Two visual languages for one
 * act, and the cheaper one happened to guard some of the more destructive operations.
 *
 * A native confirm also ignores the theme, the typography and the focus ring, cannot say
 * anything longer than one line without looking broken, and cannot mark a destructive
 * action as destructive.
 *
 * The shape is deliberately the same as the native one — ask, get a boolean, act — so a
 * call site changes by one `await` and nothing else:
 *
 *     if (!(await confirm({ title, body, tone: "danger" }))) return;
 *
 * A promise rather than a callback because that is what keeps the call sites flat: the
 * bodies that used `window.confirm` are early-return guards, and a callback would invert
 * every one of them.
 */
export interface ConfirmOptions {
  title: string;
  body?: ReactNode;
  confirmLabel?: string;
  tone?: "default" | "danger";
}

type Ask = (options: ConfirmOptions) => Promise<boolean>;

const ConfirmContext = createContext<Ask | null>(null);

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [options, setOptions] = useState<ConfirmOptions | null>(null);
  const settle = useRef<((answer: boolean) => void) | null>(null);

  const ask = useCallback<Ask>((next) => {
    // A second question while one is open answers the first with "no" rather than
    // stacking: two confirmations on screen is never what a caller meant, and leaving the
    // first promise unsettled would hang whatever awaited it.
    settle.current?.(false);
    setOptions(next);
    return new Promise<boolean>((resolve) => {
      settle.current = resolve;
    });
  }, []);

  const answer = (value: boolean) => {
    settle.current?.(value);
    settle.current = null;
    setOptions(null);
  };

  const value = useMemo(() => ask, [ask]);

  return (
    <ConfirmContext.Provider value={value}>
      {children}
      <ConfirmDialog
        open={options !== null}
        title={options?.title ?? ""}
        confirmLabel={options?.confirmLabel}
        tone={options?.tone}
        onCancel={() => answer(false)}
        onConfirm={() => answer(true)}
      >
        {options?.body}
      </ConfirmDialog>
    </ConfirmContext.Provider>
  );
}

/**
 * Ask before doing something. Outside the provider it falls back to the native dialog
 * rather than throwing: a screen that renders in a test harness without the provider
 * should still be able to ask.
 */
export function useConfirm(): Ask {
  const ask = useContext(ConfirmContext);
  return (
    ask ??
    (async (options) => window.confirm(typeof options.title === "string" ? options.title : ""))
  );
}
