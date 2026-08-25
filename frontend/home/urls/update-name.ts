import type { Schema, SuccessResponse } from "../../types/api-helpers.d.ts";
import type { UtubSummaryItem } from "../../types/utub.js";

import { $, getInputValue } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { isUtubLockedHandled } from "../utub-locked.js";
import { emit } from "../../lib/metrics-client.js";
import { clearOpenForm, setOpenForm } from "../../lib/modal-tracking.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import {
  getCurrentUTubName,
  getAllAccessibleUTubNames,
  sameNameWarningHideModal,
} from "../utubs/utils.js";
import { getState, setState } from "../../store/app-store.js";
import { fitUTubHeaderAndSubheader } from "../utubs/header-fit.js";
import { highlightInput, showInput, hideInput } from "../btns-forms.js";
import { temporarilyHideSearchForEdit, showURLSearchIcon } from "./search.js";
import {
  updateUTubDescriptionHideInput,
  updateUTubDescriptionShowInput,
} from "./update-description.js";
import { showFieldSavedTick } from "./field-saved-tick.js";
import { isCoarsePointer } from "../mobile.js";
import { deselectAllURLs } from "./cards/selection.js";
import {
  isMultiSelectActive,
  refreshMultiSelectToggleVisibility,
} from "./bulk-actions/bulk-mode.js";
import {
  FORM_CANCEL_TRIGGER,
  FORM_SUBMIT_TRIGGER,
  HOME_FORM,
  UTUB_DESC_EDIT_OPEN_TRIGGER,
} from "../../types/metrics-dim-values.js";
import { debug } from "../../lib/debug.js";

const log = debug("urls");

let nameEditOpenedViaKeyboard = false;

// Per-field in-flight guard for the mobile keep-open path. While the name field
// stays open across a submit, a second overlapping submit (double-tap / repeated
// Enter / sameName-modal double-tap) must be blocked until the PATCH settles.
// Only ever set on the panelOpen path, so desktop (collapse-on-submit) is
// unaffected. Reflected on the submit control via aria-disabled — never native
// `disabled`, which would drop focus and pull it from the a11y tree.
let nameSubmitInFlight = false;

export function clearNameSubmitInFlight(): void {
  nameSubmitInFlight = false;
  $("#utubNameSubmitBtnUpdate").removeAttr("aria-disabled");
}

type UpdateUtubNameRequest = Schema<"UpdateUTubNameRequest">;
type UpdateUtubNameResponse = SuccessResponse<"updateUtubName">;
type UpdateUtubNameError = Schema<"ErrorResponse_UTubErrorCodes">;

const UPDATE_UTUB_NAME_FIELD_NAMES = ["utubName"] as const;

type UpdateUtubNameFieldName = (typeof UPDATE_UTUB_NAME_FIELD_NAMES)[number];

function isUpdateUtubNameFieldName(
  key: string,
): key is UpdateUtubNameFieldName {
  return (UPDATE_UTUB_NAME_FIELD_NAMES as readonly string[]).includes(key);
}

function checkSameNameUTubOnUpdate(name: string, utubID: number): void {
  if (getAllAccessibleUTubNames().includes(name)) {
    // UTub with same name exists. Confirm action with user
    log(
      "checkSameNameUTubOnUpdate: duplicate name detected, showing confirmation modal",
      { name, utubID },
    );
    sameUTubNameOnUpdateUTubNameWarningShowModal(utubID);
  } else {
    // UTub name is unique. Proceed with requested action
    updateUTubName(utubID);
  }
}

