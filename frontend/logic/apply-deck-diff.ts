/**
 * Generic deck-diff applier — given old and new lists of items, computes the
 * diff via `diffIDLists` and dispatches add/remove/update DOM mutations
 * through caller-supplied callbacks. Used by URL, tag, and member decks.
 */

import { diffIDLists } from "./deck-diffing.js";

export interface DeckDiffConfig<T> {
  oldItems: T[];
  newItems: T[];
  getID: (item: T) => number;
  removeElement: (id: number) => void;
  addElement: (item: T) => void;
  updateElement?: (id: number, item: T) => void;
}

export function applyDeckDiff<T>(config: DeckDiffConfig<T>): void {
  const oldIDs = config.oldItems.map(config.getID);
  const newIDs = config.newItems.map(config.getID);

  const { toRemove, toAdd, toUpdate } = diffIDLists(oldIDs, newIDs);

  toRemove.forEach((id) => config.removeElement(id));

  toAdd.forEach((id) => {
    const item = config.newItems.find(
      (candidate) => config.getID(candidate) === id,
    );
    if (!item) return;
    config.addElement(item);
  });

  if (config.updateElement) {
    toUpdate.forEach((id) => {
      const item = config.newItems.find(
        (candidate) => config.getID(candidate) === id,
      );
      if (!item) return;
      config.updateElement!(id, item);
    });
  }
}
