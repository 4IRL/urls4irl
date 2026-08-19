import { $ } from "../../../lib/globals.js";
import { debug } from "../../../lib/debug.js";
import { AppEvents, emit } from "../../../lib/event-bus.js";
import { dedupe, removeIds, toggleId } from "../../../logic/multi-select.js";
import { getState, setState } from "../../../store/app-store.js";
import { VISIBLE_URL_SELECTOR } from "../utils.js";
import { isAnyBulkPickerOpen } from "./picker-guard.js";

const log = debug("urls:cards");

const MULTI_SELECTED_CLASS = "multiSelected";
const CHECKBOX_SELECTOR = ".urlSelectCheckbox";
const GO_TO_ICON_SELECTOR = ".goToUrlIcon";
const VISIBLE_ON_FOCUS_CLASS = "visible-on-focus";

/** Resolve a URL card by its utuburlid. */
function urlCardById(id: number): JQuery {
  return $(`.urlRow[utuburlid=${id}]`);
}

/** Read a card's utuburlid as a number (NaN when absent/unparseable). */
function urlCardId(urlCard: JQuery): number {
  return parseInt(urlCard.attr("utuburlid") ?? "", 10);
}

/** Paint the multi-select marker on a card (or strip it). */
function markCard({
  urlCard,
  isSelected,
}: {
  urlCard: JQuery;
  isSelected: boolean;
}): void {
  const ariaChecked = isSelected ? "true" : "false";
  if (isSelected) {
    urlCard.addClass(MULTI_SELECTED_CLASS);
  } else {
    urlCard.removeClass(MULTI_SELECTED_CLASS);
  }
  // aria-checked lives on both the row (the whole-card marker, source for the
  // JS/Playwright assertions) and the .urlSelectCheckbox span, which is the
  // element that actually carries role="checkbox" and is what assistive tech
  // announces — so its checked state must track selection, not stay static.
  urlCard.attr("aria-checked", ariaChecked);
  urlCard.find(CHECKBOX_SELECTOR).attr("aria-checked", ariaChecked);
}

/**
 * Commit a new selection array to the store (always a fresh array — never a
 * mutation of the shared getState() reference) and announce the change.
 */
function commitSelection(nextSelectedURLCardIDs: number[]): void {
  setState({ selectedURLCardIDs: nextSelectedURLCardIDs });
  emit(AppEvents.URL_MULTISELECT_CHANGED, {
    selectedURLCardIDs: nextSelectedURLCardIDs,
  });
}

/** Current selected URL-card ids (the store's source of truth). */
export function getSelectedURLCardIDs(): number[] {
  return getState().selectedURLCardIDs;
}

/**
 * Toggle a single card's membership in the selection: add if absent, remove if
 * present. Re-marks the DOM row to match and emits URL_MULTISELECT_CHANGED.
 */
export function toggleURLCardSelection(id: number): void {
  const next = toggleId(getState().selectedURLCardIDs, id);
  log("toggle URL card selection", { id, next });
  markCard({ urlCard: urlCardById(id), isSelected: next.includes(id) });
  commitSelection(next);
}

/** Empty the selection and strip every multi-select mark from the deck. */
export function clearURLSelection(): void {
  // Defense-in-depth: the selection is snapshotted while a bulk sub-picker is
  // open, so it must not be cleared out from under an open/in-flight picker. The
  // normal mode-exit path (bulk-mode.ts) calls closeAllPickers() BEFORE this, so
  // no picker is open by the time a legitimate exit reaches here; this guard only
  // fires for a caller that reaches clearURLSelection() without that ordering.
  if (isAnyBulkPickerOpen()) return;
  log("clear URL selection");
  const marked = $(`.urlRow.${MULTI_SELECTED_CLASS}`);
  marked.removeClass(MULTI_SELECTED_CLASS).attr("aria-checked", "false");
  marked.find(CHECKBOX_SELECTOR).attr("aria-checked", "false");
  // Strip the stray single-select go-to-icon reveal from every row. Tapping a
  // row in multi-select focuses it, and setFocusEventListenersOnURLCard
  // (cards/cards.ts) adds `.visible-on-focus` to its .goToUrlIcon; the focusout
  // handler only removes it when the icon button ITSELF blurs, and the
  // multi-select tap path never runs the single-select deselect cleanup
  // (selection.ts) that would otherwise strip it. Because exiting mode does not
  // re-render the deck, those rows keep the class — and once the in-mode
  // `#URLDeck.multiSelectActive .goToUrlIcon` suppression is gone,
  // `.visible-on-focus`'s `visibility: visible !important` (layout.css) would
  // show a stray go-to icon on unfocused rows. This runs on both Clear and Exit
  // (exitMultiSelectMode calls clearURLSelection).
  $(`.urlRow ${GO_TO_ICON_SELECTOR}`).removeClass(VISIBLE_ON_FOCUS_CLASS);
  commitSelection([]);
}

/**
 * Union every currently-visible row's id into the existing selection (deduped),
 * preserving any already-selected hidden ids — it never replaces the array
 * wholesale. Only rows matching VISIBLE_URL_SELECTOR are added.
 */
export function selectAllVisibleURLCards(): void {
  // Selection is locked while a bulk sub-picker (tag or copy) is open —
  // defense-in-depth for any caller that reaches this export without going
  // through bulk-bar.ts's own call-site guard.
  if (isAnyBulkPickerOpen()) return;
  const visibleIDs: number[] = [];
  $(VISIBLE_URL_SELECTOR).each((_index, element) => {
    const id = urlCardId($(element));
    if (!Number.isNaN(id)) visibleIDs.push(id);
  });
  const next = dedupe([...getState().selectedURLCardIDs, ...visibleIDs]);
  log("select all visible URL cards", { visibleIDs, next });
  setState({ selectedURLCardIDs: next });
  reapplyAllMultiSelectMarks();
  emit(AppEvents.URL_MULTISELECT_CHANGED, { selectedURLCardIDs: next });
}

/**
 * Drop the given ids from the selection (used by the deck-diff reconcile when a
 * URL is genuinely removed) and emit the reduced array.
 */
export function pruneRemovedFromSelection(removed: number[]): void {
  const next = removeIds(getState().selectedURLCardIDs, removed);
  log("prune removed from selection", { removed, next });
  commitSelection(next);
}

/**
 * Deck-diff survival primitive: re-mark a freshly built/re-added card from the
 * store so a live selection survives a rebuild. No-op if the card's id is not
 * currently selected.
 */
export function reapplyMultiSelectMark(urlCard: JQuery): void {
  const id = urlCardId(urlCard);
  if (getState().selectedURLCardIDs.includes(id)) {
    markCard({ urlCard, isSelected: true });
  }
}

/**
 * Re-derive the multi-select mark on every rendered row from the store's
 * current selection (marking selected rows, stripping the rest).
 */
export function reapplyAllMultiSelectMarks(): void {
  const selectedURLCardIDs = getState().selectedURLCardIDs;
  $(".urlRow").each((_index, element) => {
    const urlCard = $(element);
    markCard({
      urlCard,
      isSelected: selectedURLCardIDs.includes(urlCardId(urlCard)),
    });
  });
}