export function setupUpdateUTubNameEventListeners(utubID: number): void {
  $("#URLDeckHeader").removeClass("editable");
  $("#UTubNameUpdateWrap")
    .removeClass("editable-wrap")
    .off("click.updateUTubname");
  const namePencilIcon = $("#UTubNameUpdateWrap .edit-pencil-icon");
  namePencilIcon.addClass("hidden").off("keydown.updateUTubname");

  // A locked UTub is frozen to all mutations. Bail like a non-owner so the
  // title never becomes editable — no editable class, no pencil, and no
  // click/keydown handler to open the inline edit form.
  if (!getState().isCurrentUserOwner || getState().isCurrentUTubLocked) return;

  $("#URLDeckHeader").addClass("editable");
  $("#UTubNameUpdateWrap").addClass("editable-wrap");
  namePencilIcon.removeClass("hidden");

  function openNameEdit(trigger: "pencil_icon" | "keyboard"): void {
    // The wrap/title click that opens this is unreachable via the (CSS-hidden)
    // pencil in multi-select mode, but the handler is bound to the whole wrap —
    // so gate the open itself. Its deselectAllURLs() only clears the
    // single-select field; opening here would strand the multi-select set under
    // the editor.
    if (isMultiSelectActive()) return;
    emit({ event: UI_EVENTS.UI_UTUB_NAME_EDIT_OPEN, trigger });
    setOpenForm(HOME_FORM.UTUB_NAME_EDIT);
    deselectAllURLs();
    updateUTubDescriptionHideInput(utubID);
    updateUTubNameShowInput(utubID);
  }

  $("#UTubNameUpdateWrap").offAndOnExact("click.updateUTubname", () => {
    // On mobile the consolidated panel (opened via #utubEditPanelToggle) is the
    // only entry point — tapping the now-pencil-less name row is a no-op.
    if (isCoarsePointer()) return;
    openNameEdit("pencil_icon");
  });

  namePencilIcon.offAndOnExact("keydown.updateUTubname", function (keyEvent) {
    if (keyEvent.key === KEYS.ENTER || keyEvent.key === KEYS.SPACE) {
      keyEvent.preventDefault();
      nameEditOpenedViaKeyboard = true;
      openNameEdit("keyboard");
    }
  });

  const utubNameSubmitBtnUpdate = $("#utubNameSubmitBtnUpdate");
  const utubNameCancelBtnUpdate = $("#utubNameCancelBtnUpdate");

  utubNameSubmitBtnUpdate.offAndOnExact("click.updateUTubname", function () {
    // Block an overlapping submit while a kept-open submit is in flight
    // (nameSubmitInFlight is only ever set on the mobile panelOpen path).
    if (nameSubmitInFlight) return;
    emit({
      event: UI_EVENTS.UI_FORM_SUBMIT,
      form: HOME_FORM.UTUB_NAME_EDIT,
      trigger: FORM_SUBMIT_TRIGGER.BUTTON_CLICK,
    });
    clearOpenForm();
    // Skip if update is identical to original
    if ($("#URLDeckHeader").text() === $("#utubNameUpdate").val()) {
      updateUTubNameHideInput();
      return;
    }
    checkSameNameUTubOnUpdate(getInputValue("#utubNameUpdate"), utubID);
  });

  utubNameCancelBtnUpdate.offAndOnExact("click.updateUTubname", function () {
    emit({
      event: UI_EVENTS.UI_FORM_CANCEL,
      form: HOME_FORM.UTUB_NAME_EDIT,
      trigger: FORM_CANCEL_TRIGGER.CANCEL_BUTTON,
    });
    clearOpenForm();
    updateUTubNameHideInput();
  });
}

// Create event listeners to escape from updating UTub name
function setEventListenersToEscapeUpdateUTubName(utubID: number): void {
  // Allow user to still click in the text box
  $("#utubNameUpdate")
    .offAndOn("focus.updateUTubname", function () {
      // Idempotent rebind: because the panel now keeps the name field open and
      // refocusable across repeated submits while the panel stays open (the
      // keydown teardown only runs on true panel close), a bare `.on()` here
      // would stack duplicate handlers on each re-focus. `.off().on()` mirrors
      // the offAndOn plugin's dedupe, applied inline inside this focus callback.
      $("#utubNameUpdate")
        .off("keydown.updateUTubname")
        .on("keydown.updateUTubname", function (keyEvent) {
          if (keyEvent.originalEvent?.repeat) return;
          switch (keyEvent.key) {
            case KEYS.ENTER:
              // Block an overlapping submit while a kept-open submit is in flight.
              if (nameSubmitInFlight) return;
              // Handle enter key pressed
              emit({
                event: UI_EVENTS.UI_FORM_SUBMIT,
                form: HOME_FORM.UTUB_NAME_EDIT,
                trigger: FORM_SUBMIT_TRIGGER.ENTER_KEY,
              });
              clearOpenForm();
              // Skip if update is identical
              if ($("#URLDeckHeader").text() === $("#utubNameUpdate").val()) {
                updateUTubNameHideInput();
                return;
              }
              checkSameNameUTubOnUpdate(
                getInputValue("#utubNameUpdate"),
                utubID,
              );
              break;
            case KEYS.ESCAPE:
              // On mobile, defer to the single document-level panel Escape handler
              // (bound in setupUTubEditPanelToggle) so the two mechanisms don't
              // both fire and double-close/double-focus-return on one keypress.
              if (isCoarsePointer()) return;
              // Handle escape key pressed
              emit({
                event: UI_EVENTS.UI_FORM_CANCEL,
                form: HOME_FORM.UTUB_NAME_EDIT,
                trigger: FORM_CANCEL_TRIGGER.ESCAPE_KEY,
              });
              clearOpenForm();
              updateUTubNameHideInput();
              break;
            default:
            /* no-op */
          }
        });
    })
    .offAndOn("blur.updateUTubname", function () {
      // The key handler is bound as keydown (not keyup); detach the matching
      // namespace so blur actually removes it across repeated keep-open submits.
      $("#utubNameUpdate").off("keydown.updateUTubname");
    });

  // Bind clicking outside the window
  $(window).offAndOn("click.updateUTubname", function (windowClickEvent) {
    // Ignore clicks on the header wrapper (title text, pencil icon, gap)
    if ($(windowClickEvent.target).closest("#UTubNameUpdateWrap").length)
      return;

    // Ignore clicks on the input box
    if ($(windowClickEvent.target).is($("#utubNameUpdate"))) return;

    // Ignore clicks on the submit button
    if ($(windowClickEvent.target).closest("#utubNameSubmitBtnUpdate").length)
      return;

    // Ignore clicks on the cancel button
    if ($(windowClickEvent.target).closest("#utubNameCancelBtnUpdate").length)
      return;

    emit({
      event: UI_EVENTS.UI_FORM_CANCEL,
      form: HOME_FORM.UTUB_NAME_EDIT,
      trigger: FORM_CANCEL_TRIGGER.OUTSIDE_CLICK,
    });
    clearOpenForm();
    // Hide UTub name update fields
    updateUTubNameHideInput();
  });
}

