import type { Schema, SuccessResponse } from "../../types/api-helpers.d.ts";

import { $, getInputValue } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { isUtubLockedHandled } from "../utub-locked.js";
import { emit } from "../../lib/metrics-client.js";
import { clearOpenForm, setOpenForm } from "../../lib/modal-tracking.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import { showInput, hideInput } from "../btns-forms.js";
import { getState, setState } from "../../store/app-store.js";
import { fitUTubHeaderAndSubheader } from "../utubs/header-fit.js";
import { updateUTubNameHideInput } from "./update-name.js";
import { showFieldSavedTick } from "./field-saved-tick.js";
import { isCoarsePointer } from "../mobile.js";
import { deselectAllURLs } from "./cards/selection.js";
import {
  isMultiSelectActive,
  refreshMultiSelectToggleVisibility,
} from "./bulk-actions/bulk-mode.js";
import { temporarilyHideSearchForEdit, showURLSearchIcon } from "./search.js";
import {
  FORM_CANCEL_TRIGGER,
  FORM_SUBMIT_TRIGGER,
  HOME_FORM,
  UTUB_DESC_EDIT_OPEN_TRIGGER,
} from "../../types/metrics-dim-values.js";
import { debug } from "../../lib/debug.js";

const log = debug("urls");

let descEditOpenedViaKeyboard = false;

// Per-field in-flight guard for the mobile keep-open path (symmetric with the
// name field's nameSubmitInFlight). Blocks a second overlapping submit until the
// PATCH settles; only ever set on the panelOpen path, reflected via
// aria-disabled (never native `disabled`, which would drop focus).
let descriptionSubmitInFlight = false;

export function clearDescriptionSubmitInFlight(): void {
  descriptionSubmitInFlight = false;
  $("#utubDescriptionSubmitBtnUpdate").removeAttr("aria-disabled");
}

type UpdateUtubDescRequest = Schema<"UpdateUTubDescriptionRequest">;
type UpdateUtubDescResponse = SuccessResponse<"updateUtubDesc">;
type UpdateUtubDescError = Schema<"ErrorResponse_UTubErrorCodes">;

const UPDATE_UTUB_DESCRIPTION_FIELD_NAMES = ["utubDescription"] as const;

type UpdateUtubDescriptionFieldName =
  (typeof UPDATE_UTUB_DESCRIPTION_FIELD_NAMES)[number];

function isUpdateUtubDescriptionFieldName(
  key: string,
): key is UpdateUtubDescriptionFieldName {
  return (UPDATE_UTUB_DESCRIPTION_FIELD_NAMES as readonly string[]).includes(
    key,
  );
}

