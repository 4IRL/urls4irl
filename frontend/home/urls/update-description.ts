import type { components, operations } from "../../types/api.d.ts";

import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { showInput, hideInput } from "../btns-forms.js";
import { setState } from "../../store/app-store.js";
import { isHidden } from "../visibility.js";
import { updateUTubNameHideInput } from "./update-name.js";
import { deselectAllURLs } from "./cards/selection.js";

type UpdateUtubDescRequest =
  components["schemas"]["UpdateUTubDescriptionRequest"];
type UpdateUtubDescResponse =
  operations["updateUtubDesc"]["responses"][200]["content"]["application/json"];
type UpdateUtubDescError =
  components["schemas"]["ErrorResponse_UTubErrorCodes"];

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
  const utubDescriptionSubmitBtnUpdate = $("#utubDescriptionSubmitBtnUpdate");
  const utubDescriptionCancelBtnUpdate = $("#utubDescriptionCancelBtnUpdate");

  // Update UTub description
  $("#updateUTubDescriptionBtn").offAndOnExact("click", function () {
    deselectAllURLs();
    updateUTubNameHideInput();
    updateUTubDescriptionShowInput(utubID);
  });

  utubDescriptionSubmitBtnUpdate.offAndOnExact("click", function () {
    updateUTubDescription(utubID);
  });

  utubDescriptionCancelBtnUpdate.onExact("click", function () {
    updateUTubDescriptionHideInput(utubID);
  });
}

