/**
 * Destination picker for a trashed URL whose origin UTub is trashed too.
 *
 * An inline listbox of live UTubs rendered inside the row, below its actions.
 * Option rows deliberately use `.trashDestinationOption` and none of
 * `.UTubSelector` / a bare `utubid` attribute / `.UTubName`: the left-panel UTub
 * name search stays live while Trash is open and queries those unscoped.
 */

import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { debug } from "../../lib/debug.js";
import { createRovingListbox } from "../../lib/roving-listbox.js";
import { getState } from "../../store/app-store.js";
import { restoreTrashedURL } from "./actions.js";
import { onTrashTabChanged } from "./tabs.js";
import type { TrashedUrlItem } from "../../types/trash.js";

const log = debug("trash:destination-picker");

const PICKER_SELECTOR = ".trashDestinationPicker";
const OPTION_SELECTOR = ".trashDestinationOption";
const ENABLED_OPTION_SELECTOR = ".trashDestinationOption:not(.disabled)";
const NO_MATCHES_SELECTOR = ".trashDestinationNoMatches";
const RESTORE_BUTTON_SELECTOR = ".trashBtnRestore";

let openRow: JQuery | null = null;
let openItem: TrashedUrlItem | null = null;
let homeEndListener: ((event: KeyboardEvent) => void) | null = null;
let keyupResetListener: (() => void) | null = null;
// Enter on the Restore button clicks on keydown, so its keyup lands on the
// option that just took focus. Activation needs a keydown seen inside the picker.
let activationArmed = false;

const roving = createRovingListbox({
  container: () => $(PICKER_SELECTOR),
  optionSelector: OPTION_SELECTOR,
  enabledOptionSelector: ENABLED_OPTION_SELECTOR,
  listboxSelector: PICKER_SELECTOR,
  noMatchesSelector: NO_MATCHES_SELECTOR,
  filterText: (row) => row.text(),
  onActivateRow: (row) => {
    if (!activationArmed) return;
    activationArmed = false;
    activateOption({ option: row });
  },
  onEscape: () => closeDestinationPicker({ returnFocus: true }),
});

export function isDestinationPickerOpen(): boolean {
  return $(PICKER_SELECTOR).length > 0;
}

function activateOption({ option }: { option: JQuery }): void {
  if (option.hasClass("disabled") || openItem === null) return;
  const destUtubID = Number(option.attr("data-dest-utub-id"));
  const item = openItem;
  void restoreTrashedURL({
    utubID: item.utubID,
    utubUrlID: item.utubUrlID,
    destUtubID,
  });
}

function buildOption({
  utub,
  isInitial,
}: {
  utub: { id: number; name: string; isLocked: boolean; memberRole: string };
  isInitial: boolean;
}): JQuery {
  const option = $('<div class="trashDestinationOption" role="option"></div>')
    .attr("data-dest-utub-id", String(utub.id))
    .attr("aria-selected", "false")
    .attr("tabindex", isInitial ? "0" : "-1");
  option.append($('<b class="trashDestinationName"></b>').text(utub.name));
  if (utub.isLocked) {
    option.addClass("disabled").attr("aria-disabled", "true");
    option.append(
      $('<span class="trashDestinationLocked"></span>').text(
        APP_CONFIG.strings.TRASH_PICKER_LOCKED,
      ),
    );
  } else {
    option.append(
      $('<span class="trashDestinationRole"></span>').text(utub.memberRole),
    );
  }
  option.on("click.trashDestination", () => activateOption({ option }));
  return option;
}

function handlePickerKeydown(event: KeyboardEvent): void {
  if (event.key === KEYS.ENTER || event.key === KEYS.SPACE) {
    activationArmed = true;
    return;
  }
  if (event.key !== "Home" && event.key !== "End") return;
  const rows = roving.enabledRowElements();
  if (rows.length === 0) return;
  event.preventDefault();
  roving.setActiveRow(event.key === "Home" ? rows[0] : rows[rows.length - 1]);
}

/** Opens (or toggles shut) the picker for a row; only one picker exists at a time. */
export function openDestinationPicker({
  item,
  row,
}: {
  item: TrashedUrlItem;
  row: JQuery;
}): void {
  const wasThisRow = openRow !== null && openRow[0] === row[0];
  closeDestinationPicker({ returnFocus: false });
  if (wasThisRow) return;

  log("open", { utubUrlID: item.utubUrlID });
  const picker = $('<div class="trashDestinationPicker"></div>');
  const destinations = getState().utubs.filter(
    (utub) => utub.id !== item.utubID,
  );
  const firstEnabled = destinations.find((utub) => !utub.isLocked);

  if (firstEnabled === undefined) {
    picker.append(
      $('<div class="trashDestinationNone" role="status" tabindex="-1"></div>')
        .attr("aria-live", "polite")
        .text(APP_CONFIG.strings.TRASH_NO_DESTINATION),
    );
  } else {
    picker
      .attr("role", "listbox")
      .attr("aria-label", APP_CONFIG.strings.TRASH_PICK_DESTINATION);
    destinations.forEach((utub) => {
      picker.append(buildOption({ utub, isInitial: utub === firstEnabled }));
    });
  }

  row.append(picker);
  row.find(RESTORE_BUTTON_SELECTOR).attr("aria-expanded", "true");
  openRow = row;
  openItem = item;
  activationArmed = false;

  const pickerElement = picker[0];
  homeEndListener = handlePickerKeydown;
  keyupResetListener = () => {
    activationArmed = false;
  };
  // Roving's keyup listener must run before the reset below consumes the flag.
  roving.attachKeyListeners();
  pickerElement.addEventListener("keydown", homeEndListener);
  pickerElement.addEventListener("keyup", keyupResetListener);

  if (firstEnabled === undefined) {
    picker.find(".trashDestinationNone").trigger("focus");
  } else {
    picker.find(ENABLED_OPTION_SELECTOR).first().trigger("focus");
  }
}

export function closeDestinationPicker({
  returnFocus,
}: {
  returnFocus: boolean;
}): void {
  const picker = $(PICKER_SELECTOR);
  if (picker.length > 0) {
    roving.detachKeyListeners();
    if (homeEndListener !== null) {
      picker[0].removeEventListener("keydown", homeEndListener);
    }
    if (keyupResetListener !== null) {
      picker[0].removeEventListener("keyup", keyupResetListener);
    }
    picker.remove();
  }
  const row = openRow;
  openRow = null;
  openItem = null;
  homeEndListener = null;
  keyupResetListener = null;
  activationArmed = false;
  if (row === null) return;
  const restore = row.find(RESTORE_BUTTON_SELECTOR);
  restore.attr("aria-expanded", "false");
  if (returnFocus) restore.trigger("focus");
}

/** Puts focus back on the picker's active option (after a 409 keeps it open). */
export function refocusDestinationPicker(): void {
  const rows = roving.enabledRowElements();
  if (rows.length === 0) return;
  const current = rows.find((row) => row.getAttribute("tabindex") === "0");
  roving.setActiveRow(current ?? rows[0]);
}

export function initDestinationPicker(): void {
  onTrashTabChanged(() => {
    if (isDestinationPickerOpen())
      closeDestinationPicker({ returnFocus: false });
  });
}
