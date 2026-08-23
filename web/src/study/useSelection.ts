import { useEffect, useState } from "react";

export function useSelection(ids: string[]) {
  const [selected, setSelected] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    const visible = new Set(ids);
    setSelected((current) => {
      const next = new Set([...current].filter((id) => visible.has(id)));
      return next.size === current.size ? current : next;
    });
  }, [ids]);

  const all = ids.length > 0 && selected.size === ids.length;
  const some = selected.size > 0 && !all;

  const toggle = (id: string, next: boolean) =>
    setSelected((current) => {
      const copy = new Set(current);
      if (next) copy.add(id);
      else copy.delete(id);
      return copy;
    });
  const toggleAll = (next: boolean) => setSelected(next ? new Set(ids) : new Set());
  const clear = () => setSelected(new Set());

  return { selected, all, some, toggle, toggleAll, clear };
}
