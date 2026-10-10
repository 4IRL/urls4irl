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
import { getNumOfURLs } from "../utils.js";
import {
  newURLInputRemoveEventListeners,
  newURLInputAddEventListeners,
} from "./cards.js";
import { insertURLCardIntoDeck } from "./card-deck.js";
import { refreshMultiSelectToggleVisibility } from "../bulk-actions/bulk-mode.js";
import {
  ComboboxMode,
  createTagComboboxBlock,
  STAGED_GET_KEY,
  STAGED_RESET_KEY,
} from "../tags/combobox.js";
import {
  TrimMode,
  createParamTrimBlock,
  expandParamTrimBlock,
  readTrimSubmit,
  resetParamTrim,
  syncParamTrim,
  type TrimSubmission,
} from "../trim/param-trim-block.js";
import { checkForStaleDataOn409 } from "./conflict-handler.js";
import {
  clearURLOutcomeBanner,
  showReviveBanner,
  showTrimSavedBanner,
} from "../outcome-banner.js";
import { isATagSelected } from "../../tags/utils.js";
import { temporarilyHideSearchForEdit, showURLSearchIcon } from "../search.js";
import { showURLsEmptyState, hideURLsEmptyState } from "../empty-state.js";
import {
  FORM_CANCEL_TRIGGER,
  FORM_SUBMIT_TRIGGER,
  HOME_FORM,
  URL_PARAMS_TRIMMED_FORM,
  VALIDATION_FORM,
} from "../../../types/metrics-dim-values.js";
import { debug } from "../../../lib/debug.js";

const log = debug("urls:cards");

type CreateUrlRequest = Schema<"CreateURLRequest">;
type CreateUrlResponse = SuccessResponse<"createUrl">;
type CreateUrlError = Schema<"ErrorResponse_URLErrorCodes">;

const CREATE_URL_FIELD_NAMES = ["urlString", "urlTitle"] as const;

type CreateUrlFieldName = (typeof CREATE_URL_FIELD_NAMES)[number];

const TRIM_INPUT_EVENT = "input.createURLTrim";

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
        createURL({ createURLTitleInput, createURLInput, utubID });
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
  resetCreateURLParamTrim();
  resetCreateURLTagCombobox();
  clearURLOutcomeBanner();
  $("#urlBtnCreate").showClassNormal();
  // Restore the multi-select toggle (guarded on the UTub still having URLs).
  refreshMultiSelectToggleVisibility();
}

// Cancels any pending debounced re-parse (via the block's reset callback) and
// removes the mounted trim block. The block is destroyed and rebuilt on every
// open, so it always starts hidden and collapsed; no collapse reset is needed.
function resetCreateURLParamTrim(): void {
  const trimWrap = $("#createURLWrap").find(".urlParamTrimWrap");
  resetParamTrim({ trimWrap });
  trimWrap.remove();
  $("#urlStringCreate").off(TRIM_INPUT_EVENT);
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
  // Param trim mounts first so tab order is title, URL, params, tags, Add URL.
  mountCreateURLParamTrim();
  mountCreateURLTagCombobox(utubID);
  // Keep initial focus on the URL Title input — the combobox must NOT steal focus
  // on form-open (it is a staging-only sub-control of the create form).
  $("#urlTitleCreate").trigger("focus");
  $("#urlBtnCreate").hideClass();
  $("#urlBtnMultiSelect").hideClass();
  temporarilyHideSearchForEdit();
}

// Mounts the opt-in query-parameter trim block between the URL input and the
// tag combobox. Removes any stale block first so re-opening the form does not
// stack duplicates. Never focuses the block: it appears mid-typing and must not
// steal focus from the URL input.
function mountCreateURLParamTrim(): void {
  const createURLInputForm = $("#createURLWrap");
  createURLInputForm.find(".urlParamTrimWrap").remove();
  const trimWrap = createParamTrimBlock({
    mode: TrimMode.CREATE,
    urlCard: null,
  });
  $("#urlSubmitBtnCreate").closest(".flex-row").before(trimWrap);

  // The block owns the debounce, so this handler is a direct call. It uses its
  // own namespace rather than `.createURL`: the URL input's blur handler runs
  // `.off(".createURL")` on that element, which would drop this listener the
  // first time focus moved to a chip. resetCreateURLParamTrim removes it.
  $("#urlStringCreate")
    .off(TRIM_INPUT_EVENT)
    .on(TRIM_INPUT_EVENT, function () {
      syncParamTrim({
        trimWrap,
        rawValue: getInputValue($("#urlStringCreate")),
      });
    });
}

