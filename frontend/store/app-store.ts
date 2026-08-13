import type { MemberItem } from "../types/member.js";
import type {
  DateFormatValue,
  DensityValue,
  SortOrderValue,
  ThemeValue,
  ViewModeValue,
} from "../types/preferences.js";
import type { UtubTag, UtubUrlItem } from "../types/url.js";
import type { UtubSummaryItem } from "../types/utub.js";

export interface UserPreferences {
  theme: ThemeValue;
  defaultView: ViewModeValue;
  defaultSort: SortOrderValue;
  density: DensityValue;
  dateFormat: DateFormatValue;
}

export interface AppState {
  utubs: UtubSummaryItem[]; // narrowed in Phase 6
  activeUTubID: number | null;
  activeUTubName: string | null;
  activeUTubDescription: string | null;
  isCurrentUserOwner: boolean;
  isCurrentUTubLocked: boolean;
  currentUserID: number | null;
  utubOwnerID: number | null;
  selectedURLCardID: number | null;
  selectedTagIDs: number[];
  multiSelectMode: boolean;
  selectedURLCardIDs: number[];
  urls: UtubUrlItem[]; // narrowed in Phase 7
  tags: UtubTag[]; // narrowed in Phase 9
  members: MemberItem[]; // narrowed in Phase 8
  preferences: UserPreferences;
}

function createInitialState(): AppState {
  return {
    utubs: [],
    activeUTubID: null,
    activeUTubName: null,
    activeUTubDescription: null,
    isCurrentUserOwner: false,
    isCurrentUTubLocked: false,
    currentUserID: null,
    utubOwnerID: null,
    selectedURLCardID: null,
    selectedTagIDs: [],
    multiSelectMode: false,
    selectedURLCardIDs: [],
    urls: [],
    tags: [],
    members: [],
    preferences: {
      theme: "system",
      defaultView: "list",
      defaultSort: "newest",
      density: "comfortable",
      dateFormat: "iso",
    },
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
