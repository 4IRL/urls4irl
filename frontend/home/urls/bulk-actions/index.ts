import { $ } from "../../../lib/globals.js";
import { KEYS } from "../../../lib/constants.js";
import { debug } from "../../../lib/debug.js";
import { AppEvents, on } from "../../../lib/event-bus.js";
import { isCrossUtubSearchActive } from "../../search/cross-utub-search.js";
import { isTagSheetOpen } from "../../tags/sheet.js";
import { initBulkBar } from "./bulk-bar.js";
import {
  enterMultiSelectMode,
  exitMultiSelectMode,
  isMultiSelectActive,
} from "./bulk-mode.js";

const log = debug("urls:cards");

const MULTI_SELECT_TOGGLE_SELECTOR = "#urlBtnMultiSelect";
const ESCAPE_KEYDOWN_NAMESPACE = "keydown.multiSelectEsc";
const TOGGLE_CLICK_NAMESPACE = "click.multiSelectToggle";

// Event-bus subscriptions are registered process-wide (the bus has no
// unbind-and-rebind), so guard them against a repeat initBulkActions() call
// accumulating duplicate handlers. The DOM bindings below stay outside this
// guard — offAndOnExact already makes them idempotent.
let _busSubscriptionsRegistered = false;

/**
 * Whether a text-entry element currently owns focus, so Escape typed into a
 * field never leaks out to exit multi-select mode (mirrors
 * cross-utub-search.ts's document-level target-type guard).
 */
function isTextInputFocused(): boolean {
  const active = document.activeElement;
  const activeTagName = active?.tagName;
  return (
    activeTagName === "INPUT" ||
    activeTagName === "TEXTAREA" ||
    (active as HTMLElement | null)?.isContentEditable === true
  );
}

/**
 * Wire up the multi-select mode: the header toggle button, the scoped
 * Escape-to-exit handler (deferring to any topmost overlay), and the UI-reset
 * event-bus subscriptions. Called once from main.ts's ready block.
 */
export function initBulkActions(): void {
  initBulkBar();

  $(MULTI_SELECT_TOGGLE_SELECTOR).offAndOnExact(TOGGLE_CLICK_NAMESPACE, () => {
    if (isMultiSelectActive()) {
      exitMultiSelectMode();
    } else {
      enterMultiSelectMode();
    }
  });

  $(document).offAndOnExact(
    ESCAPE_KEYDOWN_NAMESPACE,
    (event: JQuery.TriggeredEvent) => {
      if (event.key !== KEYS.ESCAPE) return;
      if (!isMultiSelectActive()) return;
      // Topmost-overlay-wins: an open Bootstrap modal (shared confirm/rename/
      // access modals), a text input, the tag sheet, or an active cross-UTub
      // search each own Escape before multi-select exit.
      if ($(".modal.show").length > 0) return;
      if (isTextInputFocused()) return;
      if (isTagSheetOpen()) return;
      if (isCrossUtubSearchActive()) return;
      log("escape exits multi-select mode");
      exitMultiSelectMode();
    },
  );

  if (_busSubscriptionsRegistered) return;
  _busSubscriptionsRegistered = true;

  // Single source of truth for the toggle's pressed state: every enter/exit
  // path (click, Escape, UTub switch/delete, mobile panel switch) routes
  // through URL_MULTISELECT_MODE_CHANGED, so aria-pressed can never go stale.
  on(AppEvents.URL_MULTISELECT_MODE_CHANGED, ({ active }) => {
    $(MULTI_SELECT_TOGGLE_SELECTOR).attr(
      "aria-pressed",
      active ? "true" : "false",
    );
  });

  // Authoritative UI reset: switching or deleting the active UTub exits mode
  // (clearing the store via exitMultiSelectMode()'s clearURLSelection()).
  on(AppEvents.UTUB_SELECTED, () => exitMultiSelectMode());
  on(AppEvents.UTUB_DELETED, () => exitMultiSelectMode());

  // Mobile: leaving the URL deck panel exits mode. Conditional on the target
  // (re-entering the url-deck panel must not itself exit mode).
  on(AppEvents.MOBILE_DECK_SWITCHED, ({ target }) => {
    if (target !== "url-deck") exitMultiSelectMode();
  });
}