export function setupUpdateUTubDescriptionEventListeners(utubID: number): void {
  $("#URLDeckSubheader").removeClass("editable");
  $("#UTubDescriptionSubheaderWrap")
    .removeClass("editable-wrap")
    .off("click.updateUTubDesc");
  const descPencilIcon = $("#UTubDescriptionSubheaderWrap .edit-pencil-icon");
  descPencilIcon.addClass("hidden").off("keydown.updateUTubDesc");

  const utubDescriptionSubmitBtnUpdate = $("#utubDescriptionSubmitBtnUpdate");
  const utubDescriptionCancelBtnUpdate = $("#utubDescriptionCancelBtnUpdate");

  // A locked UTub is frozen to all mutations, so the description never becomes
  // editable — skip the editable class, pencil, and click/keydown handlers,
  // exactly as for a non-owner.
  if (getState().isCurrentUserOwner && !getState().isCurrentUTubLocked) {
    $("#URLDeckSubheader").addClass("editable");
    $("#UTubDescriptionSubheaderWrap").addClass("editable-wrap");
    descPencilIcon.removeClass("hidden");

    function openDescriptionEdit(trigger: "pencil_icon" | "keyboard"): void {
      // Bound to the whole subheader wrap, so hiding the pencil in multi-select
      // mode is not enough — gate the open itself. Its deselectAllURLs() only
      // clears the single-select field, leaving the multi-select set stranded.
      if (isMultiSelectActive()) return;
      emit({ event: UI_EVENTS.UI_UTUB_DESC_EDIT_OPEN, trigger });
      setOpenForm(HOME_FORM.UTUB_DESC_EDIT);
      deselectAllURLs();
      updateUTubNameHideInput();
      updateUTubDescriptionShowInput(utubID);
    }

    $("#UTubDescriptionSubheaderWrap").offAndOnExact(
      "click.updateUTubDesc",
      () => {
        // On mobile the consolidated panel (opened via #utubEditPanelToggle) is
        // the only entry point — tapping the pencil-less description row is a
        // no-op.
        if (isCoarsePointer()) return;
        openDescriptionEdit("pencil_icon");
      },
    );

    descPencilIcon.offAndOnExact("keydown.updateUTubDesc", function (keyEvent) {
      if (keyEvent.key === KEYS.ENTER || keyEvent.key === KEYS.SPACE) {
        keyEvent.preventDefault();
        descEditOpenedViaKeyboard = true;
        openDescriptionEdit("keyboard");
      }
    });
  }

  utubDescriptionSubmitBtnUpdate.offAndOnExact("click", function () {
    // Block an overlapping submit while a kept-open submit is in flight
    // (descriptionSubmitInFlight is only ever set on the mobile panelOpen path).
    if (descriptionSubmitInFlight) return;
    emit({
      event: UI_EVENTS.UI_FORM_SUBMIT,
      form: HOME_FORM.UTUB_DESC_EDIT,
      trigger: FORM_SUBMIT_TRIGGER.BUTTON_CLICK,
    });
    clearOpenForm();
    updateUTubDescription(utubID);
  });

  utubDescriptionCancelBtnUpdate.offAndOnExact("click", function () {
    emit({
      event: UI_EVENTS.UI_FORM_CANCEL,
      form: HOME_FORM.UTUB_DESC_EDIT,
      trigger: FORM_CANCEL_TRIGGER.CANCEL_BUTTON,
    });
    clearOpenForm();
    updateUTubDescriptionHideInput(utubID);
  });
}

// Create event listeners to escape from updating UTub name
function setEventListenersToEscapeUpdateUTubDescription(utubID: number): void {
  // Allow user to still click in the text box
  $("#utubDescriptionUpdate")
    .offAndOn("focus.updateUTubDescription", function () {
      // Idempotent rebind (symmetric with the name field): the panel keeps the
      // description field refocusable across repeated submits while open, so a
      // bare `.on()` would stack duplicate keydown handlers on each re-focus.
      $("#utubDescriptionUpdate")
        .off("keydown.updateUTubDescription")
        .on("keydown.updateUTubDescription", function (keyEvent) {
          if (keyEvent.originalEvent?.repeat) return;
          switch (keyEvent.key) {
            case KEYS.ENTER:
              // Block an overlapping submit while a kept-open submit is in flight.
              if (descriptionSubmitInFlight) return;
              // Handle enter key pressed
              emit({
                event: UI_EVENTS.UI_FORM_SUBMIT,
                form: HOME_FORM.UTUB_DESC_EDIT,
                trigger: FORM_SUBMIT_TRIGGER.ENTER_KEY,
              });
              clearOpenForm();
              updateUTubDescription(utubID);
              break;
            case KEYS.ESCAPE:
              // On mobile, defer to the single document-level panel Escape
              // handler (bound in setupUTubEditPanelToggle) so the two
              // mechanisms don't both fire and double-close on one keypress.
              if (isCoarsePointer()) return;
              // Handle escape key pressed
              emit({
                event: UI_EVENTS.UI_FORM_CANCEL,
                form: HOME_FORM.UTUB_DESC_EDIT,
                trigger: FORM_CANCEL_TRIGGER.ESCAPE_KEY,
              });
              clearOpenForm();
              updateUTubDescriptionHideInput(utubID);
              break;
            default:
            /* no-op */
          }
        });
    })
    .offAndOn("blur.updateUTubDescription", function () {
      $("#utubDescriptionUpdate").off("keydown.updateUTubDescription");
    });

  // Bind clicking outside the window
  $(window).offAndOn(
    "click.updateUTubDescription",
    function (windowClickEvent) {
      if (
        $(windowClickEvent.target).closest("#UTubDescriptionSubheaderWrap")
          .length ||
        $(windowClickEvent.target).is($("#utubDescriptionUpdate")) ||
        $(windowClickEvent.target).is(
          $("#URLDeckSubheaderCreateDescription"),
        ) ||
        $(windowClickEvent.target).closest("#utubDescriptionSubmitBtnUpdate")
          .length ||
        $(windowClickEvent.target).closest("#utubDescriptionCancelBtnUpdate")
          .length
      )
        return;

      emit({
        event: UI_EVENTS.UI_FORM_CANCEL,
        form: HOME_FORM.UTUB_DESC_EDIT,
        trigger: FORM_CANCEL_TRIGGER.OUTSIDE_CLICK,
      });
      clearOpenForm();
      // Hide UTub description update fields
      updateUTubDescriptionHideInput(utubID);
    },
  );
}

