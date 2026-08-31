import type { MemberItem } from "../../types/member.js";

import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { debug } from "../../lib/debug.js";
import { AppEvents, on } from "../../lib/event-bus.js";
import { clearOpenForm, setOpenForm } from "../../lib/modal-tracking.js";
import { HOME_FORM } from "../../types/metrics-dim-values.js";
import { getState } from "../../store/app-store.js";
import { makeUTubRoleIcon } from "../utubs/selectors.js";
import { roleLabelFor } from "./members.js";
import { closeAllMemberRowMenus } from "./row-menu.js";
import { beginTransferFlow, showTransferConfirmView } from "./transfer.js";

const log = debug("members");

// The transfer flow now lives in a DEDICATED Bootstrap modal (#transferOwnerModal)
// with an inline pick→confirm transition. This module owns the OPEN trigger, the
// PICK view rendering, and the single-select/roving/filter interaction; transfer.ts
// owns the modal lifecycle, the CONFIRM view, and the PATCH commit.
const MODAL_SELECTOR = "#transferOwnerModal";
const PICK_VIEW_SELECTOR = "#transferOwnerPickView";
const CONFIRM_VIEW_SELECTOR = "#transferOwnerConfirmView";
const TITLE_SELECTOR = "#transferOwnerModalTitle";
const FOOTER_MSG_SELECTOR = "#transferOwnerFooterMsg";
// The Cancel button is wired once in transfer.ts beginTransferFlow (shared modal),
// so this module no longer references CANCEL_BTN_SELECTOR.
const SUBMIT_BTN_SELECTOR = "#transferOwnerSubmit";
// The role="listbox" element is an INNER child of the pick view (not the view
// itself) so the filter input can live in the same view without being an invalid
// child of the listbox (mirrors bulk-copy.ts).
const LISTBOX_SELECTOR = ".transferPickerListbox";
const NO_MATCHES_SELECTOR = ".transferPickerNoMatches";
const OPTION_SELECTOR = '.transferPickerOption[role="option"]';
// "Enabled" for roving/focus = not filtered out (.hidden). Single-select has no
// per-row disabled state (every non-owner member is an eligible target), so only
// the filter's .hidden gate excludes a row.
const ENABLED_OPTION_SELECTOR =
  '.transferPickerOption[role="option"]:not(.hidden)';

// Funnel prefix icon for the filter — the SAME markup the app's deck search bars
// use (and the bulk-copy filter), so the box reads as the same control. Trusted
// static literal — never interpolate user content into it.
const FILTER_ICON_HTML =
  '<svg class="utub-search-prefix-icon" xmlns="http://www.w3.org/2000/svg" ' +
  'fill="currentColor" height="14" width="14" viewBox="0 0 16 16" aria-hidden="true">' +
  '<path d="M1.5 1.5A.5.5 0 0 1 2 1h12a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-.128.334L10 8.692V13.5a.5.5 0 0 1-.342.474l-3 1A.5.5 0 0 1 6 14.5V8.692L1.628 3.834A.5.5 0 0 1 1.5 3.5z"/>' +
  "</svg>";

// --- Module state -------------------------------------------------------------

// Single-select: the staged target member id (contrast bulk-copy's Set).
let selectedMemberId: number | null = null;
let transferPickerOpen = false;
let keydownListener: ((event: KeyboardEvent) => void) | null = null;
let keyupListener: ((event: KeyboardEvent) => void) | null = null;
// Bus subscriptions are process-wide (no rebind); guard against a repeat init.
let _transferPickerInitialized = false;

function setTransferPickerOpen(open: boolean): void {
  transferPickerOpen = open;
}

/** Whether the transfer picker is currently open. */
export function isTransferPickerOpen(): boolean {
  return transferPickerOpen;
}

// --- Init / bus subscriptions -------------------------------------------------

/**
 * Wire the picker's event-bus subscriptions at home bootstrap: teardown on UTub
 * switch/delete and the delete-flow open trigger (TRANSFER_PICKER_REQUESTED).
 * Idempotent — safe to call once from main.ts.
 */
