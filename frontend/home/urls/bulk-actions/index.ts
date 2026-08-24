import { $ } from "../../../lib/globals.js";
import { KEYS } from "../../../lib/constants.js";
import { debug } from "../../../lib/debug.js";
import { AppEvents, on } from "../../../lib/event-bus.js";
import { isMobile } from "../../mobile.js";
import { isCrossUtubSearchActive } from "../../search/cross-utub-search.js";
import {
  isTagSheetOpen,
  openTagSheetFromUserAction,
} from "../../tags/sheet.js";
import { initBulkBar } from "./bulk-bar.js";
import { initBulkCopy } from "./bulk-copy.js";
import { initBulkDelete } from "./bulk-delete.js";
import { initBulkTag } from "./bulk-tag.js";
import { isAnyBulkPickerOpen } from "./picker-guard.js";
import {
  enterMultiSelectMode,
  exitMultiSelectMode,
  isMultiSelectActive,
} from "./bulk-mode.js";

const log = debug("urls:cards");

const MULTI_SELECT_TOGGLE_SELECTOR = "#urlBtnMultiSelect";
const TAG_FILTER_ICON_SELECTOR = "#bulkTagFilterIcon";
const ESCAPE_KEYDOWN_NAMESPACE = "keydown.multiSelectEsc";
const TOGGLE_CLICK_NAMESPACE = "click.multiSelectToggle";
const TAG_FILTER_CLICK_NAMESPACE = "click.bulkTagFilter";
const TAG_FILTER_FOCUS_NAMESPACE = "focus.bulkTagFilter";

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
 * Sync the tag-filter icon's aria-expanded to the live tag-sheet open state.
 * The sheet exposes no open/close AppEvent, so this is driven off the icon's own
 * click (open) and its focus (the sheet returns focus here on close).
 */
function syncTagFilterExpanded(): void {
  $(TAG_FILTER_ICON_SELECTOR).attr(
    "aria-expanded",
    isTagSheetOpen() ? "true" : "false",
  );
}

/**
 * Wire up the multi-select mode: the header toggle button, the mobile tag-filter
 * icon, the scoped Escape-to-exit handler (deferring to any topmost overlay),
 * and the UI-reset event-bus subscriptions. Called once from main.ts's ready
 * block.
 */
export function initBulkActions(): void {
  initBulkBar();
  // Registers the "Add tags" bulk action + its mode-exit teardown. The import
  // above is what makes the registration run.
  initBulkTag();
  // Registers the "Copy to UTub" bulk action + its picker-close callback. The
  // import above is what makes the registration run.
  initBulkCopy();
  // Registers the destructive "Delete" bulk action + its confirm-modal
  // picker-close callback. The import above is what makes the registration run.
  initBulkDelete();

  $(MULTI_SELECT_TOGGLE_SELECTOR).offAndOnExact(TOGGLE_CLICK_NAMESPACE, () => {
    if (isMultiSelectActive()) {
      exitMultiSelectMode();
    } else {
      enterMultiSelectMode();
    }
  });

  // Header tag-filter icon: mobile-only on-demand tag filtering. Opens the
  // existing tag-sheet (a no-op on desktop, where tag filtering is the LHS
  // #TagDeck). The icon is document.activeElement at call time, so openTagSheet
  // captures it as _opener for WCAG focus-return.
  $(TAG_FILTER_ICON_SELECTOR).offAndOnExact(TAG_FILTER_CLICK_NAMESPACE, () => {
    if (!isMobile()) return;
    // A bulk sub-picker (tag or copy) owns the deck while open — tapping the
    // tag-filter icon must not open the tag sheet over/under it.
    if (isAnyBulkPickerOpen()) return;
    openTagSheetFromUserAction();
    syncTagFilterExpanded();
  });
  // On sheet close, focus returns to the icon (its _opener) — re-read the open
  // state so aria-expanded falls back to "false".
  $(TAG_FILTER_ICON_SELECTOR).offAndOnExact(
    TAG_FILTER_FOCUS_NAMESPACE,
    syncTagFilterExpanded,
  );

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
      // Redundant second exit path: an open picker's own container capture-phase
      // listener already stops Escape from reaching here while it is open, but
      // guard defensively (either picker) in case focus ever escapes it.
      if (isAnyBulkPickerOpen()) return;
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
    // The sheet is never open across a mode enter/exit, so keep the tag-filter
    // icon's aria-expanded in sync (defensively resets it to the sheet state).
    syncTagFilterExpanded();
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
