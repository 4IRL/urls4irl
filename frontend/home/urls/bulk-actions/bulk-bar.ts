import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { debug } from "../../../lib/debug.js";
import { AppEvents, on } from "../../../lib/event-bus.js";
import { getState } from "../../../store/app-store.js";
import { VISIBLE_URL_SELECTOR } from "../utils.js";
import {
  type BulkActionContext,
  getAvailableBulkActions,
} from "./bulk-action-registry.js";
import { exitMultiSelectMode } from "./bulk-mode.js";
import { isAnyBulkPickerOpen, onPickerOpenChange } from "./picker-guard.js";
import {
  clearURLSelection,
  invertVisibleSelection,
  selectAllVisibleURLCards,
} from "./bulk-selection.js";

const log = debug("urls:cards");

const BAR_SELECTOR = "#bulkActionBar";
const COUNT_SELECTOR = "#bulkSelectCount";
const HIDDEN_HINT_SELECTOR = "#bulkSelectHiddenHint";
const ANNOUNCEMENT_SELECTOR = "#URLBulkSelectionAnnouncement";
const ACTION_BUTTONS_SELECTOR = "#bulkActionButtons";
const SELECT_ALL_SELECTOR = "#bulkSelectAll";
const CLEAR_SELECTOR = "#bulkSelectClear";
const EXIT_SELECTOR = "#bulkSelectExit";
// Desktop selection-context range strip (subheader). Its Select all / Invert /
// Clear are a responsive DUPLICATE of the header/drawer #bulkSelectAll /
// #bulkSelectClear (shown only >=992px; the drawer copies show only < 992px),
// bound to the same handlers below.
const RANGE_SELECT_ALL_SELECTOR = "#bulkRangeSelectAll";
const RANGE_INVERT_SELECTOR = "#bulkRangeInvert";
const RANGE_CLEAR_SELECTOR = "#bulkRangeClear";
const RANGE_STRIP_SELECTOR = "#bulkSelectRangeStrip";
const MULTI_SELECT_TOGGLE_SELECTOR = "#urlBtnMultiSelect";
const DECK_SELECTOR = "#URLDeck";
const HIDDEN_CLASS = "hidden";

const SELECT_ALL_CLICK = "click.bulkSelectAll";
const CLEAR_CLICK = "click.bulkSelectClear";
const EXIT_CLICK = "click.bulkSelectExit";
const RANGE_SELECT_ALL_CLICK = "click.bulkRangeSelectAll";
const RANGE_INVERT_CLICK = "click.bulkRangeInvert";
const RANGE_CLEAR_CLICK = "click.bulkRangeClear";

// Bus subscriptions are process-wide (the bus has no rebind), so guard them
// against a repeat initBulkBar() accumulating duplicate handlers. The DOM
// button bindings stay outside this guard — offAndOnExact is idempotent.
let _barSubscriptionsRegistered = false;

/** Ids of currently visible (filterable + not search-hidden) URL rows. */
function visibleURLCardIDs(): Set<number> {
  const ids = new Set<number>();
  $(VISIBLE_URL_SELECTOR).each((_index, element) => {
    const id = parseInt($(element).attr("utuburlid") ?? "", 10);
    if (!Number.isNaN(id)) ids.add(id);
  });
  return ids;
}

/** How many selected ids are not in the visible set (hidden by search/filter). */
function hiddenSelectedCount(selectedURLCardIDs: number[]): number {
  const visible = visibleURLCardIDs();
  return selectedURLCardIDs.filter((id) => !visible.has(id)).length;
}

/**
 * Compose the single shared aria-live announcement: the selected-count line,
 * with the "N hidden by filter" clause appended when some selections are hidden
 * (one live region, never a second one).
 */
function composeAnnouncement({
  selectedCount,
  hiddenCount,
}: {
  selectedCount: number;
  hiddenCount: number;
}): string {
  if (selectedCount === 0) return APP_CONFIG.strings.URL_BULK_NONE_SELECTED;
  const countText =
    selectedCount === 1
      ? APP_CONFIG.strings.URL_BULK_SELECTED_COUNT_ONE
      : APP_CONFIG.strings.URL_BULK_SELECTED_COUNT.replace(
          "{n}",
          String(selectedCount),
        );
  if (hiddenCount === 0) return countText;
  const hiddenText = APP_CONFIG.strings.URL_BULK_N_HIDDEN.replace(
    "{n}",
    String(hiddenCount),
  );
  return `${countText}, ${hiddenText}`;
}

/** Snapshot of the current selection + URL list for action gating. */
function buildContext(): BulkActionContext {
  const state = getState();
  return {
    selectedURLCardIDs: state.selectedURLCardIDs,
    urls: state.urls,
  };
}

