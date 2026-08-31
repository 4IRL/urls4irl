import type { MemberItem } from "../../types/member.js";

import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { debug } from "../../lib/debug.js";
import { AppEvents, on } from "../../lib/event-bus.js";
import { clearOpenForm, setOpenForm } from "../../lib/modal-tracking.js";
import { createRovingListbox } from "../../lib/roving-listbox.js";
import { HOME_FORM } from "../../types/metrics-dim-values.js";
import { getState } from "../../store/app-store.js";
import { makeUTubRoleIcon } from "../utubs/selectors.js";
import { roleLabelFor } from "./members.js";
import { closeAllMemberRowMenus } from "./row-menu.js";
import { beginTransferFlow, showTransferConfirmView } from "./transfer.js";
import {
  CONFIRM_VIEW_SELECTOR,
  FOOTER_MSG_SELECTOR,
  MODAL_SELECTOR,
  PICK_VIEW_SELECTOR,
  SUBMIT_BTN_SELECTOR,
  TITLE_SELECTOR,
} from "./transfer-selectors.js";

const log = debug("members");

// The transfer flow now lives in a DEDICATED Bootstrap modal (#transferOwnerModal)
// with an inline pick→confirm transition. This module owns the OPEN trigger, the
// PICK view rendering, and the single-select/roving/filter interaction; transfer.ts
// owns the modal lifecycle, the CONFIRM view, and the PATCH commit. The shared
// modal selectors are imported from ./transfer-selectors.js; the Cancel button is
// wired once in transfer.ts beginTransferFlow, so this module never imports
// CANCEL_BTN_SELECTOR.
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
// Bus subscriptions are process-wide (no rebind); guard against a repeat init.
let _transferPickerInitialized = false;

// Shared roving-tabindex + keyboard + substring-filter listbox behaviour. This
// picker is SINGLE-select with no per-row disabled state and leaves Escape to
// Bootstrap's data-bs-keyboard (so no onEscape hook). Enter/Space keyup activates
// via selectRow (single-select clears others + stages one id).
const roving = createRovingListbox({
  container: () => $(PICK_VIEW_SELECTOR),
  optionSelector: OPTION_SELECTOR,
  enabledOptionSelector: ENABLED_OPTION_SELECTOR,
  listboxSelector: LISTBOX_SELECTOR,
  noMatchesSelector: NO_MATCHES_SELECTOR,
  filterText: (row) => row.find(".transferPickerName").text(),
  onActivateRow: (row) => selectRow(row),
});

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
    roving.detachKeyListeners();
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
      roving.setActiveRow(firstRow);
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
    roving.attachKeyListeners();
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
  roving.attachKeyListeners();
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
    roving.applyFilter(String(input.val() ?? "")),
  );
  inner.append(input);
  wrap.append(inner);
  return wrap;
}

// --- Single-select (roving/keyboard/filter live in the shared roving-listbox) --

/**
 * Single-select a row (contrast bulk-copy's Set toggle): move roving focus to it
 * first, clear every row's selected state, then mark the clicked row selected and
 * stage its member id. Updates the footer hint + enables Transfer.
 */
function selectRow(row: JQuery): void {
  const rowEl = row[0];
  if (!rowEl) return;
  roving.setActiveRow(rowEl);

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
