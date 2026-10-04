/**
 * How many rows of a list a correction touched: changed, added or removed.
 *
 * Counted as sets and never by position: taking the second of six criteria out is one
 * change, where a row-by-row comparison called it five. A row rewritten is one row gone
 * and one row new, hence the larger of the two counts and not their sum.
 */
export function changes<T>(saved: T[], draft: T[]): number {
  const left = saved.map((row) => JSON.stringify(row));
  let added = 0;
  for (const row of draft) {
    const at = left.indexOf(JSON.stringify(row));
    if (at < 0) added += 1;
    else left.splice(at, 1);
  }
  return Math.max(added, left.length);
}