export function initTransferPicker(): void {
  if (_transferPickerInitialized) return;
  _transferPickerInitialized = true;

  // UTub switch / delete tears the modal down even if the user never closed it.
  on(AppEvents.UTUB_SELECTED, () => closeTransferPicker());
  on(AppEvents.UTUB_DELETED, () => closeTransferPicker());

  // Delete-flow entry point: the "Transfer instead" button emits this with the
  // delete trigger as the opener, so a cancel returns focus there.
  on(AppEvents.TRANSFER_PICKER_REQUESTED, ({ opener }) =>
    openTransferPicker(opener),
  );
}

// --- Open / close lifecycle ---------------------------------------------------

/**
 * Open the transfer modal for the active UTub in its PICK state: render the
 * eligible-member listbox into #transferOwnerPickView, wire the footer Cancel /
 * Transfer buttons, arm a one-shot shown-focus handler, then hand off to
 * transfer.ts's beginTransferFlow (which resets the confirm/success flags, emits
 * the SHOWN metric, arms the hidden-close handler, and shows the modal). The
 * modal backdrop inherently suppresses the deck — no cross-surface CSS is needed.
 * Re-entrant open is a defined no-op.
 */
export function openTransferPicker(opener: HTMLElement | string): void {
  if (transferPickerOpen) return;

  log("open transfer picker", { opener });

  // A stray open kebab must not linger under the modal.
  closeAllMemberRowMenus();

  selectedMemberId = null;

  // Render the pick view; ensure the confirm view is hidden + empty and the pick
  // view is shown (a prior confirm-state leftover cannot survive a reopen).
  $(CONFIRM_VIEW_SELECTOR).addClass("hidden").empty();
  $(PICK_VIEW_SELECTOR).removeClass("hidden");
  renderPickView();

  $(TITLE_SELECTOR).text(APP_CONFIG.strings.TRANSFER_OWNER_PICKER_TITLE);
  // Footer starts empty — the modal title already says "Transfer ownership to…",
  // so a "select a member" hint here would be redundant. The footer only speaks
  // up once a member is staged ("{username} will become the owner.").
  $(FOOTER_MSG_SELECTOR).text("");

  // Footer Transfer button (the modal's own, not rendered per-view). Cancel is
  // bound once in beginTransferFlow (dismisses in both views). Transfer stays
  // disabled until a member is staged, then advances to confirm.
  $(SUBMIT_BTN_SELECTOR)
    .text(APP_CONFIG.strings.TRANSFER_OWNER_SUBMIT)
    .prop("disabled", true)
    .offAndOn("click", function () {
      onContinue();
    });

  setTransferPickerOpen(true);
  setOpenForm(HOME_FORM.TRANSFER_OWNER);

  // Reset module state + tear down listeners/views when the modal closes (any
  // path: Cancel, Escape, backdrop, or a successful transfer). Namespaced so it
  // removes exactly this handler and the shown-focus one-shot on teardown.
  $(MODAL_SELECTOR).on("hidden.bs.modal.transferPicker", function () {
    setTransferPickerOpen(false);
    selectedMemberId = null;
    clearOpenForm();
    detachKeyListeners();
    $(PICK_VIEW_SELECTOR).empty();
    $(CONFIRM_VIEW_SELECTOR).addClass("hidden").empty();
    $(MODAL_SELECTOR).off(
      "shown.bs.modal.transferOwnerFocus hidden.bs.modal.transferPicker",
    );
  });

  // Focus the first enabled row (or the empty-state message) once the modal has
  // finished its show transition — Bootstrap's own focus trap otherwise steals it.
  $(MODAL_SELECTOR).offAndOn("shown.bs.modal.transferOwnerFocus", function () {
    const firstRow = $(PICK_VIEW_SELECTOR).find(ENABLED_OPTION_SELECTOR)[0];
    if (firstRow) {
      setActiveRow(firstRow);
    } else {
      $(PICK_VIEW_SELECTOR).find(".transferPickerAllLocked")[0]?.focus();
    }
  });

  // transfer.ts owns showing the modal + the flags + the SHOWN metric + the
  // close (cancel-metric / focus-return) handler.
  beginTransferFlow(opener);
}

/**
 * Close the transfer modal. State reset happens in the hidden.bs.modal.transferPicker
 * handler armed in openTransferPicker. Safe no-op when already closed.
 */
export function closeTransferPicker(): void {
  if (!transferPickerOpen) return;
  $(MODAL_SELECTOR).modal("hide");
}

// --- Rendering ----------------------------------------------------------------