function removeEventListenersToEscapeUpdateUTubName(): void {
  $(window).off(".updateUTubname");
  $("#utubNameUpdate").off(".updateUTubname");
}

function sameUTubNameOnUpdateUTubNameWarningShowModal(utubID: number): void {
  const modalTitle = "Continue with this UTub name?";
  const modalBody = `${APP_CONFIG.strings.UTUB_UPDATE_SAME_NAME}`;
  const buttonTextDismiss = "Go Back to Editing";
  const buttonTextSubmit = "Edit Name";
  let isSubmitting = false;

  removeEventListenersToEscapeUpdateUTubName();

  $("#confirmModalTitle").text(modalTitle);

  $("#confirmModalBody").text(modalBody);

  $("#modalDismiss")
    .addClass("btn btn-secondary")
    .text(buttonTextDismiss)
    .offAndOnExact("click", function (dismissClickEvent) {
      dismissClickEvent.preventDefault();
      sameNameWarningHideModal();
      setEventListenersToEscapeUpdateUTubName(utubID);
      setTimeout(function () {
        highlightInput($("#utubNameUpdate"));
      }, 300);
    });

  $("#modalRedirect").hideClass();
  $("#modalRedirect").hide();

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-success")
    .text(buttonTextSubmit)
    .offAndOnExact("click", function () {
      // Block a double-tap on the confirm-modal "Edit Name" button while the
      // confirmed submit is already in flight (mobile keep-open path).
      if (nameSubmitInFlight) return;
      isSubmitting = true;
      updateUTubName(utubID);
    });

  $("#confirmModal").modal("show");
  $("#confirmModal").offAndOn("hidden.bs.modal", function (modalHiddenEvent) {
    modalHiddenEvent.stopPropagation();
    setEventListenersToEscapeUpdateUTubName(utubID);
    if (!isSubmitting) highlightInput($("#utubNameUpdate"));
  });
}

function rebindCreateDescriptionForNameUpdate(utubID: number): void {
  const clickToCreateDesc = $("#URLDeckSubheaderCreateDescription");
  clickToCreateDesc.offAndOnExact("click.createUTubdescription", function () {
    emit({
      event: UI_EVENTS.UI_UTUB_DESC_EDIT_OPEN,
      trigger: UTUB_DESC_EDIT_OPEN_TRIGGER.CREATE_BUTTON,
    });
    clickToCreateDesc
      .removeClass("opa-1 height-2rem")
      .addClass("opa-0 height-0");
    updateUTubNameHideInput();
    updateUTubDescriptionShowInput(utubID);
    clickToCreateDesc.off("click.createUTubdescription");
  });
}