/**
 * Render every available registered action as a button in #bulkActionButtons.
 * Empty in Phase 1 (no actions registered); the seam is exercised by tests and
 * plugged by Phases 2/3.
 */
function renderBulkActionButtons(context: BulkActionContext): void {
  const container = $(ACTION_BUTTONS_SELECTOR);
  container.empty();
  for (const action of getAvailableBulkActions(context)) {
    const button = $("<button></button>")
      .attr("type", "button")
      .attr("data-bulk-action-id", action.id)
      .addClass("barBtn")
      .text(action.label);
    if (action.iconHtml) button.prepend(action.iconHtml);
    button.on("click", () => action.onActivate(buildContext()));
    container.append(button);
  }
}

/**
 * Re-derive the three desktop range-strip buttons' aria-disabled from the CURRENT
 * selection/visibility state and write them. The single place both updateBar()
 * and the picker-close path call, so the gating lives in one spot:
 *  - Clear      → disabled at 0 selected (same value as #bulkSelectClear).
 *  - Select all → disabled at 0 visible (can't act on the visible axis).
 *  - Invert     → disabled at 0 selected OR 0 visible (DD-6: at 0 selected,
 *                 inverting the visible set == Select All, so it's redundant).
 * visibleCount is derived the same way the "N hidden by filter" hint is —
 * $(VISIBLE_URL_SELECTOR).length.
 */
function syncRangeButtonStates(): void {
  const selectedCount = getState().selectedURLCardIDs.length;
  const visibleCount = $(VISIBLE_URL_SELECTOR).length;
  $(RANGE_SELECT_ALL_SELECTOR).attr(
    "aria-disabled",
    visibleCount === 0 ? "true" : "false",
  );
  $(RANGE_INVERT_SELECTOR).attr(
    "aria-disabled",
    selectedCount === 0 || visibleCount === 0 ? "true" : "false",
  );
  $(RANGE_CLEAR_SELECTOR).attr(
    "aria-disabled",
    selectedCount === 0 ? "true" : "false",
  );
}

/** Repaint the bar (count, hidden hint, SR announcement, Clear state, actions). */
function updateBar(selectedURLCardIDs: number[]): void {
  const selectedCount = selectedURLCardIDs.length;
  const hiddenCount = hiddenSelectedCount(selectedURLCardIDs);

  $(COUNT_SELECTOR).text(String(selectedCount));

  const hint = $(HIDDEN_HINT_SELECTOR);
  if (hiddenCount > 0) {
    hint
      .text(
        APP_CONFIG.strings.URL_BULK_N_HIDDEN.replace(
          "{n}",
          String(hiddenCount),
        ),
      )
      .removeClass(HIDDEN_CLASS);
  } else {
    hint.text("").addClass(HIDDEN_CLASS);
  }

  $(ANNOUNCEMENT_SELECTOR).text(
    composeAnnouncement({ selectedCount, hiddenCount }),
  );
  // aria-disabled (not the native `disabled` attribute) so Clear stays a valid
  // focus target: mode-enter focuses it while the selection is still empty, and
  // a natively-disabled button cannot receive focus. The click handler no-ops
  // when aria-disabled, so an empty-selection Clear is inert either way.
  $(CLEAR_SELECTOR).attr(
    "aria-disabled",
    selectedCount === 0 ? "true" : "false",
  );

  // The action-button region rebuilds on every selection/filter/search change.
  // While any bulk sub-picker (tag or copy) is open the selection is locked, so
  // skip the rebuild — it would otherwise destroy and recreate the ephemeral
  // action button out from under the open picker mounted in the stable container.
  if (!isAnyBulkPickerOpen()) {
    renderBulkActionButtons(buildContext());
  }

  // Same picker-open guard: while a picker is up the onPickerOpenChange OPEN
  // handler has force-disabled all three strip buttons, so updateBar() must NOT
  // re-enable them by re-deriving from selection/visibility. The picker-close
  // handler re-runs syncRangeButtonStates() itself once the picker closes.
  if (!isAnyBulkPickerOpen()) {
    syncRangeButtonStates();
  }
}

/** Show/hide the bar and manage focus on mode enter/exit. */
function toggleBar(active: boolean): void {
  const bar = $(BAR_SELECTOR);
  if (active) {
    bar.removeClass(HIDDEN_CLASS);
    updateBar(getState().selectedURLCardIDs);
    // Exit (the header's primary in-mode control) is the intentional initial
    // focus target now that the context/Exit live in the header; the bottom bar
    // hosts only the (empty in Phase 1) action registry + Select All / Clear.
    $(EXIT_SELECTOR)[0]?.focus();
    return;
  }
  bar.addClass(HIDDEN_CLASS);
  // Restore focus to the toggle, unless the empty-state path hid it while mode
  // was still active (a remote diff removing the last URL, per Step 7's
  // removeElement empty-state bullet) — then fall back to the always-rendered
  // deck container (DD-23) so focus/SR never lands on a hidden button.
  const toggle = $(MULTI_SELECT_TOGGLE_SELECTOR);
  if (toggle.length > 0 && !toggle.hasClass(HIDDEN_CLASS)) {
    toggle[0]?.focus();
  } else {
    $(DECK_SELECTOR)[0]?.focus();
  }
}