// Mounts the staging-only tag combobox inline in the Create URL form, between
// the URL-string container and the action row, matching the mockup. Removes any
// stale block first so re-opening the form does not stack duplicates.
function mountCreateURLTagCombobox(utubID: number): void {
  const createURLInputForm = $("#createURLWrap");
  createURLInputForm.find(".urlTagComboboxWrap").remove();
  const comboboxWrap = createTagComboboxBlock({
    mode: ComboboxMode.CREATE,
    urlCard: null,
    utubID,
    onSecondEscape: createURLHideInput,
  });
  comboboxWrap.removeClass("hidden");
  // Inject before the action row (the row holding the submit button).
  $("#urlSubmitBtnCreate").closest(".flex-row").before(comboboxWrap);
}

// Prepares post request inputs for addition of a new URL
function createURLSetup({
  createURLTitleInput,
  createURLInput,
  utubID,
}: {
  createURLTitleInput: JQuery;
  createURLInput: JQuery;
  utubID: number;
}): [string, CreateUrlRequest, TrimSubmission | null] {
  // Assemble post request route
  const postURL = APP_CONFIG.routes.createURL(utubID);

  // Assemble submission data
  const urlTitle = getInputValue(createURLTitleInput);

  // Flushes the trim block's pending debounce so a submit within 200ms of the
  // last keystroke trims against the input's current value, not a stale parse.
  const { urlString, trimSubmission } = readTrimSubmit({
    trimWrap: $("#createURLWrap").find(".urlParamTrimWrap"),
    rawValue: getInputValue(createURLInput),
  });

  // Fold any staged tags from the inline combobox into the create request. The
  // getter returns a defensive copy; defaults to [] when the combobox is absent.
  const comboboxWrap = $("#createURLWrap").find(".urlTagComboboxWrap");
  const getStaged = comboboxWrap.data(STAGED_GET_KEY) as
    | (() => string[])
    | undefined;
  const tagStrings = getStaged ? getStaged() : [];

  const data: CreateUrlRequest = {
    urlString,
    urlTitle,
    tagStrings,
  };

  return [postURL, data, trimSubmission];
}

// Handles addition of new URL after user submission
export function createURL({
  createURLTitleInput,
  createURLInput,
  utubID,
}: {
  createURLTitleInput: JQuery;
  createURLInput: JQuery;
  utubID: number;
}): void {
  // Extract data to submit in POST request
  const [postURL, data, trimSubmission] = createURLSetup({
    createURLTitleInput,
    createURLInput,
    utubID,
  });

  if (!isEmptyString(data.urlString) && !isValidURL(data.urlString)) {
    log("createURL rejected by client-side validation", {
      urlStringLength: data.urlString.length,
    });
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
      createURLSuccess({ response, utubID, trimSubmission });
    }
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    resetCreateURLFailErrors();
    createURLFail({ xhr, utubID, trimSubmission });
  });

  request.always(function () {
    // Icon is only shown after 25ms - if <25ms, the timeout and callback function are cleared
    clearTimeout(timeoutId);
    $("#urlCreateDualLoadingRing").removeClass("dual-loading-ring");
  });
}

