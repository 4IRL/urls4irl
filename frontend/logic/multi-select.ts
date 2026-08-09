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
