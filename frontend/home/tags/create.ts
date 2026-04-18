import type { Schema, SuccessResponse } from "../../types/api-helpers.d.ts";
import type { UtubTag } from "../../types/url.js";

import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { $, getInputValue } from "../../lib/globals.js";
import { getState, setState } from "../../store/app-store.js";
import { getNumOfUTubs } from "../utubs/utils.js";
import { buildTagFilterInDeck } from "./tags.js";

type AddTagRequest = Schema<"AddTagRequest">;
type CreateUtubTagResponse = SuccessResponse<"createUtubTag">;

export function setupOpenCreateUTubTagEventListeners(utubID: number): void {
  const utubTagBtnCreate = $("#utubTagBtnCreate");

  // Add tag to UTub
  utubTagBtnCreate.offAndOn("click.createUTubTag", function () {
    createUTubTagShowInput(utubID);
  });
}

// Clear tag input form
export function resetNewUTubTagForm(): void {
  $("#utubTagCreate").val("");
}

function setupCreateUTubTagEventListeners(utubID: number): void {
  const utubTagSubmitBtnCreate = $("#utubTagSubmitBtnCreate");
  const utubTagCancelBtnCreate = $("#utubTagCancelBtnCreate");

  utubTagSubmitBtnCreate.offAndOnExact(
    "click.createUTubTagSubmit",
    function () {
      createUTubTag(utubID);
    },
  );

  utubTagCancelBtnCreate.offAndOnExact(
    "click.createUTubTagEscape",
    function () {
      createUTubTagHideInput();
    },
  );

  const utubTagInput = $("#utubTagCreate");
  utubTagInput.offAndOn("focus.createUTubTagSubmitEscape", function () {
    bindCreateUTubTagFocusEventListeners(utubID, utubTagInput);
  });
  utubTagInput.offAndOn("blur.createUTubTagSubmitSubmitEscape", function () {
    unbindCreateUTubTagFocusEventListeners(utubTagInput);
  });
}

export function removeCreateUTubTagEventListeners(): void {
  $("#utubTagCreate").off(".createUTubTagSubmitEscape");
}

function bindCreateUTubTagFocusEventListeners(
  utubID: number,
  utubTagInput: JQuery,
): void {
  // Allow closing by pressing escape key
  utubTagInput.offAndOn(
    "keydown.createUTubTagSubmitEscape",
    function (event: JQuery.TriggeredEvent) {
      if ((event.originalEvent as KeyboardEvent).repeat) return;
      switch (event.key) {
        case KEYS.ENTER:
          // Handle enter key pressed
          createUTubTag(utubID);
          break;
        case KEYS.ESCAPE:
          // Handle escape  key pressed
          createUTubTagHideInput();
          break;
        default:
        /* no-op */
      }
    },
  );
}

function unbindCreateUTubTagFocusEventListeners(utubTagInput: JQuery): void {
  utubTagInput.off(".createUTubTagSubmitEscape");
}

function createUTubTagShowInput(utubID: number): void {
  $("#createUTubTagWrap").showClassFlex();
  $("#listTags").hideClass();
  $("#utubTagStandardBtns").hideClass();
  setupCreateUTubTagEventListeners(utubID);
  $("#utubTagCreate").trigger("focus");
}

export function createUTubTagHideInput(): void {
  $("#createUTubTagWrap").hideClass();
  $("#listTags").showClassNormal();
  if (getNumOfUTubs() !== 0) $("#utubTagStandardBtns").showClassFlex();
  removeCreateUTubTagEventListeners();
  resetCreateUTubTagFailErrors();
  resetNewUTubTagForm();
}

function createUTubTagSetup(utubID: number): [string, AddTagRequest] {
  const postURL = APP_CONFIG.routes.createUTubTag(utubID);

  const tagString = getInputValue("#utubTagCreate");
  const data: AddTagRequest = { tagString };

  return [postURL, data];
}

function createUTubTag(utubID: number): void {
  // Extract data to submit in POST request
  const [postURL, data] = createUTubTagSetup(utubID);
  resetCreateUTubTagFailErrors();

  const request = ajaxCall("post", postURL, data);

  // Handle response
  request.done(function (
    response: CreateUtubTagResponse,
    _textStatus: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    if (xhr.status === 200) {
      createUTubTagSuccess(response, utubID);
    }
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    createUTubTagFail(xhr);
  });
}

function createUTubTagSuccess(
  response: CreateUtubTagResponse,
  utubID: number,
): void {
  resetNewUTubTagForm();

  const newTag: UtubTag = {
    id: response.utubTag.utubTagID,
    tagString: response.utubTag.tagString,
    tagApplied: response.tagCountsInUtub,
  };
  setState({ tags: [...getState().tags, newTag] });

  // Create and append the new tag in the tag deck
  $("#listTags").append(
    buildTagFilterInDeck(
      utubID,
      response.utubTag.utubTagID,
      response.utubTag.tagString,
    ),
  );

  // Show unselect all and update buttons if not already shown
  $("#unselectAllTagFilters").showClassNormal();
  $("#utubTagBtnUpdateAllOpen").showClassNormal();

  createUTubTagHideInput();
}

function createUTubTagFail(xhr: JQuery.jqXHR): void {
  if (is429Handled(xhr)) return;

  if (!("responseJSON" in xhr)) {
    if (
      xhr.status === 403 &&
      xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      // Handle invalid CSRF token error response
      // Anti-pattern kept for consistency with 14 CSRF 403 callers in frontend/home/ (members/, utubs/, urls/, tags/).
      $("body").html(xhr.responseText);
      return;
    }
    window.location.assign(APP_CONFIG.routes.errorPage);
    return;
  }

  switch (xhr.status) {
    case 400: {
      const responseJSON = xhr.responseJSON as
        | { errors?: Record<string, string[]>; message?: string }
        | undefined;
      const errors = responseJSON?.errors;
      const message = responseJSON?.message;
      if (errors) {
        // Show form errors
        createUTubTagFailErrors(errors);
        break;
      } else if (message) {
        // Show message
        displayCreateUTubTagFailErrors("utubTag", message);
        break;
      }
      // Intentional fall-through: an unexpected 400 body shape (neither
      // `errors` nor `message`) is treated as an unrecoverable error and
      // falls through to the default error-page redirect below.
    }
    // Intentional fall-through: 403 falls through to default error redirect
    case 403:
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}

function createUTubTagFailErrors(errors: Record<string, string[]>): void {
  for (const key in errors) {
    if (key !== "tagString") continue;
    const errorMessage = errors[key][0];
    displayCreateUTubTagFailErrors(key, errorMessage);
    return;
  }
}

function displayCreateUTubTagFailErrors(
  _fieldName: "tagString" | "utubTag",
  message: string,
): void {
  $("#utubTagCreate-error").addClass("visible").text(message);
  $("#utubTagCreate").addClass("invalid-field");
}

export function resetCreateUTubTagFailErrors(): void {
  $("#utubTagCreate-error").removeClass("visible");
  $("#utubTagCreate").removeClass("invalid-field");
}
