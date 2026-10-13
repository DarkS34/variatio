import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

/**
 * Five screens, one shell, no nested layouts: a router this small has no reason to be
 * a dependency. Data loading is TanStack Query's job, so routes only pick a component.
 */

interface RouterValue {
  path: string;
  navigate: (to: string, options?: { replace?: boolean }) => void;
}

const RouterContext = createContext<RouterValue>({ path: "/", navigate: () => {} });

export function RouterProvider({ children }: { children: ReactNode }) {
  const [path, setPath] = useState(() => window.location.pathname || "/");

  useEffect(() => {
    const sync = () => setPath(window.location.pathname || "/");
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);

  const navigate = useCallback((to: string, options?: { replace?: boolean }) => {
    if (to === window.location.pathname + window.location.search) return;
    if (options?.replace) window.history.replaceState({}, "", to);
    else window.history.pushState({}, "", to);
    setPath(pathOf(to));
    window.scrollTo({ top: 0 });
  }, []);

  const value = useMemo(() => ({ path, navigate }), [path, navigate]);
  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
}

/**
 * The route of an address: its path alone, as `window.location.pathname` gives it.
 *
 * A query belongs to the screen that reads it (`/demo?start=generate`, read by the demo's
 * page): kept in the path, it matched no route, and «Empezar en «Generar ejercicios»» landed
 * on the login form when pressed, though the same address typed in opened the demo.
 */
export function pathOf(to: string): string {
  const end = to.search(/[?#]/);
  return (end < 0 ? to : to.slice(0, end)) || "/";
}

/**
 * A router that lives in memory: the landing's demo navigates the real screens inside a
 * frame, and the browser's address bar must stay on the landing.
 *
 * Same context, same `Link`: a screen cannot tell which provider it sits under. The
 * `onNavigate` hook lets the frame scroll itself to its top, where a window would.
 */
export function MemoryRouterProvider({
  initialPath,
  onNavigate,
  children,
}: {
  initialPath: string;
  onNavigate?: (to: string) => void;
  children: ReactNode;
}) {
  const [path, setPath] = useState(initialPath);
  const navigate = useCallback(
    (to: string) => {
      setPath(to);
      onNavigate?.(to);
    },
    [onNavigate],
  );
  const value = useMemo(() => ({ path, navigate }), [path, navigate]);
  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
}

export function useRouter() {
  return useContext(RouterContext);
}

export function Link({
  to,
  className,
  children,
  onClick,
  title,
  "aria-current": current,
}: {
  to: string;
  className?: string;
  children: ReactNode;
  onClick?: () => void;
  title?: string;
  "aria-current"?: "page";
}) {
  const { navigate } = useRouter();
  return (
    <a
      href={to}
      className={className}
      title={title}
      aria-current={current}
      onClick={(event) => {
        if (event.metaKey || event.ctrlKey || event.shiftKey) return;
        event.preventDefault();
        onClick?.();
        navigate(to);
      }}
    >
      {children}
    </a>
  );
}