// Shows input fields for updating an exiting UTub's name
export function updateUTubNameShowInput(utubID: number): void {
  // Setup event listeners on window and escape/enter keys to escape the input box
  setEventListenersToEscapeUpdateUTubName(utubID);

  // Show update fields
  const utubNameUpdate = $("#utubNameUpdate");
  const parentTitleElem = utubNameUpdate.closest(".titleElement");
  parentTitleElem.addClass("m-top-bot-0-5rem");
  utubNameUpdate.val(getCurrentUTubName() ?? "");
  showInput("#utubNameUpdate");
  utubNameUpdate.trigger("focus");

  // Hide current name and pencil icon
  $("#URLDeckHeader").hideClass();
  $("#UTubNameUpdateWrap .edit-pencil-icon").addClass("hidden");
  $("#urlBtnCreate").hideClass();
  $("#urlBtnMultiSelect").hideClass();
  temporarilyHideSearchForEdit();

  if ($("#URLDeckSubheader").text().length === 0) {
    rebindCreateDescriptionForNameUpdate(utubID);
  }
}

// Hides input fields for updating an existing UTub's name
export function updateUTubNameHideInput(): void {
  // Mobile form-model guard: while the consolidated panel is open, a per-field
  // submit keeps the name input open, the chrome hidden, and the Enter/Escape
  // listeners live. Only the true panel-close Hide (signal already flipped to
  // "closed" by resetUTubEditPanelState) runs the full collapse + restore.
  const panelOpen =
    isCoarsePointer() && !$("#utubEditPanelClose").hasClass("hidden");

  if (panelOpen) {
    // Keep-open path: leave the input visible (with its Show-path margin), the
    // pencil hidden, and the chrome (#urlBtnCreate + search funnel) hidden;
    // leave the Enter/Escape listeners bound across repeated submits. Re-register
    // the tracked open form so a later pagehide doesn't misreport
    // UI_FORM_CANCEL{navigation} for a field that is still genuinely open.
    setOpenForm(HOME_FORM.UTUB_NAME_EDIT);

    // Harmless housekeeping that runs on both paths: clear any stale error state
    // and keep the input value synced with the displayed header text.
    resetUpdateUTubNameFailErrors();
    $("#utubNameUpdate").val($("#URLDeckHeader").text());
    return;
  }

  const editWasOpen = $("#URLDeckHeader").hasClass("hidden");

  // Hide update fields
  hideInput("#utubNameUpdate");
  const utubNameUpdate = $("#utubNameUpdate");
  const parentTitleElem = utubNameUpdate.closest(".titleElement");
  parentTitleElem.removeClass("m-top-bot-0-5rem");

  // Show values and pencil icon (only for owners), return focus to pencil
  $("#URLDeckHeader").showClassNormal();
  if (getState().isCurrentUserOwner) {
    const namePencilIcon = $("#UTubNameUpdateWrap .edit-pencil-icon");
    namePencilIcon.removeClass("hidden");
    if (editWasOpen && nameEditOpenedViaKeyboard) namePencilIcon[0]?.focus();
  }
  nameEditOpenedViaKeyboard = false;
  $("#urlBtnCreate").showClassNormal();
  // Restore the multi-select toggle (guarded on the UTub still having URLs).
  refreshMultiSelectToggleVisibility();
  showURLSearchIcon();

  // Remove event listeners on window and escape/enter keys
  removeEventListenersToEscapeUpdateUTubName();

  if ($("#URLDeckSubheader").text().length === 0) {
    const clickToCreateDesc = $("#URLDeckSubheaderCreateDescription");
    clickToCreateDesc.off("click.createUTubdescription");
  }

  // Remove any errors if shown
  resetUpdateUTubNameFailErrors();

  // Replace default value
  $("#utubNameUpdate").val($("#URLDeckHeader").text());
}

// Handles post request and response for updating an existing UTub's name
function updateUTubName(utubID: number): void {
  // Skip if update is identical
  if ($("#URLDeckHeader").text() === $("#utubNameUpdate").val()) {
    log("updateUTubName skipped — value unchanged", { utubID });
    updateUTubNameHideInput();
    return;
  }

  // Extract data to submit in POST request
  const [postURL, data] = updateUTubNameSetup(utubID);

  const panelOpen =
    isCoarsePointer() && !$("#utubEditPanelClose").hasClass("hidden");
  if (panelOpen) {
    nameSubmitInFlight = true;
    $("#utubNameSubmitBtnUpdate").attr("aria-disabled", "true");
  }

  const request = ajaxCall("patch", postURL, data);

  // Handle response
  request.done(function (response: UpdateUtubNameResponse, _textStatus, xhr) {
    // Re-enable before the status check so a non-200 still clears the guard.
    clearNameSubmitInFlight();
    if (xhr.status === 200) {
      updateUTubNameSuccess(response);
    }
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    clearNameSubmitInFlight();
    updateUTubNameFail(xhr);
  });
}

