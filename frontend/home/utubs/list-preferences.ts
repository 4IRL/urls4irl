import type { UtubSortValue } from "../../types/preferences.js";

import { $ } from "../../lib/globals.js";
import { debug } from "../../lib/debug.js";
import { getState, setState } from "../../store/app-store.js";
import { isUtubSortValue } from "../../types/preferences.js";
import { reorderUTubDeck } from "./sort.js";

// Leaf module (imports only types, the store, the DOM and sort.ts). It must not
// import the settings section or `panel-settings`; sort.ts must not import it
// back. list-settings-section.ts is the only writer of the edit tokens and
// settled marks.

const log = debug("utubs");

export type ListPreferenceUpdate =
  | { field: "utubSort"; value: UtubSortValue }
  | { field: "showRowCounts"; value: boolean }
  | { field: "showListTotals"; value: boolean };

export type ListPreferenceField = ListPreferenceUpdate["field"];

export const LIST_PREFERENCE_FIELDS: readonly ListPreferenceField[] = [
  "utubSort",
  "showRowCounts",
  "showListTotals",
];

const DECK_CLASS_BY_FIELD = {
  showRowCounts: { className: "showUTubRowCounts", whenValue: true },
  showListTotals: { className: "hideListTotals", whenValue: false },
} as const;

// ---------------------------------------------------------------------------
// Apply
// ---------------------------------------------------------------------------

// Writes one validated field to the store and toggles the matching #UTubDeck
// class (none for the sort field). No token or version checks, no reorder.
export function applyListPreference(update: ListPreferenceUpdate): void {
  recordSavedPreference(update);
  if (update.field === "utubSort") return;
  const { className, whenValue } = DECK_CLASS_BY_FIELD[update.field];
  $("#UTubDeck").toggleClass(className, update.value === whenValue);
}

// Writes only the saved value to the store (no class, no reorder).
export function recordSavedPreference(update: ListPreferenceUpdate): void {
  setState({
    preferences: { ...getState().preferences, [update.field]: update.value },
  });
}

// ---------------------------------------------------------------------------
// Edit tokens and settled marks
// ---------------------------------------------------------------------------

interface FieldTracking {
  counter: number;
  latest: number | null;
  settledAt: number;
}

function freshTracking(): Record<ListPreferenceField, FieldTracking> {
  return {
    utubSort: { counter: 0, latest: null, settledAt: 0 },
    showRowCounts: { counter: 0, latest: null, settledAt: 0 },
    showListTotals: { counter: 0, latest: null, settledAt: 0 },
  };
}

let tracking = freshTracking();
let prefsVersion = 0;

export function resetListPreferenceTracking(): void {
  tracking = freshTracking();
  prefsVersion = 0;
}

// Increments the field's counter, records it as the latest token and returns it.
export function markEdit(field: ListPreferenceField): number {
  const entry = tracking[field];
  entry.counter += 1;
  entry.latest = entry.counter;
  return entry.counter;
}

export function latestToken(field: ListPreferenceField): number | null {
  return tracking[field].latest;
}

export function isLatestEdit({
  field,
  token,
}: {
  field: ListPreferenceField;
  token: number;
}): boolean {
  return tracking[field].latest === token;
}

export function hasOutstandingEdit(field: ListPreferenceField): boolean {
  return tracking[field].latest !== null;
}

// Records the settle in prefsVersion and stamps the field's settledAt, whether or
// not `token` is still the latest (a superseded save's echo is still a committed
// value a stale rebuild response must not overwrite). Clears the field's mark
// only if `token` is still the latest.
export function settleEdit({
  field,
  token,
}: {
  field: ListPreferenceField;
  token: number;
}): void {
  const entry = tracking[field];
  if (entry.latest === token) entry.latest = null;
  prefsVersion += 1;
  entry.settledAt = prefsVersion;
}

export function clearAllEdits(): void {
  for (const field of LIST_PREFERENCE_FIELDS) {
    tracking[field].latest = null;
  }
}

export function getPrefsVersion(): number {
  return prefsVersion;
}

// ---------------------------------------------------------------------------
// Reseed
// ---------------------------------------------------------------------------

type ReseedListener = (changedFields: ListPreferenceField[]) => void;

let reseedListener: ReseedListener | null = null;

export function setReseedListener(listener: ReseedListener | null): void {
  reseedListener = listener;
}

function readValidUpdate({
  preferences,
  field,
}: {
  preferences: unknown;
  field: ListPreferenceField;
}): ListPreferenceUpdate | null {
  if (typeof preferences !== "object" || preferences === null) return null;
  const value = (preferences as Record<string, unknown>)[field];
  if (field === "utubSort") {
    return isUtubSortValue(value) ? { field, value } : null;
  }
  return typeof value === "boolean" ? { field, value } : null;
}

// Applies each non-skipped field of a `GET /utubs` `preferences` object. A field
// is skipped when it has an outstanding edit token, or when a save for it
// settled after the request was issued (`settledAt > capturedVersion`). Fails
// closed: a missing or malformed object or value keeps the current store value.
// Returns the fields whose stored value changed.
export function reseedListPreferences({
  preferences,
  capturedVersion,
}: {
  preferences: unknown;
  capturedVersion: number;
}): ListPreferenceField[] {
  const changed: ListPreferenceField[] = [];
  for (const field of LIST_PREFERENCE_FIELDS) {
    if (hasOutstandingEdit(field)) continue;
    if (tracking[field].settledAt > capturedVersion) continue;
    const update = readValidUpdate({ preferences, field });
    if (update === null) continue;
    const previous = getState().preferences[field];
    applyListPreference(update);
    if (previous !== update.value) changed.push(field);
  }

  if (changed.length > 0 && reseedListener !== null) {
    try {
      reseedListener(changed);
    } catch (error) {
      // A render exception in the settings section must never abort a rebuild.
      log("reseed listener threw", error);
    }
  }
  return changed;
}

// Call after buildUTubDeck: when the store's sort differs from the sort the
// response was built with (the reseed skipped the sort field), the rebuilt deck
// is in the stale response's order, so reorder it to the store sort. Never scrolls.
export function syncDeckOrderToStoreSort({
  responseSort,
}: {
  responseSort: unknown;
}): void {
  if (!isUtubSortValue(responseSort)) return;
  const storeSort = getState().preferences.utubSort;
  if (storeSort === responseSort) return;
  reorderUTubDeck(storeSort);
}