function removeEventListenersToEscapeUpdateUTubDescription(): void {
  $(window).off(".updateUTubDescription");
  $(document).off(".updateUTubDescription");
  // Also detach the input's own focus/blur/keydown namespace, mirroring the
  // name field's teardown — otherwise repeated panel opens stack handlers on
  // #utubDescriptionUpdate across the keep-open lifecycle.
  $("#utubDescriptionUpdate").off(".updateUTubDescription");
}

export function showCreateDescriptionButtonAlways(utubID: number): void {
  const clickToCreateDesc = $("#URLDeckSubheaderCreateDescription");
  clickToCreateDesc.removeClass("opa-0 height-0").addClass("opa-1 height-2rem");
  clickToCreateDesc.enableTab();

  clickToCreateDesc.offAndOnExact("click.createUTubdescription", function () {
    emit({
      event: UI_EVENTS.UI_UTUB_DESC_EDIT_OPEN,
      trigger: UTUB_DESC_EDIT_OPEN_TRIGGER.CREATE_BUTTON,
    });
    setOpenForm(HOME_FORM.UTUB_DESC_EDIT);
    clickToCreateDesc
      .removeClass("opa-1 height-2rem")
      .addClass("opa-0 height-0 width-0");

    updateUTubDescriptionShowInput(utubID);
    clickToCreateDesc.off("click.createUTubdescription");
  });
}

export function removeEventListenersForShowCreateUTubDescIfEmptyDesc(): void {
  const clickToCreateDesc = $("#URLDeckSubheaderCreateDescription");
  clickToCreateDesc.off("click.createUTubdescription");
  clickToCreateDesc.removeClass("opa-1 height-2rem").addClass("opa-0 height-0");
  clickToCreateDesc.disableTab();
  $("#URLDeckNoDescription").hideClass();
}

// Shows input fields for updating an exiting UTub's description
export function updateUTubDescriptionShowInput(utubID: number): void {
  // Setup event listeners for window click and escape/enter keys
  setEventListenersToEscapeUpdateUTubDescription(utubID);

  // Show update fields
  const utubDescriptionUpdate = $("#utubDescriptionUpdate");
  utubDescriptionUpdate.val($("#URLDeckSubheader").text());
  showInput("#utubDescriptionUpdate");
  utubDescriptionUpdate.trigger("focus");
  $("#utubDescriptionSubmitBtnUpdate").showClassNormal();

  // Hide current description and pencil icon
  $("#UTubDescription").hideClass();
  $("#URLDeckSubheader").hideClass();
  $("#UTubDescriptionSubheaderWrap .edit-pencil-icon").addClass("hidden");
  $("#URLDeckSubheaderCreateDescription").addClass("width-0");
  temporarilyHideSearchForEdit();
  $("#urlBtnCreate").hideClass();
  $("#urlBtnMultiSelect").hideClass();

  removeEventListenersForShowCreateUTubDescIfEmptyDesc();
}

