/**
 * Pure logic for the URL multi-select selection array.
 * Framework-free array math; DOM/state glue lives in
 * frontend/home/urls/bulk-actions/bulk-selection.js.
 */

/**
 * Returns a new array with `id` toggled: removed if already present,
 * otherwise appended. Never mutates the input.
 */
export function toggleId(ids: number[], id: number): number[] {
  return ids.includes(id)
    ? ids.filter((existingId) => existingId !== id)
    : [...ids, id];
}

/**
 * Returns a new array with every id in `removed` filtered out of `ids`.
 * Never mutates the input.
 */
export function removeIds(ids: number[], removed: number[]): number[] {
  return ids.filter((existingId) => !removed.includes(existingId));
}

/**
 * Returns a new array with duplicate ids collapsed, preserving first-seen
 * order. Never mutates the input.
 */
export function dedupe(ids: number[]): number[] {
  return [...new Set(ids)];
}

/**
 * Returns a new array that flips membership of every id in `toggle` against
 * `current` (a symmetric difference): each currently-selected id NOT in `toggle`
 * is kept (e.g. hidden-but-selected survivors), and each id in `toggle` NOT
 * currently selected is added. Ids in both are dropped. Preserves order (kept
 * survivors first, then newly-toggled-on ids in `toggle` iteration order) and
 * never mutates the inputs.
 */
export function symmetricToggle(
  current: number[],
  toggle: Set<number>,
): number[] {
  return [
    ...current.filter((existingId) => !toggle.has(existingId)),
    ...[...toggle].filter((toggledId) => !current.includes(toggledId)),
  ];
}
