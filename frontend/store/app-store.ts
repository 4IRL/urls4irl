import type { MemberItem } from "../types/member.js";
import type { UtubUrlItem } from "../types/url.js";
import type { UtubSummaryItem } from "../types/utub.js";

export interface AppState {
  utubs: UtubSummaryItem[]; // narrowed in Phase 6
  activeUTubID: number | null;
  activeUTubName: string | null;
  activeUTubDescription: string | null;
  isCurrentUserOwner: boolean;
  currentUserID: number | null;
  utubOwnerID: number | null;
  selectedURLCardID: number | null;
  selectedTagIDs: number[];
  urls: UtubUrlItem[]; // narrowed in Phase 7
  tags: unknown[]; // narrow in Phase 9
  members: MemberItem[]; // narrowed in Phase 8
}

function createInitialState(): AppState {
  return {
    utubs: [],
    activeUTubID: null,
    activeUTubName: null,
    activeUTubDescription: null,
    isCurrentUserOwner: false,
    currentUserID: null,
    utubOwnerID: null,
    selectedURLCardID: null,
    selectedTagIDs: [],
    urls: [],
    tags: [],
    members: [],
  };
}

let _state: AppState = createInitialState();

/** Returns a shallow copy of the current state. */
export function getState(): AppState {
  return { ..._state };
}

/** Merges partial into state. */
export function setState(partial: Partial<AppState>): void {
  Object.assign(_state, partial);
}

/** Resets to initial state (for tests). */
export function resetStore(): void {
  _state = createInitialState();
}
