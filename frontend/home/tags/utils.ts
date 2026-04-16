import { getState } from "../../store/app-store.js";

// Returns tag IDs currently in the store
export function currentTagDeckIDs(): number[] {
  return getState().tags.map((tag) => tag.id);
}

export function isTagInUTubTagDeck(utubTagID: number): boolean {
  return currentTagDeckIDs().includes(utubTagID);
}

export function isATagSelected(): boolean {
  return getState().selectedTagIDs.length > 0;
}
