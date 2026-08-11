import { $ } from "../../../lib/globals.js";
import { debug } from "../../../lib/debug.js";
import { AppEvents, emit } from "../../../lib/event-bus.js";
import { getState, setState } from "../../../store/app-store.js";
import { deselectAllURLs } from "../cards/selection.js";
import { clearURLSelection } from "./bulk-selection.js";

const log = debug("urls:cards");

const MULTI_SELECT_ACTIVE_CLASS = "multiSelectActive";
const HIDDEN_CLASS = "hidden";
const CROSS_SEARCH_TRIGGER_SELECTOR = "#toCrossUtubSearch";
const EDIT_PANEL_TOGGLE_SELECTOR = "#utubEditPanelToggle";
const BULK_SELECT_CRUMB_SELECTOR = "#bulkSelectCrumb";
// The common ancestor of both #URLDeck and #tagDeckSheet (siblings under it).
// Marking it in-mode lets tag-sheet.css slide the collapsed tag-sheet peek fully
// off-screen while selecting (killing the DD-11 double drawer) WITHOUT hiding the
// sheet outright — so the header tag icon can still open it on demand.
const MAIN_PANEL_SELECTOR = "#mainPanel";

// Whether the cross-UTub-search navbar trigger was visible before mode entry.
// Module-scoped because enter/exit are not guaranteed to be paired
// synchronously, so exit must remember the pre-entry visibility to restore it
// without clobbering a legitimately-hidden trigger (e.g. an empty utubs list).
let crossSearchWasVisible = false;

// Whether the mobile consolidated-edit toggle (#utubEditPanelToggle) was visible
// before mode entry. Same capture-and-restore idiom as crossSearchWasVisible:
// exit restores it only if it was showing (owner + unlocked + coarse pointer),
// never clobbering a legitimately-hidden toggle. The name/description pencils
// need no such bookkeeping — they auto-restore when the .multiSelectActive CSS
// gate is removed on exit.
let editPanelToggleWasVisible = false;

/** Whether multi-select mode is currently active (store is the source of truth). */
export function isMultiSelectActive(): boolean {
  return getState().multiSelectMode;
}

/**
 * Enter multi-select mode: collapse any expanded card, mark the deck, disable
 * the cross-UTub-search entry point (an unbranched selectURLCard() call site),
 * and announce the change.
 */
export function enterMultiSelectMode(): void {
  log("enter multi-select mode");

  // Disable the cross-UTub-search navbar trigger (its navigateToHit() is an
  // unguarded selectURLCard() call site), remembering its prior visibility so
  // exit can restore it only if it was showing.
  crossSearchWasVisible = !$(CROSS_SEARCH_TRIGGER_SELECTOR).hasClass(
    HIDDEN_CLASS,
  );
  $(CROSS_SEARCH_TRIGGER_SELECTOR).addClass(HIDDEN_CLASS);

  // Hide the mobile consolidated-edit toggle (its open handler is also gated on
  // isMultiSelectActive()), remembering prior visibility so exit restores it
  // only if it was showing. The name/description pencils are CSS-gated on
  // .multiSelectActive (no JS bookkeeping) and auto-restore on exit.
  editPanelToggleWasVisible = !$(EDIT_PANEL_TOGGLE_SELECTOR).hasClass(
    HIDDEN_CLASS,
  );
  $(EDIT_PANEL_TOGGLE_SELECTOR).addClass(HIDDEN_CLASS);

  // Fill the selection-context breadcrumb with the active UTub name (same store
  // field setUTubNameAndDescription writes). The context region is revealed by
  // the .multiSelectActive CSS gate below.
  $(BULK_SELECT_CRUMB_SELECTOR).text(getState().activeUTubName ?? "");

  setState({ multiSelectMode: true });
  $("#URLDeck").addClass(MULTI_SELECT_ACTIVE_CLASS);
  // Also mark the shared ancestor so tag-sheet.css can suppress the collapsed
  // peek (transform, not `.hidden`) without blocking on-demand opens.
  $(MAIN_PANEL_SELECTOR).addClass(MULTI_SELECT_ACTIVE_CLASS);
  deselectAllURLs();
  emit(AppEvents.URL_MULTISELECT_MODE_CHANGED, { active: true });
}

/**
 * Exit multi-select mode: empty the selection (stripping marks), unmark the
 * deck, conditionally restore the cross-UTub-search trigger, and announce.
 */
export function exitMultiSelectMode(): void {
  // No-op only on a genuinely-inactive (unpaired) exit — keeping exit
  // idempotent so it can never restore #toCrossUtubSearch from a stale
  // crossSearchWasVisible captured by an earlier enter, nor emit a spurious
  // mode-changed / clear the selection. But the deck's multiSelectActive class
  // is the authoritative "visually in mode" signal: a caller (UTub
  // switch/delete via buildSelectedUTub / deleteUTubSuccess) may pre-clear the
  // store flag in its own setState BEFORE the UTUB_SELECTED/UTUB_DELETED emit
  // reaches this subscriber, and the DOM still needs teardown in that case, so
  // proceed whenever either signal says we are (or look) in mode.
  if (
    !isMultiSelectActive() &&
    !$("#URLDeck").hasClass(MULTI_SELECT_ACTIVE_CLASS)
  ) {
    return;
  }
  log("exit multi-select mode");

  clearURLSelection();
  setState({ multiSelectMode: false });
  $("#URLDeck").removeClass(MULTI_SELECT_ACTIVE_CLASS);
  // Dropping the mainPanel mode class lets the collapsed tag-sheet peek slide
  // back into view (tag-sheet.css) — no refreshTagSheetAvailability() needed
  // since mode never toggled the sheet's `.hidden` availability.
  $(MAIN_PANEL_SELECTOR).removeClass(MULTI_SELECT_ACTIVE_CLASS);
  if (crossSearchWasVisible) {
    $(CROSS_SEARCH_TRIGGER_SELECTOR).removeClass(HIDDEN_CLASS);
  }
  if (editPanelToggleWasVisible) {
    $(EDIT_PANEL_TOGGLE_SELECTOR).removeClass(HIDDEN_CLASS);
  }
  emit(AppEvents.URL_MULTISELECT_MODE_CHANGED, { active: false });
}
