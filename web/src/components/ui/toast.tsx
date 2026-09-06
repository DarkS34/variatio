import { X } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

// VOCABULARY RULE: the verb is kept. The button says "Aprobar", the notice says
// "Aprobado". Never "Operación completada con éxito", which names neither the operation
// nor why it is appearing now. If the notice cannot name the action, the action did not
// need a notice.
type Tone = "settled" | "attention" | "danger";

interface Toast {
  id: number;
  title: string;
  description?: string;
  tone: Tone;
}

type Push = (t: { title: string; description?: string; tone?: Tone }) => void;

const ToastContext = createContext<Push | null>(null);

export function useToast(): Push {
  const push = useContext(ToastContext);
  if (!push) throw new Error("useToast outside ToastProvider");
  return push;
}

const TONE: Record<Tone, string> = {
  settled: "border-[color-mix(in_oklch,var(--settled)_45%,transparent)]",
  attention: "border-[color-mix(in_oklch,var(--attention)_45%,transparent)]",
  danger: "border-destructive/50",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const next = useRef(0);

  const push = useCallback<Push>((t) => {
    const id = next.current++;
    setItems((prev) => [...prev, { ...t, tone: t.tone ?? "settled", id }]);
    // An error stays until it is dismissed. The rest leave on their own: an
    // acknowledgement you have to dismiss by hand stops being an acknowledgement and
    // becomes a chore.
    if (t.tone !== "danger") {
      setTimeout(() => setItems((prev) => prev.filter((item) => item.id !== id)), 5000);
    }
  }, []);

  const drop = (id: number) => setItems((prev) => prev.filter((item) => item.id !== id));

  return (
    <ToastContext.Provider value={push}>
      {children}
      {/* Two regions rather than one: `assertive` interrupts whatever the screen reader is
          reading, which is right for a failure and rude for "Aprobado". */}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="pointer-events-none fixed bottom-4 left-1/2 z-50 flex w-full max-w-sm -translate-x-1/2 flex-col gap-2"
      >
        {items
          .filter((item) => item.tone !== "danger")
          .map((item) => (
            <ToastCard key={item.id} item={item} onClose={() => drop(item.id)} />
          ))}
      </div>
      <div
        aria-live="assertive"
        aria-atomic="false"
        className="pointer-events-none fixed bottom-4 left-1/2 z-50 flex w-full max-w-sm -translate-x-1/2 flex-col gap-2"
      >
        {items
          .filter((item) => item.tone === "danger")
          .map((item) => (
            <ToastCard key={item.id} item={item} onClose={() => drop(item.id)} />
          ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastCard({ item, onClose }: { item: Toast; onClose: () => void }) {
  const { t } = useT();
  return (
    <div
      className={cn(
        "pointer-events-auto flex items-start gap-3 rounded-lg border bg-card p-3 shadow-overlay animate-fade-in",
        TONE[item.tone],
      )}
    >
      <div className="min-w-0 flex-1">
        <p className="font-medium">{item.title}</p>
        {item.description ? (
          <p className="mt-0.5 text-small text-muted-foreground">{item.description}</p>
        ) : null}
      </div>
      <button
        onClick={onClose}
        aria-label={t("ui.closeNotice")}
        className="rounded-md p-0.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <X className="size-3.5" />
      </button>
    </div>
  );
}
