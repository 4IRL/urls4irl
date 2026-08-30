import type { MemberItem } from "../../types/member.js";

import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { debug } from "../../lib/debug.js";
import { AppEvents, on } from "../../lib/event-bus.js";
import { clearOpenForm, setOpenForm } from "../../lib/modal-tracking.js";
import { HOME_FORM } from "../../types/metrics-dim-values.js";
import { getState } from "../../store/app-store.js";
import { isMobile } from "../mobile.js";
import { makeUTubRoleIcon } from "../utubs/selectors.js";
import { hideAndResetMemberCombobox } from "./member-combobox.js";
import { roleLabelFor } from "./members.js";
import { closeAllMemberRowMenus } from "./row-menu.js";
import { closeMemberNameFilter } from "./search.js";
import { transferOwnershipShowModal } from "./transfer.js";

const log = debug("members");

const PICKER_MOUNT_SELECTOR = "#transferOwnerPickerMount";
const DECK_SELECTOR = "#MemberDeck";
const PICKER_OPEN_CLASS = "transfer-picker-open";
// The role="listbox" element is an INNER child of the mount (not the mount
// itself) so the title, filter input, and footer can live inside the picker
// without being invalid children of a listbox (mirrors bulk-copy.ts).
const LISTBOX_SELECTOR = ".transferPickerListbox";
const NO_MATCHES_SELECTOR = ".transferPickerNoMatches";
const OPTION_SELECTOR = '.transferPickerOption[role="option"]';
// "Enabled" for roving/focus = not filtered out (.hidden). Single-select has no
// per-row disabled state (every non-owner member is an eligible target), so only
// the filter's .hidden gate excludes a row.
const ENABLED_OPTION_SELECTOR =
  '.transferPickerOption[role="option"]:not(.hidden)';
const CONFIRM_BTN_SELECTOR = ".transferPickerConfirmBtn";
const MESSAGE_SELECTOR = ".transferPickerMsg";
// Namespaced document-level tap-outside listener (MOBILE ONLY). On mobile the
// picker is a bottom-docked drawer, so a tap anywhere outside its mount closes
// it. Namespaced so teardown removes exactly this listener.
const OUTSIDE_TAP_NAMESPACE = "click.transferPickerOutside";

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
// The element/selector focus returns to when the picker closes (the trigger that
// opened it — #memberBtnTransferOwner or, from the delete flow, #utubBtnDelete).
let _openerRef: HTMLElement | string | null = null;
let keydownListener: ((event: KeyboardEvent) => void) | null = null;
let keyupListener: ((event: KeyboardEvent) => void) | null = null;
// Pending deferred bind of the mobile tap-outside listener (see openTransferPicker).
let outsideTapBindTimeoutID: ReturnType<typeof setTimeout> | null = null;
// Bus subscriptions are process-wide (no rebind); guard against a repeat init.
let _transferPickerInitialized = false;

function setTransferPickerOpen(open: boolean): void {
  transferPickerOpen = open;
}

/** Whether the transfer picker is currently mounted/open. */
export function isTransferPickerOpen(): boolean {
  return transferPickerOpen;
}

// --- Init / bus subscriptions -------------------------------------------------

/**
 * Wire the picker's event-bus subscriptions at home bootstrap: teardown on UTub
 * switch/delete, the delete-flow open trigger (TRANSFER_PICKER_REQUESTED), and
 * the reverse mutual-exclusion (DD-6) close when the add-member combobox or the
 * member-name filter opens. Idempotent — safe to call once from main.ts.
 */
