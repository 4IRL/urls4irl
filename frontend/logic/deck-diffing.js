/**
 * Pure logic for diffing ID lists used in URL, tag, and member deck updates.
 * DOM adapters live in the respective deck.js files.
 */

/**
 * Given two arrays of IDs (old state and new state), returns which IDs
 * should be removed, added, and updated.
 *
 * @param {number[]} oldIDs
 * @param {number[]} newIDs
 * @returns {{ toRemove: number[], toAdd: number[], toUpdate: number[] }}
 */
export function diffIDLists(oldIDs, newIDs) {
  return {
    toRemove: oldIDs.filter((id) => !newIDs.includes(id)),
    toAdd: newIDs.filter((id) => !oldIDs.includes(id)),
    toUpdate: oldIDs.filter((id) => newIDs.includes(id)),
  };
}
