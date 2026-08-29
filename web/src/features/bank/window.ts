export interface WindowRow<T> {
  id: string;
  item: T;
  leaving: boolean;
}

const asRow = <T extends { id: string }>(item: T): WindowRow<T> => ({
  id: item.id,
  item,
  leaving: false,
});

/**
 * Whether the source still holds something the window has not let in.
 *
 * What paces the feed: `step` admits one row per call, so this is what says whether another
 * call is owed. It reads the live rows only — one on its way out has already had its turn.
 */
export function behind<T extends { id: string }>(
  current: WindowRow<T>[],
  incoming: T[],
  limit: number,
): boolean {
  const shown = new Set(current.filter((row) => !row.leaving).map((row) => row.id));
  if (shown.size === 0) return incoming.length > 0;
  return incoming.slice(0, limit).some((item) => !shown.has(item.id));
}

/**
 * One step of the window towards `incoming`: at most ONE row admitted.
 *
 * The source arrives in bursts and not one by one — the builder writes a whole document at
 * once, and a reload replays the tagger's whole buffer — so taking it wholesale replaced the
 * rows between two blinks and left the tail of each burst on screen with no way to read
 * either the order or the movement. Here the OLDEST item the window has not got enters at
 * the top, everything under it shifts down, and whatever no longer fits within `limit` is
 * marked leaving so it can close its own space; `purge` drops it once that is over. The
 * feed therefore trails its source by a tick per row, which is the point — the count beside
 * it is what reports the totals.
 *
 * Two rules the shape depends on. An empty window is ARRIVING and not sliding, so it takes
 * what is there in one go: there is nothing on screen for a row to push. And a row the
 * source no longer lists is not dropped for that — it leaves by being pushed past `limit`,
 * or the feed would empty itself every time the source's own page moved on.
 */
export function step<T extends { id: string }>(
  current: WindowRow<T>[],
  incoming: T[],
  limit: number,
): WindowRow<T>[] {
  const target = incoming.slice(0, limit);
  const live = current.filter((row) => !row.leaving);
  const leaving = current.filter((row) => row.leaving);

  if (live.length === 0) {
    return target.length === 0 ? current : [...target.map(asRow), ...leaving];
  }

  const shown = new Set(live.map((row) => row.id));
  const fresh = new Map(target.map((item) => [item.id, item]));

  // `target` is newest first, so the last one the window is missing is the oldest of them.
  let admitted: T | undefined;
  for (const item of target) if (!shown.has(item.id)) admitted = item;

  // An item is edited in place while it is on screen — its concepts land after the item
  // itself does — and holding that back until some later turn would keep the tagger's work
  // invisible for as long as the queue lasts.
  let moved = admitted !== undefined;
  const refreshed = live.map((row) => {
    const item = fresh.get(row.id);
    if (item === undefined || item === row.item) return row;
    moved = true;
    return { ...row, item };
  });
  if (!moved) return current;

  const rows = admitted === undefined ? refreshed : [asRow(admitted), ...refreshed];
  return [
    ...rows.slice(0, limit),
    ...rows.slice(limit).map((row) => ({ ...row, leaving: true })),
    ...leaving,
  ];
}

export function purge<T>(rows: WindowRow<T>[]): WindowRow<T>[] {
  const kept = rows.filter((row) => !row.leaving);
  return kept.length === rows.length ? rows : kept;
}
