/**
 * Pure logic for diffing ID lists used in URL, tag, and member deck updates.
 * DOM adapters live in the respective deck.js files.
 */

interface DiffResult {
  toRemove: number[];
  toAdd: number[];
  toUpdate: number[];
}

/**
 * Given two arrays of IDs (old state and new state), returns which IDs
 * should be removed, added, and updated.
 */
export function diffIDLists(oldIDs: number[], newIDs: number[]): DiffResult {
  return {
    toRemove: oldIDs.filter((id) => !newIDs.includes(id)),
    toAdd: newIDs.filter((id) => !oldIDs.includes(id)),
    toUpdate: oldIDs.filter((id) => newIDs.includes(id)),
  };
}