export function initTransferPicker(): void {
  if (_transferPickerInitialized) return;
  _transferPickerInitialized = true;

  // UTub switch / delete tears the picker down even if the user never closed it.
  on(AppEvents.UTUB_SELECTED, () => closeTransferPicker());
  on(AppEvents.UTUB_DELETED, () => closeTransferPicker());

  // Delete-flow entry point (Step 5): the "Transfer instead" button emits this
  // with the delete trigger as the opener, so a cancel returns focus there.
  on(AppEvents.TRANSFER_PICKER_REQUESTED, ({ opener }) =>
    openTransferPicker(opener),
  );

  // Mutual exclusion (DD-6), reverse direction: opening the add-member combobox
  // or the member-name filter tears down an open picker (safe no-op if closed).
  on(AppEvents.MEMBER_ADD_OPENED, () => closeTransferPicker());
  on(AppEvents.MEMBER_FILTER_OPENED, () => closeTransferPicker());
}

// --- Open / close lifecycle ---------------------------------------------------

/**
 * Open the single-select transfer picker for the active UTub: tear down any
 * conflicting deck surface (row menus, add-member combobox, member-name filter),
 * mark the deck open (suppresses the other member controls via CSS), render the
 * eligible-member listbox into the stable mount, and focus the first row. Stores
 * the opener so close/Escape/cancel returns focus to it. Re-entrant open is a
 * defined no-op.
 */
export function openTransferPicker(opener: HTMLElement | string): void {
  if (transferPickerOpen) return;

  log("open transfer picker", { opener });

  _openerRef = opener;
  // A stray open kebab must not float over the picker.
  closeAllMemberRowMenus();
  // Mutual exclusion (DD-6): tear down an open add-member combobox / member-name
  // filter before the picker renders (mirrors showMemberCombobox's own forward
  // closeMemberNameFilter() call).
  hideAndResetMemberCombobox();
  closeMemberNameFilter();

  $(DECK_SELECTOR).addClass(PICKER_OPEN_CLASS);

  selectedMemberId = null;
  setTransferPickerOpen(true);
  setOpenForm(HOME_FORM.TRANSFER_OWNER);

  $(PICKER_MOUNT_SELECTOR).removeClass("hidden");
  renderPicker();

  // MOBILE ONLY: bottom-drawer, so a tap OUTSIDE the mount dismisses it. The bind
  // is DEFERRED one tick so the click that opened the picker finishes bubbling to
  // `document` BEFORE the listener attaches (otherwise it closes on open).
  if (isMobile()) {
    outsideTapBindTimeoutID = setTimeout(() => {
      outsideTapBindTimeoutID = null;
      $(document).on(OUTSIDE_TAP_NAMESPACE, handleOutsideTap);
    }, 0);
  }
}

/**
 * Tear down the picker: detach listeners, empty + hide the mount, drop the
 * deck-open class + open-form token + open flag, reset module state, and return
 * focus to the tracked opener (a selector string is resolved via jQuery, an
 * element is focused directly). Safe no-op when already closed.
 */
export function closeTransferPicker(): void {
  if (!transferPickerOpen) return;

  detachKeyListeners();
  // Tear down the mobile tap-outside listener: cancel a still-pending deferred
  // bind AND remove any already-bound listener (idempotent on desktop).
  if (outsideTapBindTimeoutID !== null) {
    clearTimeout(outsideTapBindTimeoutID);
    outsideTapBindTimeoutID = null;
  }
  $(document).off(OUTSIDE_TAP_NAMESPACE);

  $(PICKER_MOUNT_SELECTOR)
    .empty()
    .addClass("hidden")
    .removeAttr("role")
    .removeAttr("aria-label");
  $(DECK_SELECTOR).removeClass(PICKER_OPEN_CLASS);

  clearOpenForm();
  setTransferPickerOpen(false);
  selectedMemberId = null;

  const opener = _openerRef;
  _openerRef = null;
  if (typeof opener === "string") {
    $(opener).trigger("focus");
  } else if (opener) {
    $(opener).trigger("focus");
  }
}

/**
 * Document-level tap handler (MOBILE): a tap whose target is OUTSIDE the picker
 * mount closes the picker. A tap INSIDE the mount is ignored.
 */
function handleOutsideTap(event: JQuery.TriggeredEvent): void {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  if ($(target).closest(PICKER_MOUNT_SELECTOR).length === 0) {
    closeTransferPicker();
  }
}

