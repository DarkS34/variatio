export interface WindowRow<T> {
  id: string;
  item: T;
  leaving: boolean;
}

export function slide<T extends { id: string }>(
  current: WindowRow<T>[],
  incoming: T[],
): WindowRow<T>[] {
  const live = new Set(incoming.map((item) => item.id));
  const gone = current.filter((row) => !live.has(row.id));

  const settled =
    gone.length === current.length - incoming.length &&
    incoming.every((item, index) => {
      const row = current[index];
      return row !== undefined && row.item === item && !row.leaving;
    }) &&
    gone.every((row) => row.leaving);
  if (settled) return current;

  return [
    ...incoming.map((item) => ({ id: item.id, item, leaving: false })),
    ...gone.map((row) => (row.leaving ? row : { ...row, leaving: true })),
  ];
}

export function purge<T>(rows: WindowRow<T>[]): WindowRow<T>[] {
  const kept = rows.filter((row) => !row.leaving);
  return kept.length === rows.length ? rows : kept;
}
