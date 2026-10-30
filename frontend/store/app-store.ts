import type { MemberCandidate, MemberItem } from "../types/member.js";
import type {
  DateFormatValue,
  DensityValue,
  SortOrderValue,
  ThemeValue,
  UtubSortValue,
  ViewModeValue,
} from "../types/preferences.js";
import type { UtubTag, UtubUrlItem } from "../types/url.js";
import type { UtubSummaryItem } from "../types/utub.js";
import type {
  ResolvedMemberSettings,
  ResolvedUtubSettings,
} from "../types/settings.js";
import { debug } from "../lib/debug.js";

const log = debug("store");

export interface UserPreferences {
  theme: ThemeValue;
  defaultView: ViewModeValue;
  defaultSort: SortOrderValue;
  density: DensityValue;
  dateFormat: DateFormatValue;
  utubSort: UtubSortValue;
  showRowCounts: boolean;
  showListTotals: boolean;
}

export interface AppState {
  utubs: UtubSummaryItem[]; // narrowed in Phase 6
  activeUTubID: number | null;
  activeUTubName: string | null;
  activeUTubDescription: string | null;
  isCurrentUserOwner: boolean;
  isCoCreator: boolean;
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
  // Resolved per-panel settings of the active UTub; null = no UTub / not yet delivered.
  settings: ResolvedUtubSettings | null;
  // Monotonic; bumped only by a successful scope-'utub' settings PATCH, in the
  // same setState that merges the response into `settings`.
  settingsVersion: number;
  // The acting member's own resolved view overrides for the active UTub; null =
  // no UTub / not yet delivered. Nulled on a UTub change like `settings`.
  memberSettings: ResolvedMemberSettings | null;
  // Monotonic; bumped only by a local personal-settings save's success write, in
  // the same setState that writes `memberSettings`.
  memberSettingsVersion: number;
  // Monotonic; bumped only by the short-link policy 403 branch, in the same
  // setState that writes `allow_short_links: false`. In-flight settings writers
  // compare it (via captureSettingsVersions) so a response that predates the
  // policy write cannot restore `true`.
  policyLearnedVersion: number;
  // Co-member add candidates for the active UTub, hydrated once when the add UI
  // opens (see loadCoMemberCandidates). Held only for the active UTub and
  // cleared on UTub switch / reset so it never leaks across UTubs.
  coMemberCandidates: MemberCandidate[];
  // False until the co-member fetch settles (success OR degrade-fail), so the
  // combobox can tell "haven't loaded yet" apart from "loaded and empty".
  coMemberCandidatesLoaded: boolean;
  preferences: UserPreferences;
  // Trash rows across both tabs (the badge on the Trash entry).
  trashCount: number;
}

function createInitialState(): AppState {
  return {
    utubs: [],
    activeUTubID: null,
    activeUTubName: null,
    activeUTubDescription: null,
    isCurrentUserOwner: false,
    isCoCreator: false,
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
    settings: null,
    settingsVersion: 0,
    memberSettings: null,
    memberSettingsVersion: 0,
    policyLearnedVersion: 0,
    coMemberCandidates: [],
    coMemberCandidatesLoaded: false,
    preferences: {
      theme: "system",
      defaultView: "list",
      defaultSort: "newest",
      density: "comfortable",
      dateFormat: "iso",
      utubSort: "recent_activity",
      showRowCounts: false,
      showListTotals: true,
    },
    trashCount: 0,
  };
}

let _state: AppState = createInitialState();

export type StoreListener = (
  changedKeys: ReadonlyArray<keyof AppState>,
) => void;

const _listeners = new Set<StoreListener>();
const _pendingNotifications: Array<ReadonlyArray<keyof AppState>> = [];
let _isNotifying = false;

/** Returns a shallow copy of the current state. */
export function getState(): AppState {
  return { ..._state };
}

/**
 * Registers a listener called synchronously after every `setState` that changed
 * at least one key (by reference), with the changed keys. Returns a disposer.
 */
export function subscribe(listener: StoreListener): () => void {
  _listeners.add(listener);
  return () => {
    _listeners.delete(listener);
  };
}

function flushNotifications(): void {
  if (_isNotifying) return;
  _isNotifying = true;
  try {
    while (_pendingNotifications.length > 0) {
      const changedKeys = _pendingNotifications.shift()!;
      for (const listener of Array.from(_listeners)) {
        // Skip a listener disposed by an earlier listener in this pass.
        if (!_listeners.has(listener)) continue;
        try {
          listener(changedKeys);
        } catch (error) {
          log("store listener threw", error);
        }
      }
    }
  } finally {
    _isNotifying = false;
  }
}

/** Merges partial into state. */
export function setState(partial: Partial<AppState>): void {
  const previous = _state;
  const changedKeys: Array<keyof AppState> = [];
  for (const key of Object.keys(partial) as Array<keyof AppState>) {
    if (!Object.is(previous[key], partial[key])) changedKeys.push(key);
  }
  const previousSettings = previous.settings;
  const previousMemberSettings = previous.memberSettings;
  Object.assign(_state, partial);

  // No UTub, no settings: a changed active UTub never keeps the previous
  // UTub's settings unless the caller supplies the new ones in the same call.
  if (
    "activeUTubID" in partial &&
    changedKeys.includes("activeUTubID") &&
    !("settings" in partial)
  ) {
    _state.settings = null;
    if (previousSettings !== null) changedKeys.push("settings");
  }
  if (
    "activeUTubID" in partial &&
    changedKeys.includes("activeUTubID") &&
    !("memberSettings" in partial)
  ) {
    _state.memberSettings = null;
    if (previousMemberSettings !== null) changedKeys.push("memberSettings");
  }

  if (changedKeys.length === 0) return;
  _pendingNotifications.push(changedKeys);
  flushNotifications();
}

/** Resets to initial state (for tests). */
export function resetStore(): void {
  _state = createInitialState();
  _pendingNotifications.length = 0;
}