// --- Rendering ----------------------------------------------------------------

/** The active UTub's members minus the owner — every one an eligible target. */
function eligibleMembers(): MemberItem[] {
  const ownerID = getState().utubOwnerID;
  return getState().members.filter((member) => member.id !== ownerID);
}

/**
 * Build and mount the picker markup: a title, a filter input, an inner
 * role="listbox" of the eligible-member option rows (roving tabindex), a
 * no-matches message, and a footer (live-region hint, Cancel, Transfer). When
 * there are zero eligible members, an accessible empty-state message replaces the
 * rows (and the filter) and Transfer stays disabled.
 */
function renderPicker(): void {
  const mount = $(PICKER_MOUNT_SELECTOR);
  mount.empty().removeAttr("role").removeAttr("aria-label");

  const title = $(document.createElement("div"))
    .addClass("transferPickerTitle")
    .text(APP_CONFIG.strings.TRANSFER_OWNER_PICKER_TITLE);

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
    mount.append(title);
    const empty = $(document.createElement("div"))
      .addClass("transferPickerAllLocked")
      .attr({ role: "status", "aria-live": "polite", tabindex: "-1" })
      .text(APP_CONFIG.strings.TRANSFER_OWNER_NO_ELIGIBLE);
    listbox.append(empty);
    mount.append(listbox).append(buildFooter());
    attachKeyListeners();
    empty[0]?.focus();
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

  mount
    .append(title)
    .append(buildFilterInput())
    .append(listbox)
    .append(buildFooter());
  // Seed the footer hint + disabled Transfer button (nothing chosen yet).
  updateConfirmState();
  attachKeyListeners();

  // Focus the FIRST row on open (never the filter input — avoids a mobile
  // soft-keyboard popup). setActiveRow moves the roving tabindex AND real focus
  // atomically so they never drift.
  const firstRow = mount.find(ENABLED_OPTION_SELECTOR)[0];
  if (firstRow) setActiveRow(firstRow);
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
    .addClass("text-input search-input transferPickerFilterInput")
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
  const listbox = $(PICKER_MOUNT_SELECTOR).find(LISTBOX_SELECTOR);

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
  const mount = $(PICKER_MOUNT_SELECTOR);
  mount.find(OPTION_SELECTOR).attr("tabindex", "-1");
  mount.find(ENABLED_OPTION_SELECTOR).first().attr("tabindex", "0");
}

/** Build the picker footer: a live-region message + Cancel + Transfer buttons. */
function buildFooter(): JQuery {
  const footer = $(document.createElement("div")).addClass(
    "transferPickerFooter flex-row align-center",
  );

  const message = $(document.createElement("div"))
    .addClass("transferPickerMsg")
    .attr({ role: "status", "aria-live": "polite" });

  const cancelBtn = $(document.createElement("button"))
    .addClass("transferPickerCancelBtn tabbable")
    .attr({ type: "button" })
    .text("Cancel");
  cancelBtn.on("click.transferPickerCancel", () => closeTransferPicker());

  const confirmBtn = $(document.createElement("button"))
    .addClass("transferPickerConfirmBtn tabbable")
    .attr({ type: "button" })
    .prop("disabled", true)
    .text(APP_CONFIG.strings.TRANSFER_OWNER_SUBMIT);
  confirmBtn.on("click.transferPickerConfirm", () => handleConfirm());

  footer.append(message).append(cancelBtn).append(confirmBtn);
  return footer;
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
  $(PICKER_MOUNT_SELECTOR)
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
  const mount = $(PICKER_MOUNT_SELECTOR);
  mount.find(OPTION_SELECTOR).attr("tabindex", "-1");
  $(rowEl).attr("tabindex", "0");
  rowEl.focus();
}