/** The active UTub's members minus the owner — every one an eligible target. */
function eligibleMembers(): MemberItem[] {
  const ownerID = getState().utubOwnerID;
  return getState().members.filter((member) => member.id !== ownerID);
}

/**
 * Build and mount the PICK view markup into #transferOwnerPickView: a filter
 * input and an inner role="listbox" of the eligible-member option rows (roving
 * tabindex) plus a no-matches message. When there are zero eligible members, an
 * accessible empty-state message replaces the rows (and the filter) and Transfer
 * stays disabled.
 */
function renderPickView(): void {
  const view = $(PICK_VIEW_SELECTOR);
  view.empty();

  const listbox = $(document.createElement("div")).addClass(
    "transferPickerListbox",
  );
  listbox.attr({
    role: "listbox",
    "aria-label": APP_CONFIG.strings.TRANSFER_OWNER_LISTBOX_ARIA,
  });

  const members = eligibleMembers();

  if (members.length === 0) {
    // No other members — nothing to transfer to. Announced message, no filter,
    // Transfer stays disabled (mirror bulk-copy's all-locked path).
    const empty = $(document.createElement("div"))
      .addClass("transferPickerAllLocked")
      .attr({ role: "status", "aria-live": "polite", tabindex: "-1" })
      .text(APP_CONFIG.strings.TRANSFER_OWNER_NO_ELIGIBLE);
    listbox.append(empty);
    view.append(listbox);
    attachKeyListeners();
    return;
  }

  members.forEach((member, index) => {
    // The first row is the initial roving-tabindex target (tabindex 0); every
    // other row starts at -1.
    const isInitialRow = index === 0;

    const row = $(document.createElement("div"))
      .addClass("transferPickerOption flex-row jc-sb align-center")
      .attr({
        role: "option",
        id: `transferPickerOption-${member.id}`,
        memberid: member.id,
        "aria-selected": "false",
        tabindex: isInitialRow ? "0" : "-1",
      });

    // Decorative single-select check ring (aria-hidden — the row's own
    // aria-selected carries the state). Prepended so it reads left-of-name.
    row.append(
      $(document.createElement("span"))
        .addClass("transferPickerCheck")
        .attr({ "aria-hidden": "true" }),
    );
    // Username via .text() — XSS-safe (never innerHTML).
    row.append(
      $(document.createElement("b"))
        .addClass("transferPickerName")
        .text(member.username),
    );
    // Role badge: decorative icon + a visually-hidden role label. The icon HTML
    // is a trusted static SVG from makeUTubRoleIcon (no user content).
    const badge = $(document.createElement("span")).addClass(
      "transferPickerRoleBadge",
    );
    badge.append(
      $(document.createElement("span"))
        .attr({ "aria-hidden": "true" })
        .html(
          makeUTubRoleIcon({ memberRole: member.memberRole, isLocked: false }),
        ),
    );
    badge.append(
      $(document.createElement("span"))
        .addClass("visually-hidden")
        .text(roleLabelFor(member.memberRole)),
    );
    row.append(badge);

    // Row click selects this member (single-select — clears any other row).
    row.on("click.transferPickerSelect", () => selectRow(row));
    listbox.append(row);
  });

  // No-results message shown inside the listbox when the filter matches nothing.
  const noMatches = $(document.createElement("div"))
    .addClass("transferPickerNoMatches hidden")
    .attr({ role: "status", "aria-live": "polite" })
    .text(APP_CONFIG.strings.TRANSFER_OWNER_NO_MATCHES);
  listbox.append(noMatches);

  view.append(buildFilterInput()).append(listbox);
  // Seed the footer hint + disabled Transfer button (nothing chosen yet).
  updateConfirmState();
  attachKeyListeners();
}

/**
 * Build the member-filter input (reuses the app's canonical deck-search pill
 * markup + funnel prefix icon). Typing filters the option rows by username
 * (case-insensitive substring). Not a listbox child, so it does not corrupt the
 * listbox's ARIA.
 */
