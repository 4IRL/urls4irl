import { $ } from "../../lib/globals.js";
import {
  hideAndResetMemberCombobox,
  showMemberCombobox,
} from "./member-combobox.js";

// Thin shell over the add-member combobox (member-combobox.ts). This module
// keeps only the two exported entry points other modules depend on —
// setupShowCreateMemberFormEventListeners (deck.ts) and createMemberHideInput
// (btns-forms.ts) — plus the module-private opener; all the input/listbox/chips/
// submit logic now lives in the combobox component. The single-input add form
// (13 superseded functions) was removed when the combobox replaced it.

export function setupShowCreateMemberFormEventListeners(utubID: number): void {
  const memberBtnCreate = $("#memberBtnCreate");

  // Full off("click") clears any leftover reopen handler that
  // hideAndResetMemberCombobox may have bound (offAndOnExact), so a re-bind on
  // UTub select never double-opens the combobox.
  memberBtnCreate.off("click").on("click.createMember", function () {
    createMemberShowInput(utubID);
  });
}

// Shows the add-member combobox (delegates entirely to member-combobox.ts).
function createMemberShowInput(utubID: number): void {
  showMemberCombobox(utubID);
}

// Hides + resets the add-member combobox (delegates entirely to
// member-combobox.ts). Preserved for btns-forms.ts's hideInputs() cleanup path.
export function createMemberHideInput(): void {
  hideAndResetMemberCombobox();
}