// Hides input fields for updating an exiting UTub's description
export function updateUTubDescriptionHideInput(
  utubID: number | null = null,
): void {
  // Mobile form-model guard: while the consolidated panel is open, a per-field
  // submit keeps the description input + submit button visible, the chrome
  // hidden, and the Enter/Escape listeners live. Only the true panel-close Hide
  // (signal already flipped to "closed" by resetUTubEditPanelState) runs the
  // full collapse + restore + deferred empty-description CTA re-arm.
  const panelOpen =
    isCoarsePointer() && !$("#utubEditPanelClose").hasClass("hidden");

  if (panelOpen) {
    // Keep-open path: re-register the tracked open form (so a later pagehide
    // doesn't misreport UI_FORM_CANCEL) and clear any stale error state — the
    // one carve-out that runs on both paths. Everything else (input/submit
    // hide, listener teardown, chrome restore, create-description CTA re-arm)
    // is deferred to the panel-closed Hide.
    setOpenForm(HOME_FORM.UTUB_DESC_EDIT);
    resetUpdateUTubDescriptionFailErrors();
    return;
  }

  const editWasOpen = $("#URLDeckSubheader").hasClass("hidden");

  // Hide update fields
  hideInput("#utubDescriptionUpdate");
  $("#utubDescriptionSubmitBtnUpdate").hideClass();

  // Remove event listeners for window click and escape/enter keys
  removeEventListenersToEscapeUpdateUTubDescription();

  // Show values and pencil icon (only for owners), return focus to pencil
  $("#URLDeckSubheader").showClassNormal();
  if (getState().isCurrentUserOwner) {
    const descPencilIcon = $("#UTubDescriptionSubheaderWrap .edit-pencil-icon");
    descPencilIcon.removeClass("hidden");
    if (editWasOpen && descEditOpenedViaKeyboard) descPencilIcon[0]?.focus();
  }
  descEditOpenedViaKeyboard = false;
  showURLSearchIcon();
  $("#urlBtnCreate").showClassNormal();
  // Restore the multi-select toggle (guarded on the UTub still having URLs).
  refreshMultiSelectToggleVisibility();

  // Reset errors on hiding of inputs
  resetUpdateUTubDescriptionFailErrors();
  $("#URLDeckSubheaderCreateDescription").removeClass("width-0");
  // Reconcile the subheader wrap to the current description state. selectors.ts
  // hides #UTubDescriptionSubheaderWrap for an empty-description UTub and shows
  // it (showClassFlex) when a description exists; the success handler's
  // empty/non-empty arms that normally manage this wrap are deferred while the
  // mobile panel is open, so reconcile it here on the panel-closed (and desktop)
  // Hide — otherwise a description added via the mobile panel stays invisible
  // until a UTub reselect. Idempotent on desktop, where the success arms have
  // already set the same state.
  $("#UTubDescriptionSubheaderOuterWrap").removeClass("height-2rem");
  if (!$("#URLDeckSubheader").text().length) {
    $("#UTubDescriptionSubheaderWrap").hideClass();
    if (utubID != null) {
      showCreateDescriptionButtonAlways(utubID);
    }
  } else {
    $("#UTubDescriptionSubheaderWrap").showClassFlex();
  }
}

// Handles post request and response for updating an existing UTub's description
function updateUTubDescription(utubID: number): void {
  // Skip if identical
  if ($("#URLDeckSubheader").text() === $("#utubDescriptionUpdate").val()) {
    log("updateUTubDescription skipped — value unchanged", { utubID });
    updateUTubDescriptionHideInput(utubID);
    return;
  }

  // Extract data to submit in POST request
  const [postURL, data] = updateUTubDescriptionSetup(utubID);

  const panelOpen =
    isCoarsePointer() && !$("#utubEditPanelClose").hasClass("hidden");
  if (panelOpen) {
    descriptionSubmitInFlight = true;
    $("#utubDescriptionSubmitBtnUpdate").attr("aria-disabled", "true");
  }

  const request = ajaxCall("patch", postURL, data);

  // Handle response
  request.done(function (response: UpdateUtubDescResponse, _textStatus, xhr) {
    // Re-enable before the status check so a non-200 still clears the guard.
    clearDescriptionSubmitInFlight();
    if (xhr.status === 200) {
      updateUTubDescriptionSuccess(response, utubID);
    }
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    clearDescriptionSubmitInFlight();
    updateUTubDescriptionFail(xhr);
  });
}

// Handles preparation for post request to update an existing UTub
function updateUTubDescriptionSetup(
  utubID: number,
): [string, UpdateUtubDescRequest] {
  const postURL = APP_CONFIG.routes.updateUTubDescription(utubID);

  const updatedDescription = getInputValue("#utubDescriptionUpdate");
  const data: UpdateUtubDescRequest = { utubDescription: updatedDescription };

  return [postURL, data];
}