// Create event listeners to escape from updating UTub name
function setEventListenersToEscapeUpdateUTubDescription(utubID: number): void {
  // Allow user to still click in the text box
  $("#utubDescriptionUpdate")
    .offAndOn("focus.updateUTubDescription", function () {
      $("#utubDescriptionUpdate").on(
        "keyup.updateUTubDescription",
        function (keyEvent) {
          if (keyEvent.originalEvent.repeat) return;
          switch (keyEvent.key) {
            case KEYS.ENTER:
              // Handle enter key pressed
              updateUTubDescription(utubID);
              break;
            case KEYS.ESCAPE:
              // Handle escape key pressed
              updateUTubDescriptionHideInput(utubID);
              break;
            default:
            /* no-op */
          }
        },
      );
    })
    .on("blur.updateUTubDescription", function () {
      $("#utubDescriptionUpdate").off("keyup.updateUTubDescription");
    });

  // Bind clicking outside the window
  $(window).offAndOn(
    "click.updateUTubDescription",
    function (windowClickEvent) {
      // Ignore clicks on the creation object
      if (
        $(windowClickEvent.target).closest("#updateUTubDescriptionBtn").length
      )
        return;

      if (
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

      // Hide UTub description update fields
      updateUTubDescriptionHideInput(utubID);
    },
  );
}

function removeEventListenersToEscapeUpdateUTubDescription(): void {
  $(window).off(".updateUTubDescription");
  $(document).off(".updateUTubDescription");
}

export function allowHoverOnUTubTitleToCreateDescriptionIfDescEmpty(
  utubID: number,
): void {
  const utubTitle = $("#URLDeckHeader");
  const clickToCreateDesc = $("#URLDeckSubheaderCreateDescription");
  clickToCreateDesc.enableTab();

  utubTitle.offAndOn("mouseenter.createUTubdescription", function () {
    clickToCreateDesc
      .removeClass("opa-0 height-0")
      .addClass("opa-1 height-2rem");
    clickToCreateDesc.offAndOnExact("click.createUTubdescription", function () {
      clickToCreateDesc
        .removeClass("opa-1 height-2rem")
        .addClass("opa-0 height-0 width-0");

      updateUTubDescriptionShowInput(utubID);
      clickToCreateDesc.off("click.createUTubdescription");
    });

    hideCreateUTubDescriptionButtonOnMouseExit();
  });
}

function hideCreateUTubDescriptionButtonOnMouseExit(): void {
  const urlHeaderWrap = $("#URLDeckHeaderWrap");
  const clickToCreateDesc = $("#URLDeckSubheaderCreateDescription");
  urlHeaderWrap.offAndOn("mouseleave.createUTubdescription", function () {
    if (!isHidden($(clickToCreateDesc))) {
      clickToCreateDesc
        .removeClass("opa-1 height-2rem")
        .addClass("opa-0 height-0");
      clickToCreateDesc.off("click.createUTubdescription");
      urlHeaderWrap.off("mouseleave.createUTubdescription");
    }
  });
}

export function removeEventListenersForShowCreateUTubDescIfEmptyDesc(): void {
  const utubTitle = $("#URLDeckHeader");
  utubTitle.off("mouseenter.createUTubdescription");
  const urlHeaderWrap = $("#URLDeckHeaderWrap");
  urlHeaderWrap.off("mouseleave.createUTubdescription");
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

  // Handle hiding the button on mobile when hover events stay after touch
  $("#updateUTubDescriptionBtn").removeClass("visibleBtn");

  // Hide current description and update button
  $("#UTubDescription").hideClass();
  $("#updateUTubDescriptionBtn").hideClass();
  $("#URLDeckSubheader").hideClass();
  $("#URLDeckSubheaderCreateDescription").addClass("width-0");

  removeEventListenersForShowCreateUTubDescIfEmptyDesc();
}

// Hides input fields for updating an exiting UTub's description
export function updateUTubDescriptionHideInput(
  utubID: number | null = null,
): void {
  // Hide update fields
  hideInput("#utubDescriptionUpdate");
  $("#utubDescriptionSubmitBtnUpdate").hideClass();

  // Handle giving mobile devices ability to see button again
  $("#updateUTubDescriptionBtn").addClass("visibleBtn");

  // Remove event listeners for window click and escape/enter keys
  removeEventListenersToEscapeUpdateUTubDescription();

  // Show values and update button
  $("#URLDeckSubheader").showClassNormal();
  $("#updateUTubDescriptionBtn").showClassNormal();

  // Reset errors on hiding of inputs
  resetUpdateUTubDescriptionFailErrors();
  $("#URLDeckSubheaderCreateDescription").removeClass("width-0");
  if (!$("#URLDeckSubheader").text().length && utubID != null) {
    allowHoverOnUTubTitleToCreateDescriptionIfDescEmpty(utubID);
  }
}

// Handles post request and response for updating an existing UTub's description
function updateUTubDescription(utubID: number): void {
  // Skip if identical
  if ($("#URLDeckSubheader").text() === $("#utubDescriptionUpdate").val()) {
    updateUTubDescriptionHideInput(utubID);
    return;
  }

  // Extract data to submit in POST request
  const [postURL, data] = updateUTubDescriptionSetup(utubID);

  const request = ajaxCall("patch", postURL, data);

  // Handle response
  request.done(function (response: UpdateUtubDescResponse, _textStatus, xhr) {
    if (xhr.status === 200) {
      updateUTubDescriptionSuccess(response, utubID);
    }
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    updateUTubDescriptionFail(xhr);
  });
}

// Handles preparation for post request to update an existing UTub
function updateUTubDescriptionSetup(
  utubID: number,
): [string, UpdateUtubDescRequest] {
  const postURL = APP_CONFIG.routes.updateUTubDescription(utubID);

  const updatedDescription = $("#utubDescriptionUpdate").val() as string;
  const data: UpdateUtubDescRequest = { utubDescription: updatedDescription };

  return [postURL, data];
}

// Handle updateion of UTub's description
function updateUTubDescriptionSuccess(
  response: UpdateUtubDescResponse,
  utubID: number,
): void {
  const utubDescription = response.utubDescription ?? "";

  setState({ activeUTubDescription: response.utubDescription });
  const utubDescriptionElem = $("#URLDeckSubheader");
  const originalUTubDescriptionLength = utubDescriptionElem.text().length;

  // Change displayed and updateable value for utub description
  $("#URLDeckSubheader").text(utubDescription);
  $("#utubDescriptionUpdate").val(utubDescription);

  if (utubDescription.length === 0) {
    allowHoverOnUTubTitleToCreateDescriptionIfDescEmpty(utubID);
    $("#UTubDescriptionSubheaderOuterWrap").removeClass("height-2rem");
    $("#UTubDescriptionSubheaderWrap").hideClass();
    $("#URLDeckSubheaderCreateDescription").enableTab();
  } else if (originalUTubDescriptionLength === 0) {
    removeEventListenersForShowCreateUTubDescIfEmptyDesc();
    $("#UTubDescriptionSubheaderOuterWrap").removeClass("height-2rem");
    $("#UTubDescriptionSubheaderWrap").showClassFlex();
    $("#URLDeckSubheaderCreateDescription").disableTab();
  }

  // Hide all inputs on success
  updateUTubDescriptionHideInput();
}

// Handle error response display to user
function updateUTubDescriptionFail(xhr: JQuery.jqXHR): void {
  if (is429Handled(xhr)) return;

  if (!xhr.hasOwnProperty("responseJSON")) {
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
      if (responseJSON.hasOwnProperty("message")) {
        if (responseJSON.hasOwnProperty("errors"))
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
