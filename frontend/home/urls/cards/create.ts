import type { Schema, SuccessResponse } from "../../../types/api-helpers.d.ts";
import type { UtubUrlItem } from "../../../types/url.js";

import { $, getInputValue } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { KEYS, SHOW_LOADING_ICON_AFTER_MS } from "../../../lib/constants.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { emit } from "../../../lib/metrics-client.js";
import { clearOpenForm, setOpenForm } from "../../../lib/modal-tracking.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";
import { isEmptyString } from "./utils.js";
import { isValidURL } from "../validation.js";
import { getNumOfVisibleURLs, getNumOfURLs } from "../utils.js";
import {
  createURLBlock,
  newURLInputRemoveEventListeners,
  newURLInputAddEventListeners,
} from "./cards.js";
import { selectURLCard } from "./selection.js";
import { updateColorOfFollowingURLCardsAfterURLCreated } from "./utils.js";
import { createTagComboboxBlock, STAGED_RESET_KEY } from "../tags/combobox.js";
import { checkForStaleDataOn409 } from "./conflict-handler.js";
import { isATagSelected } from "../../tags/utils.js";
import { getState, setState } from "../../../store/app-store.js";
import {
  closeURLSearchAndEraseInput,
  temporarilyHideSearchForEdit,
  showURLSearchIcon,
} from "../search.js";
import { showURLsEmptyState, hideURLsEmptyState } from "../empty-state.js";
import {
  FORM_CANCEL_TRIGGER,
  FORM_SUBMIT_TRIGGER,
  HOME_FORM,
  VALIDATION_FORM,
} from "../../../types/metrics-dim-values.js";

type CreateUrlRequest = Schema<"CreateURLRequest">;
type CreateUrlResponse = SuccessResponse<"createUrl">;
type CreateUrlError = Schema<"ErrorResponse_URLErrorCodes">;

const CREATE_URL_FIELD_NAMES = ["urlString", "urlTitle"] as const;

type CreateUrlFieldName = (typeof CREATE_URL_FIELD_NAMES)[number];

function isCreateUrlFieldName(key: string): key is CreateUrlFieldName {
  return (CREATE_URL_FIELD_NAMES as readonly string[]).includes(key);
}

export function bindCreateURLFocusEventListeners(
  inputElem: JQuery,
  createURLInput: JQuery,
  createURLTitleInput: JQuery,
  utubID: number,
): void {
  $(inputElem).on("keydown.createURL", function (event: JQuery.TriggeredEvent) {
    if ((event.originalEvent as KeyboardEvent).repeat) return;
    switch (event.key) {
      case KEYS.ENTER:
        // Handle enter key pressed
        emit({
          event: UI_EVENTS.UI_FORM_SUBMIT,
          form: HOME_FORM.URL_CREATE,
          trigger: FORM_SUBMIT_TRIGGER.ENTER_KEY,
        });
        clearOpenForm();
        createURL(createURLTitleInput, createURLInput, utubID);
        break;
      case KEYS.ESCAPE:
        // Handle escape key pressed
        emit({
          event: UI_EVENTS.UI_FORM_CANCEL,
          form: HOME_FORM.URL_CREATE,
          trigger: FORM_CANCEL_TRIGGER.ESCAPE_KEY,
        });
        clearOpenForm();
        createURLHideInput();
        break;
      default:
      /* no-op */
    }
  });
}

export function unbindCreateURLFocusEventListeners(inputElem: JQuery): void {
  $(inputElem).off(".createURL");
}

// Clear new URL Form
export function resetNewURLForm(): void {
  $("#urlTitleCreate").val("");
  $("#urlStringCreate").val("");
  $("#createURLWrap").hideClass();
  newURLInputRemoveEventListeners();
  resetCreateURLTagCombobox();
  $("#urlBtnCreate").showClassNormal();
}

// Clears the staged-tags backing state (via the combobox's exposed reset
// callback) and removes the mounted block from the create form.
function resetCreateURLTagCombobox(): void {
  const comboboxWrap = $("#createURLWrap").find(".urlTagComboboxWrap");
  (comboboxWrap.data(STAGED_RESET_KEY) as (() => void) | undefined)?.();
  comboboxWrap.remove();
}
// Displays new URL input prompt
export function createURLHideInput(): void {
  resetNewURLForm();
  if (!getNumOfURLs()) {
    showURLsEmptyState();
  } else {
    showURLSearchIcon();
  }
}

// Hides new URL input prompt
export function createURLShowInput(utubID: number): void {
  emit({ event: UI_EVENTS.UI_URL_CREATE_OPEN });
  setOpenForm(HOME_FORM.URL_CREATE);
  if (!getNumOfURLs()) {
    hideURLsEmptyState();
  }
  const createURLInputForm = $("#createURLWrap");
  createURLInputForm.showClassFlex();
  newURLInputAddEventListeners(createURLInputForm, utubID);
  mountCreateURLTagCombobox(utubID);
  // Keep initial focus on the URL Title input — the combobox must NOT steal focus
  // on form-open (it is a staging-only sub-control of the create form).
  $("#urlTitleCreate").trigger("focus");
  $("#urlBtnCreate").hideClass();
  temporarilyHideSearchForEdit();
}

// Mounts the staging-only tag combobox inline in the Create URL form, between
// the URL-string container and the action row, matching the mockup. Removes any
// stale block first so re-opening the form does not stack duplicates.
function mountCreateURLTagCombobox(utubID: number): void {
  const createURLInputForm = $("#createURLWrap");
  createURLInputForm.find(".urlTagComboboxWrap").remove();
  const comboboxWrap = createTagComboboxBlock({
    mode: "create",
    urlCard: null,
    utubID,
    onSecondEscape: createURLHideInput,
  });
  comboboxWrap.removeClass("hidden");
  // Inject before the action row (the row holding the submit button).
  $("#urlSubmitBtnCreate").closest(".flex-row").before(comboboxWrap);
}