// Handle updateion of UTub's description
function updateUTubDescriptionSuccess(
  response: UpdateUtubDescResponse,
  utubID: number,
): void {
  // A submit is fire-and-forget while the mobile panel stays open, so a success
  // can land after the user has switched to a different UTub. Every write here
  // targets the singleton `#URLDeckSubheader` DOM / `activeUTubDescription`
  // state for the CURRENTLY displayed UTub (the utubs summary array holds no
  // description, so there is no id-keyed array write to preserve). Bail entirely
  // when the response is no longer for the active UTub so a stale success can't
  // overwrite the new UTub's subheader (DD-1).
  if (response.utubID !== getState().activeUTubID) return;

  const utubDescription = response.utubDescription ?? "";

  setState({ activeUTubDescription: response.utubDescription });
  const utubDescriptionElem = $("#URLDeckSubheader");
  const originalUTubDescriptionLength = utubDescriptionElem.text().length;

  // Change displayed and updateable value for utub description
  $("#URLDeckSubheader").text(utubDescription);
  $("#utubDescriptionUpdate").val(utubDescription);

  const panelOpen =
    isCoarsePointer() && !$("#utubEditPanelClose").hasClass("hidden");

  // Both the empty-description arm and the first-non-empty-transition arm mutate
  // the create-description CTA / subheader chrome. While the mobile panel is
  // open neither may run — they are deferred as a single unit to the
  // panel-closed Hide (updateUTubDescriptionHideInput's empty-desc re-arm). On
  // desktop / panel closed, run them exactly as before.
  if (!panelOpen) {
    if (utubDescription.length === 0) {
      showCreateDescriptionButtonAlways(utubID);
      $("#UTubDescriptionSubheaderOuterWrap").removeClass("height-2rem");
      $("#UTubDescriptionSubheaderWrap").hideClass();
    } else if (originalUTubDescriptionLength === 0) {
      removeEventListenersForShowCreateUTubDescIfEmptyDesc();
      $("#UTubDescriptionSubheaderOuterWrap").removeClass("height-2rem");
      $("#UTubDescriptionSubheaderWrap").showClassFlex();
      $("#URLDeckSubheaderCreateDescription").disableTab();
    }
  }

  // Hide all inputs on success (keeps the field open on the mobile panel path
  // via the panelOpen guard inside updateUTubDescriptionHideInput).
  updateUTubDescriptionHideInput();
  fitUTubHeaderAndSubheader();

  // Mobile form model: flash a transient "Saved ✓" beside the still-open field
  // on a real change. updateUTubDescriptionSuccess is only reached on a genuine
  // 200 for a changed value, so no unchanged/no-op guard is needed here.
  if (panelOpen) {
    showFieldSavedTick({
      tick: $("#utubDescriptionSavedTick"),
      announce: $("#fieldSavedAnnouncement"),
      label: APP_CONFIG.strings.FIELD_SAVED_LABEL_UTUB_DESCRIPTION,
    });
  }
}

// Handle error response display to user
function updateUTubDescriptionFail(xhr: JQuery.jqXHR): void {
  if (is429Handled(xhr)) return;
  if (isUtubLockedHandled(xhr)) return;

  log("updateUTubDescription failed", {
    status: xhr.status,
    hasResponseJSON: "responseJSON" in xhr,
  });

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
      const responseJSON = xhr.responseJSON as UpdateUtubDescError;
      if (responseJSON.message) {
        if (responseJSON.errors)
          updateUTubDescriptionFailErrors(
            responseJSON.errors as Partial<
              Record<UpdateUtubDescriptionFieldName, string[]>
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
function updateUTubDescriptionFailErrors(
  errors: Partial<Record<UpdateUtubDescriptionFieldName, string[]>>,
): void {
  for (const errorFieldName in errors) {
    if (isUpdateUtubDescriptionFieldName(errorFieldName)) {
      const errorMessage = errors[errorFieldName]![0];
      displayUpdateUTubDescriptionFailErrors(errorFieldName, errorMessage);
    }
  }
}

// Show the error message and highlight the input box border red on error of field
function displayUpdateUTubDescriptionFailErrors(
  key: string,
  errorMessage: string,
): void {
  $("#" + key + "Update-error")
    .addClass("visible")
    .text(errorMessage);
  $("#" + key + "Update").addClass("invalid-field");
}

function resetUpdateUTubDescriptionFailErrors(): void {
  $("#utubDescriptionUpdate-error").removeClass("visible");
  $("#utubDescriptionUpdate").removeClass("invalid-field");
}
