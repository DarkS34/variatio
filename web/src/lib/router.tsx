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
    if (to === window.location.pathname) return;
    if (options?.replace) window.history.replaceState({}, "", to);
    else window.history.pushState({}, "", to);
    setPath(to);
    window.scrollTo({ top: 0 });
  }, []);

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