// Prepares post request inputs for addition of a new URL
function createURLSetup(
  createURLTitleInput: JQuery,
  createURLInput: JQuery,
  utubID: number,
): [string, CreateUrlRequest] {
  // Assemble post request route
  const postURL = APP_CONFIG.routes.createURL(utubID);

  // Assemble submission data
  const urlTitle = getInputValue(createURLTitleInput);
  const urlString = getInputValue(createURLInput);
  const data: CreateUrlRequest = {
    urlString,
    urlTitle,
  };

  return [postURL, data];
}

// Handles addition of new URL after user submission
export function createURL(
  createURLTitleInput: JQuery,
  createURLInput: JQuery,
  utubID: number,
): void {
  // Extract data to submit in POST request
  const [postURL, data] = createURLSetup(
    createURLTitleInput,
    createURLInput,
    utubID,
  );

  if (!isEmptyString(data.urlString) && !isValidURL(data.urlString)) {
    emit({
      event: UI_EVENTS.UI_VALIDATION_ERROR,
      form: VALIDATION_FORM.URL_CREATE,
    });
    createURLShowFormErrors({
      urlString: [APP_CONFIG.strings.INVALID_URL],
    });
    return;
  }

  // Show loading icon when creating a URL
  const timeoutId = setTimeout(function () {
    $("#urlCreateDualLoadingRing").addClass("dual-loading-ring");
  }, SHOW_LOADING_ICON_AFTER_MS);
  const request = ajaxCall("post", postURL, data, 35000);

  request.done(function (
    response: CreateUrlResponse,
    _: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    if (xhr.status === 200) {
      createURLSuccess(response, utubID);
    }
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    resetCreateURLFailErrors();
    createURLFail(xhr, utubID);
  });

  request.always(function () {
    // Icon is only shown after 25ms - if <25ms, the timeout and callback function are cleared
    clearTimeout(timeoutId);
    $("#urlCreateDualLoadingRing").removeClass("dual-loading-ring");
  });
}

// Displays changes related to a successful addition of a new URL
function createURLSuccess(response: CreateUrlResponse, utubID: number): void {
  resetNewURLForm();
  const url = response.URL;

  const newUrl: UtubUrlItem = {
    utubUrlID: url.utubUrlID,
    urlString: url.urlString,
    urlTitle: url.urlTitle,
    utubUrlTagIDs: [],
    canDelete: true,
  };

  setState({
    urls: [...getState().urls, newUrl],
  });

  // DP 09/17 need to implement ability to addTagtoURL interstitially before createURL is completed
  const currentNumOfURLs = getNumOfVisibleURLs();
  const newUrlCard = createURLBlock(
    newUrl,
    [], // Mimics an empty array of tags to match against
    utubID,
  ).addClass("even");

  newUrlCard.insertAfter($("#createURLWrap"));

  if (currentNumOfURLs !== 0) {
    updateColorOfFollowingURLCardsAfterURLCreated();
  }

  // Only select the URL when no tags are selected
  // If a tag is selected, new URLs have no Tags associated, so they should be hidden after added
  if (isATagSelected()) {
    newUrlCard.attr({ filterable: false });
  } else {
    selectURLCard(newUrlCard);
  }

  closeURLSearchAndEraseInput();
  showURLSearchIcon();
}

// Displays appropriate prompts and options to user following a failed addition of a new URL
function createURLFail(xhr: JQuery.jqXHR, utubID: number): void {
  if (is429Handled(xhr)) return;

  if (!("responseJSON" in xhr)) {
    if (
      xhr.status === 403 &&
      xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      // Handle invalid CSRF token error response
      $("body").html(xhr.responseText);
      return;
    }
    displayCreateUrlFailErrors(
      "urlString",
      "Server timed out while validating URL. Try again later.",
    );
    return;
  }
  const responseJSON = xhr.responseJSON as CreateUrlError;
  switch (xhr.status) {
    case 400:
      if (responseJSON.message) {
        if (responseJSON.errors) {
          createURLShowFormErrors(
            responseJSON.errors as Partial<
              Record<CreateUrlFieldName, string[]>
            >,
          );
        } else {
          displayCreateUrlFailErrors(
            "urlString",
            responseJSON.message as string,
          );
        }
      }
      break;
    case 409:
      checkForStaleDataOn409(responseJSON, utubID);
      displayCreateUrlFailErrors("urlString", responseJSON.message as string);
      break;
    case 403:
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}

function createURLShowFormErrors(
  errors: Partial<Record<CreateUrlFieldName, string[]>>,
): void {
  for (const key in errors) {
    if (isCreateUrlFieldName(key)) {
      const errorMessage = errors[key]![0];
      displayCreateUrlFailErrors(key, errorMessage);
    }
  }
}

// Show the error message and highlight the input box border red on error of field
function displayCreateUrlFailErrors(key: string, errorMessage: string): void {
  $("#" + key + "Create-error")
    .addClass("visible")
    .text(errorMessage);
  $("#" + key + "Create").addClass("invalid-field");
}

export function resetCreateURLFailErrors(): void {
  const newUrlFields = ["urlString", "urlTitle"];
  newUrlFields.forEach((fieldName) => {
    $("#" + fieldName + "Create").removeClass("invalid-field");
    $("#" + fieldName + "Create-error").removeClass("visible");
  });
}