/** The visible (non-filtered) option rows, in DOM order, as elements. */
function enabledRowElements(): HTMLElement[] {
  return $(PICKER_MOUNT_SELECTOR).find(ENABLED_OPTION_SELECTOR).toArray();
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
  const mount = $(PICKER_MOUNT_SELECTOR);
  const chosen =
    selectedMemberId === null
      ? undefined
      : getState().members.find((member) => member.id === selectedMemberId);

  mount.find(CONFIRM_BTN_SELECTOR).prop("disabled", chosen === undefined);

  const message =
    chosen === undefined
      ? APP_CONFIG.strings.TRANSFER_OWNER_PICK_HINT
      : APP_CONFIG.strings.TRANSFER_OWNER_PICK_CHOSEN.replace(
          "{{ username }}",
          chosen.username,
        );
  mount.find(MESSAGE_SELECTOR).text(message);
}

// --- Keyboard handling (capture-phase keydown + keyup on the mount) -----------

function attachKeyListeners(): void {
  const mountElement = $(PICKER_MOUNT_SELECTOR)[0];
  if (!mountElement) return;
  keydownListener = handleMountKeydown;
  keyupListener = handleMountKeyup;
  // Capture phase for keydown so Escape is swallowed before it reaches any
  // document-level handler (mirrors bulk-copy.ts).
  mountElement.addEventListener("keydown", keydownListener, { capture: true });
  mountElement.addEventListener("keyup", keyupListener);
}

function detachKeyListeners(): void {
  const mountElement = $(PICKER_MOUNT_SELECTOR)[0];
  if (mountElement) {
    if (keydownListener) {
      mountElement.removeEventListener("keydown", keydownListener, {
        capture: true,
      });
    }
    if (keyupListener) {
      mountElement.removeEventListener("keyup", keyupListener);
    }
  }
  keydownListener = null;
  keyupListener = null;
}

/**
 * Keydown: Escape closes the picker; ArrowUp/ArrowDown rove focus across visible
 * rows; Space is prevent-defaulted on a focused row (keydown is where the
 * page-scroll-on-Space happens — keyup alone cannot suppress it). Selection
 * itself happens on keyup.
 */
function handleMountKeydown(event: KeyboardEvent): void {
  switch (event.key) {
    case KEYS.ESCAPE: {
      event.stopPropagation();
      event.preventDefault();
      closeTransferPicker();
      return;
    }
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
      // paired keyup selects it). Space on the footer buttons keeps its native
      // button-activation behaviour.
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
function handleMountKeyup(event: KeyboardEvent): void {
  if (event.key !== KEYS.ENTER && event.key !== KEYS.SPACE) return;
  const target = event.target as HTMLElement | null;
  if (target === null) return;
  const row = $(target).closest(OPTION_SELECTOR);
  if (row.length === 0) return;
  selectRow(row);
}

// --- Confirm (hand off to the confirm modal, Step 2) --------------------------

/**
 * Read the staged member live from the store, close the picker, and hand the
 * target to transferOwnershipShowModal. Defensive: if the staged member has
 * vanished (removed mid-pick), reset to the empty-selection state instead of
 * proceeding. The opener is captured BEFORE closeTransferPicker() (which clears
 * `_openerRef`) so it can be threaded through to the confirm modal (DD-15).
 */
function handleConfirm(): void {
  if (selectedMemberId === null) return;

  const chosen = getState().members.find(
    (member) => member.id === selectedMemberId,
  );
  if (chosen === undefined) {
    // The staged member vanished — treat as nothing chosen.
    selectedMemberId = null;
    renderPicker();
    return;
  }

  const utubID = getState().activeUTubID;
  if (utubID === null) return;

  // Capture the opener BEFORE closeTransferPicker() clears _openerRef so the
  // confirm modal can return focus to the original trigger on cancel (DD-15).
  const opener = _openerRef;
  const newOwnerId = chosen.id;
  const newOwnerUsername = chosen.username;

  closeTransferPicker();

  transferOwnershipShowModal({
    newOwnerId,
    newOwnerUsername,
    utubID,
    // closeTransferPicker() nulled _openerRef; fall back to the standalone
    // trigger if the picker was somehow opened without one.
    opener: opener ?? "#memberBtnTransferOwner",
  });
}
