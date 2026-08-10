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

// Whether the cross-UTub-search navbar trigger was visible before mode entry.
// Module-scoped because enter/exit are not guaranteed to be paired
// synchronously, so exit must remember the pre-entry visibility to restore it
// without clobbering a legitimately-hidden trigger (e.g. an empty utubs list).
let crossSearchWasVisible = false;

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

  setState({ multiSelectMode: true });
  $("#URLDeck").addClass(MULTI_SELECT_ACTIVE_CLASS);
  deselectAllURLs();
  emit(AppEvents.URL_MULTISELECT_MODE_CHANGED, { active: true });
}

/**
 * Exit multi-select mode: empty the selection (stripping marks), unmark the
 * deck, conditionally restore the cross-UTub-search trigger, and announce.
 */
export function exitMultiSelectMode(): void {
  // No-op when mode is not active. This keeps exit idempotent so an unpaired
  // exit (e.g. a UTub switch/delete while mode was already off) can never
  // restore #toCrossUtubSearch from a stale crossSearchWasVisible captured by
  // an earlier enter, nor emit a spurious mode-changed / clear the selection.
  if (!isMultiSelectActive()) return;
  log("exit multi-select mode");

  clearURLSelection();
  setState({ multiSelectMode: false });
  $("#URLDeck").removeClass(MULTI_SELECT_ACTIVE_CLASS);
  if (crossSearchWasVisible) {
    $(CROSS_SEARCH_TRIGGER_SELECTOR).removeClass(HIDDEN_CLASS);
  }
  emit(AppEvents.URL_MULTISELECT_MODE_CHANGED, { active: false });
}