function buildFilterInput(): JQuery {
  const wrap = $(document.createElement("div")).addClass(
    "transferPickerFilterWrap",
  );
  const inner = $(document.createElement("div")).addClass(
    "text-input-inner-container",
  );
  inner.append(FILTER_ICON_HTML);
  const input = $(document.createElement("input"))
    .addClass("text-input transferPickerFilterInput")
    .attr({
      type: "search",
      autocomplete: "off",
      autocorrect: "off",
      autocapitalize: "off",
      "aria-label": APP_CONFIG.strings.TRANSFER_OWNER_FILTER_PLACEHOLDER,
      placeholder: APP_CONFIG.strings.TRANSFER_OWNER_FILTER_PLACEHOLDER,
    });
  input.on("input.transferPickerFilter", () =>
    applyFilter(String(input.val() ?? "")),
  );
  inner.append(input);
  wrap.append(inner);
  return wrap;
}

/**
 * Filter the option rows by the typed query (case-insensitive substring on the
 * username). Non-matching rows get `.hidden` (excluded from roving via
 * ENABLED_OPTION_SELECTOR); the no-results message shows when nothing matches. A
 * currently-staged row stays staged even if filtered out — `selectedMemberId`,
 * not row visibility, is what Transfer commits.
 */
function applyFilter(rawQuery: string): void {
  const query = rawQuery.trim().toLowerCase();
  const listbox = $(PICK_VIEW_SELECTOR).find(LISTBOX_SELECTOR);

  let visibleCount = 0;
  listbox.find(OPTION_SELECTOR).each((_, element) => {
    const row = $(element);
    const name = row.find(".transferPickerName").text().toLowerCase();
    const matches = query === "" || name.includes(query);
    row.toggleClass("hidden", !matches);
    if (matches) visibleCount += 1;
  });

  listbox.find(NO_MATCHES_SELECTOR).toggleClass("hidden", visibleCount > 0);
  resetRovingEntry();
}

/**
 * Reset the roving tabindex entry point after a filter change: clear tabindex on
 * every option row, then set the FIRST still-visible row to tabindex 0. Focus is
 * not moved (it stays in the filter input while the user types).
 */
function resetRovingEntry(): void {
  const view = $(PICK_VIEW_SELECTOR);
  view.find(OPTION_SELECTOR).attr("tabindex", "-1");
  view.find(ENABLED_OPTION_SELECTOR).first().attr("tabindex", "0");
}

// --- Single-select + roving tabindex ------------------------------------------

/**
 * Single-select a row (contrast bulk-copy's Set toggle): move roving focus to it
 * first, clear every row's selected state, then mark the clicked row selected and
 * stage its member id. Updates the footer hint + enables Transfer.
 */
function selectRow(row: JQuery): void {
  const rowEl = row[0];
  if (!rowEl) return;
  setActiveRow(rowEl);

  const id = parseInt(row.attr("memberid") ?? "", 10);
  if (Number.isNaN(id)) return;

  // Clear every other row, then select this one (single-select).
  $(PICK_VIEW_SELECTOR)
    .find(OPTION_SELECTOR)
    .attr("aria-selected", "false")
    .removeClass("active");
  row.attr("aria-selected", "true").addClass("active");
  selectedMemberId = id;

  updateConfirmState();
  log("select transfer target", { id });
}

/**
 * Move the roving tabindex AND real DOM focus onto `rowEl` atomically: the
 * previously-active row's tabindex goes back to -1, `rowEl`'s becomes 0, then it
 * receives focus. Both arrow navigation and selection call this one helper.
 */
function setActiveRow(rowEl: HTMLElement): void {
  const view = $(PICK_VIEW_SELECTOR);
  view.find(OPTION_SELECTOR).attr("tabindex", "-1");
  $(rowEl).attr("tabindex", "0");
  rowEl.focus();
}

/** The visible (non-filtered) option rows, in DOM order, as elements. */
function enabledRowElements(): HTMLElement[] {
  return $(PICK_VIEW_SELECTOR).find(ENABLED_OPTION_SELECTOR).toArray();
}

/**
 * Move roving focus to the next/previous visible row (wrapping at the ends).
 * Pure navigation — it does NOT select a row. `direction` is +1 (ArrowDown) or
 * -1 (ArrowUp).
 */
function moveRoving({ direction }: { direction: 1 | -1 }): void {
  const rows = enabledRowElements();
  if (rows.length === 0) return;
  const active = document.activeElement as HTMLElement | null;
  const currentIndex = active ? rows.indexOf(active) : -1;
  const nextIndex =
    currentIndex === -1
      ? direction === 1
        ? 0
        : rows.length - 1
      : (currentIndex + direction + rows.length) % rows.length;
  setActiveRow(rows[nextIndex]);
}