// Displays changes related to a successful addition of a new URL
function createURLSuccess({
  response,
  utubID,
  trimSubmission,
}: {
  response: CreateUrlResponse;
  utubID: number;
  trimSubmission: TrimSubmission | null;
}): void {
  // Resets and hides the form and combobox (clears staged tags via STAGED_RESET_KEY)
  resetNewURLForm();
  const url = response.URL;
  log("createURL success — appending new card", {
    utubUrlID: url.utubUrlID,
    hiddenByTagFilter: isATagSelected(),
  });
  const utubUrlTagIDs = url.utubUrlTagIDs ?? [];
  // Absent on a payload from before the revive fields existed: treat as a plain add.
  const revivedFromTrash = response.revivedFromTrash ?? false;
  const lostTagCount = response.lostTagCount ?? 0;

  const newUrl: UtubUrlItem = {
    utubUrlID: url.utubUrlID,
    urlString: url.urlString,
    urlTitle: url.urlTitle,
    utubUrlTagIDs,
    canDelete: true,
    // Server-returned timestamp is the sole source of truth for the card's
    // addedAt (never a client-side Date.now()), so the create-time re-sort
    // below places a freshly-created card correctly on the very insert.
    addedAt: url.addedAt,
    // Server-returned adder id (the current user for a create) — drives the
    // "Added by <username> · <date>" attribution badge, resolved to a name
    // from the UTub member list at render time.
    addedByUserID: response.addedByUserID,
  };

  // A revive is announced by the visible outcome banner below (role=status), so
  // the "URL added" live-region write is skipped to avoid a double announcement.
  const newUrlCard = insertURLCardIntoDeck({
    newUrl,
    utubID,
    appliedTags: response.appliedTags ?? [],
    announce: !revivedFromTrash,
  });

  // Last, so the form reset and card selection above (which clear any banner)
  // cannot wipe it. A save with nothing dropped relies on that same reset to
  // clear a stale banner. A revive that also trimmed params folds into the trim
  // banner (which carries Undo) so there is never a second banner.
  if (trimSubmission !== null && trimSubmission.droppedCount > 0) {
    showTrimSavedBanner({
      trimSubmission,
      utubID,
      utubUrlID: url.utubUrlID,
      urlCard: newUrlCard,
      form: URL_PARAMS_TRIMMED_FORM.URL_CREATE,
      revive: revivedFromTrash ? { lostTagCount } : undefined,
    });
  } else if (revivedFromTrash) {
    showReviveBanner({ lostTagCount, utubUrlID: url.utubUrlID });
  }
}

// Displays appropriate prompts and options to user following a failed addition of a new URL
function createURLFail({
  xhr,
  utubID,
  trimSubmission,
}: {
  xhr: JQuery.jqXHR;
  utubID: number;
  trimSubmission: TrimSubmission | null;
}): void {
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
    log("createURL failed with non-JSON response (likely timeout)", {
      status: xhr.status,
    });
    displayCreateUrlFailErrors({
      key: "urlString",
      errorMessage: "Server timed out while validating URL. Try again later.",
    });
    return;
  }
  const responseJSON = xhr.responseJSON as CreateUrlError;
  switch (xhr.status) {
    case 400:
      if (responseJSON.message) {
        if (responseJSON.errors) {
          const errors = responseJSON.errors as Partial<
            Record<string, string[]>
          >;
          // `tagStrings` has no `#tagStringsCreate` input — route its error to
          // the inline combobox message element instead, then strip it before
          // the field-name dispatch loop handles the remaining errors.
          if (errors.tagStrings) {
            displayCreateUrlFailErrors({
              key: "tagStrings",
              errorMessage: errors.tagStrings[0],
              domTarget: $(
                ".urlTagComboboxWrap .urlTagComboboxMsg",
                "#createURLWrap",
              ),
            });
            delete errors.tagStrings;
          }
          createURLShowFormErrors(
            errors as Partial<Record<CreateUrlFieldName, string[]>>,
          );
        } else {
          displayCreateUrlFailErrors({
            key: "urlString",
            errorMessage: responseJSON.message as string,
          });
        }
      }
      break;
    case 409:
      log("createURL conflict (409) — checking for stale local data", {
        utubID,
        conflictMessage: responseJSON.message,
      });
      checkForStaleDataOn409(responseJSON, utubID);
      if ((trimSubmission?.droppedCount ?? 0) > 0) {
        // The collision is caused by the user's trim: say so, and expand the
        // section (same three-part move as the header toggle) so the cause is
        // on screen.
        expandParamTrimBlock({
          trimWrap: $("#createURLWrap").find(".urlParamTrimWrap"),
        });
      }
      displayCreateUrlFailErrors({
        key: "urlString",
        errorMessage:
          (trimSubmission?.droppedCount ?? 0) > 0
            ? APP_CONFIG.strings.URL_TRIM_CONFLICT
            : (responseJSON.message as string),
      });
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
      displayCreateUrlFailErrors({ key, errorMessage });
    }
  }
}

// Show the error message and highlight the input box border red on error of field.
// When `domTarget` is provided (e.g. the combobox message element for tagStrings),
// the error is written there instead of the per-field `#<key>Create-error` element.
function displayCreateUrlFailErrors({
  key,
  errorMessage,
  domTarget,
}: {
  key: string;
  errorMessage: string;
  domTarget?: JQuery;
}): void {
  if (domTarget) {
    domTarget.addClass("warn").text(errorMessage);
    return;
  }
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
  // Clear any stale tagStrings error rendered in the inline combobox message
  // (mirrors the combobox message reset in hideAndResetTagCombobox).
  $("#createURLWrap .urlTagComboboxWrap .urlTagComboboxMsg")
    .text("")
    .removeClass("warn");
}
