/**
 * Generic deck-diff applier — given old and new lists of items, computes the
 * diff via `diffIDLists` and dispatches add/remove/update DOM mutations
 * through caller-supplied callbacks. Used by URL, tag, and member decks.
 */

import { diffIDLists } from "./deck-diffing.js";

export interface DeckDiffConfig<Item> {
  oldItems: Item[];
  newItems: Item[];
  getID: (item: Item) => number;
  removeElement: (id: number) => void;
  addElement: (item: Item) => void;
  updateElement?: (id: number, item: Item) => void;
}

export function applyDeckDiff<Item>(config: DeckDiffConfig<Item>): void {
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