/**
 * Wire the bulk-action bar: its Select All / Clear / Exit buttons and the two
 * multi-select event-bus subscriptions (count/hint/announcement on selection
 * change; show-hide + focus on mode change). Called from initBulkActions().
 */
export function initBulkBar(): void {
  $(SELECT_ALL_SELECTOR).offAndOnExact(SELECT_ALL_CLICK, () => {
    // Selection is locked while any bulk sub-picker (tag or copy) is open.
    if (isAnyBulkPickerOpen()) return;
    selectAllVisibleURLCards();
  });
  $(CLEAR_SELECTOR).offAndOnExact(CLEAR_CLICK, () => {
    if (isAnyBulkPickerOpen()) return;
    if ($(CLEAR_SELECTOR).attr("aria-disabled") === "true") return;
    clearURLSelection();
  });
  // Desktop range-strip controls. Each guards on BOTH the picker-open state and
  // its own aria-disabled — the DD-6 gating must be enforced, not just painted —
  // mirroring the #bulkSelectClear guard shape above.
  $(RANGE_SELECT_ALL_SELECTOR).offAndOnExact(RANGE_SELECT_ALL_CLICK, () => {
    if (isAnyBulkPickerOpen()) return;
    if ($(RANGE_SELECT_ALL_SELECTOR).attr("aria-disabled") === "true") return;
    selectAllVisibleURLCards();
  });
  $(RANGE_INVERT_SELECTOR).offAndOnExact(RANGE_INVERT_CLICK, () => {
    if (isAnyBulkPickerOpen()) return;
    if ($(RANGE_INVERT_SELECTOR).attr("aria-disabled") === "true") return;
    invertVisibleSelection();
  });
  $(RANGE_CLEAR_SELECTOR).offAndOnExact(RANGE_CLEAR_CLICK, () => {
    if (isAnyBulkPickerOpen()) return;
    if ($(RANGE_CLEAR_SELECTOR).attr("aria-disabled") === "true") return;
    clearURLSelection();
  });
  $(EXIT_SELECTOR).offAndOnExact(EXIT_CLICK, () => exitMultiSelectMode());

  if (_barSubscriptionsRegistered) return;
  _barSubscriptionsRegistered = true;

  on(AppEvents.URL_MULTISELECT_CHANGED, ({ selectedURLCardIDs }) => {
    log("bulk-bar selection changed", { selectedURLCardIDs });
    updateBar(selectedURLCardIDs);
  });
  on(AppEvents.URL_MULTISELECT_MODE_CHANGED, ({ active }) => {
    log("bulk-bar mode changed", { active });
    toggleBar(active);
  });
  // The visible URL set — not the selection — changes when a tag filter or the
  // in-UTub search is applied/cleared. Selections deliberately survive that
  // (hidden rows stay selected), so no URL_MULTISELECT_CHANGED fires; repaint
  // the bar directly so the "N hidden by filter" hint + announcement stay
  // accurate against the new visible set.
  on(AppEvents.URL_TAG_FILTER_APPLIED, () => {
    log("bulk-bar tag filter applied");
    updateBar(getState().selectedURLCardIDs);
  });
  on(AppEvents.URL_SEARCH_VISIBILITY_CHANGED, () => {
    log("bulk-bar url search visibility changed");
    updateBar(getState().selectedURLCardIDs);
  });

  // Picker-inert wiring (DD-5 + Pass2-DD-3): the single place that syncs the
  // range strip's inert state for BOTH pickers. The container carries its own
  // aria-disabled for the CSS pointer-events:none rule; the three buttons carry
  // their own aria-disabled too, for per-control SR disclosure.
  onPickerOpenChange((open) => {
    $(RANGE_STRIP_SELECTOR).attr("aria-disabled", open ? "true" : "false");
    if (open) {
      // Picker open: force all three buttons inert regardless of current
      // selection/visibility — the strip is locked while a picker is up.
      $(RANGE_SELECT_ALL_SELECTOR).attr("aria-disabled", "true");
      $(RANGE_INVERT_SELECTOR).attr("aria-disabled", "true");
      $(RANGE_CLEAR_SELECTOR).attr("aria-disabled", "true");
    } else {
      // Picker closed: do NOT blindly clear each button's aria-disabled —
      // re-derive from current selection/visibility so a button that should
      // stay disabled (e.g. Clear at 0 selected) does.
      syncRangeButtonStates();
    }
  });
}