// Handles preparation for post request to update an existing UTub
function updateUTubNameSetup(utubID: number): [string, UpdateUtubNameRequest] {
  const postURL = APP_CONFIG.routes.updateUTubName(utubID);

  const updatedUTubName = getInputValue("#utubNameUpdate");
  const data: UpdateUtubNameRequest = { utubName: updatedUTubName };

  return [postURL, data];
}

// Handle update of UTub's name
function updateUTubNameSuccess(response: UpdateUtubNameResponse): void {
  const utubName = response.utubName;

  // A submit is fire-and-forget while the mobile panel stays open, so a success
  // can land after the user has already switched to a different UTub. The
  // utubs-array write below is id-keyed (matches on response.utubID), so it is
  // always safe. But the singleton `#URLDeckHeader`/subheader DOM and the
  // `activeUTubName` state describe the CURRENTLY displayed UTub, so writing
  // them for a no-longer-active response would corrupt the new UTub's header
  // (DD-1). Gate those on the response still being for the active UTub.
  const isForActiveUTub = response.utubID === getState().activeUTubID;

  const utubs: UtubSummaryItem[] = getState().utubs;
  setState({
    utubs: utubs.map((utub) =>
      utub.id === response.utubID ? { ...utub, name: response.utubName } : utub,
    ),
    ...(isForActiveUTub ? { activeUTubName: response.utubName } : {}),
  });

  $("#confirmModal").modal("hide");

  // UTubDeck display updates — target the response's OWN list entry by id, not
  // `.active` (which for a stale response is now a different UTub and would be
  // mislabeled). Always safe: it labels exactly the UTub the response is for.
  $("#listUTubs")
    .find(`.UTubSelector[utubid='${response.utubID}']`)
    .find(".UTubName")
    .text(utubName);

  if (!isForActiveUTub) return;

  // Display updates — on mobile this keeps the field open via the panelOpen
  // guard inside updateUTubNameHideInput.
  setUTubNameAndDescription(utubName);

  // Mobile form model: on a real name change while the panel is open, flash a
  // transient "Saved ✓" beside the (still-open) field. updateUTubNameSuccess is
  // only reached on a genuine 200 for a changed value, so no unchanged/no-op
  // guard is needed here.
  const panelOpen =
    isCoarsePointer() && !$("#utubEditPanelClose").hasClass("hidden");
  if (panelOpen) {
    showFieldSavedTick({
      tick: $("#utubNameSavedTick"),
      announce: $("#fieldSavedAnnouncement"),
      label: APP_CONFIG.strings.FIELD_SAVED_LABEL_UTUB_NAME,
    });
  }
}

// Handle error response display to user
function updateUTubNameFail(xhr: JQuery.jqXHR): void {
  if (is429Handled(xhr)) return;
  if (isUtubLockedHandled(xhr)) return;

  log("updateUTubName failed", { status: xhr.status });

  if (!("responseJSON" in xhr)) {
    if (
      xhr.status === 403 &&
      xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      $("body").html(xhr.responseText);
      return;
    }
    window.location.assign(APP_CONFIG.routes.errorPage);
    return;
  }

  switch (xhr.status) {
    case 400: {
      const responseJSON = xhr.responseJSON as UpdateUtubNameError;
      if (responseJSON.message) {
        if (responseJSON.errors)
          updateUTubNameFailErrors(
            responseJSON.errors as Partial<
              Record<UpdateUtubNameFieldName, string[]>
            >,
          );
        break;
      }
    }
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}

// Cycle through the valid errors for updating a UTub name
function updateUTubNameFailErrors(
  errors: Partial<Record<UpdateUtubNameFieldName, string[]>>,
): void {
  for (const errorFieldName in errors) {
    if (isUpdateUtubNameFieldName(errorFieldName)) {
      const errorMessage = errors[errorFieldName]![0];
      displayUpdateUTubNameFailErrors(errorFieldName, errorMessage);
      return;
    }
  }
}

// Show the error message and highlight the input box border red on error of field
function displayUpdateUTubNameFailErrors(
  key: string,
  errorMessage: string,
): void {
  $("#" + key + "Update-error")
    .addClass("visible")
    .text(errorMessage);
  $("#" + key + "Update").addClass("invalid-field");
}

function resetUpdateUTubNameFailErrors(): void {
  $("#utubNameUpdate-error").removeClass("visible");
  $("#utubNameUpdate").removeClass("invalid-field");
}

export function setUTubNameAndDescription(utubName: string): void {
  $("#URLDeckHeader").text(utubName);
  $("#utubNameUpdate").val(utubName);
  updateUTubNameHideInput();
  fitUTubHeaderAndSubheader();
}