/**
 * Sync the Transfer button's enabled state and the footer live-region hint to
 * the staged selection: disabled with the "select a member" hint at nothing
 * chosen; enabled with the "{username} will become the owner." message once a
 * member is staged. XSS-safe (`.text()`).
 */
function updateConfirmState(): void {
  const chosen =
    selectedMemberId === null
      ? undefined
      : getState().members.find((member) => member.id === selectedMemberId);

  $(SUBMIT_BTN_SELECTOR).prop("disabled", chosen === undefined);

  // No footer message: the modal title states the task and the highlighted row
  // (aria-selected) makes the choice obvious, so a "{username} will become the
  // owner." line is just noise. Footer stays empty in every pick state.
  $(FOOTER_MSG_SELECTOR).text("");
}

// --- Keyboard handling (capture-phase keydown + keyup on the pick view) --------

function attachKeyListeners(): void {
  const viewElement = $(PICK_VIEW_SELECTOR)[0];
  if (!viewElement) return;
  detachKeyListeners();
  keydownListener = handleViewKeydown;
  keyupListener = handleViewKeyup;
  // Capture phase for keydown so ArrowUp/Down are handled before any nested
  // handler (mirrors bulk-copy.ts). Escape is left to Bootstrap's data-bs-keyboard.
  viewElement.addEventListener("keydown", keydownListener, { capture: true });
  viewElement.addEventListener("keyup", keyupListener);
}

function detachKeyListeners(): void {
  const viewElement = $(PICK_VIEW_SELECTOR)[0];
  if (viewElement) {
    if (keydownListener) {
      viewElement.removeEventListener("keydown", keydownListener, {
        capture: true,
      });
    }
    if (keyupListener) {
      viewElement.removeEventListener("keyup", keyupListener);
    }
  }
  keydownListener = null;
  keyupListener = null;
}

/**
 * Keydown: ArrowUp/ArrowDown rove focus across visible rows; Space is
 * prevent-defaulted on a focused row (keydown is where the page-scroll-on-Space
 * happens — keyup alone cannot suppress it). Selection itself happens on keyup.
 * Escape is handled by Bootstrap's own data-bs-keyboard modal dismissal.
 */
function handleViewKeydown(event: KeyboardEvent): void {
  switch (event.key) {
    case KEYS.ARROW_DOWN: {
      event.preventDefault();
      moveRoving({ direction: 1 });
      return;
    }
    case KEYS.ARROW_UP: {
      event.preventDefault();
      moveRoving({ direction: -1 });
      return;
    }
    case KEYS.SPACE: {
      // Suppress page scroll-on-Space ONLY when an option row is focused (the
      // paired keyup selects it).
      const target = event.target as HTMLElement | null;
      if (target && $(target).closest(OPTION_SELECTOR).length > 0) {
        event.preventDefault();
      }
      return;
    }
    default:
      return;
  }
}

/**
 * Keyup: Enter or Space on the currently-focused row selects it (single-select).
 */
function handleViewKeyup(event: KeyboardEvent): void {
  if (event.key !== KEYS.ENTER && event.key !== KEYS.SPACE) return;
  const target = event.target as HTMLElement | null;
  if (target === null) return;
  const row = $(target).closest(OPTION_SELECTOR);
  if (row.length === 0) return;
  selectRow(row);
}

// --- Continue (advance the SAME modal to the confirm view) ---------------------

/**
 * Read the staged member live from the store and advance the modal to the
 * confirm view (transfer.ts owns that view + the commit). Defensive: if the
 * staged member has vanished (removed mid-pick), reset to the empty-selection
 * state instead of proceeding. The modal is NOT closed — it swaps in place.
 */
function onContinue(): void {
  if (selectedMemberId === null) return;

  const chosen = getState().members.find(
    (member) => member.id === selectedMemberId,
  );
  if (chosen === undefined) {
    // The staged member vanished — treat as nothing chosen; stay on the pick view.
    selectedMemberId = null;
    renderPickView();
    $(SUBMIT_BTN_SELECTOR).prop("disabled", true);
    $(FOOTER_MSG_SELECTOR).text("");
    return;
  }

  const utubID = getState().activeUTubID;
  if (utubID === null) return;

  showTransferConfirmView({
    newOwnerId: chosen.id,
    newOwnerUsername: chosen.username,
    utubID,
  });
}
