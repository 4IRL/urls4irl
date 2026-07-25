import type { Schema, SuccessResponse } from "../../../types/api-helpers.d.ts";
import type { UtubUrlItem } from "../../../types/url.js";

import { $, getInputValue } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { isUtubLockedHandled } from "../../utub-locked.js";
import { emit } from "../../../lib/metrics-client.js";
import { setOpenForm } from "../../../lib/modal-tracking.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";
import { HOME_FORM } from "../../../types/metrics-dim-values.js";
import { getUpdatedURL, handleRejectFromGetURL } from "./get.js";
import {
  setTimeoutAndShowURLCardLoadingIcon,
  clearTimeoutIDAndHideLoadingIcon,
} from "./loading.js";
import {
  disableClickOnSelectedURLCardToHide,
  enableClickOnSelectedURLCardToHide,
} from "./selection.js";
import { enableEditingURLString } from "./utils.js";
import { hideAndResetUpdateURLStringForm } from "./update-string.js";
import { isMobile, isCoarsePointer } from "../../mobile.js";
import { showFieldSavedTick } from "../field-saved-tick.js";
import { getState, setState } from "../../../store/app-store.js";
import { debug } from "../../../lib/debug.js";

const log = debug("urls:cards");

// Per-field in-flight guard for the mobile keep-open path. While the title
// field stays open across a submit, a second submit (double-tap / repeated
// Enter) must be blocked until the fire-and-forget PATCH settles. The entry
// points (click/Enter handlers) live in url-title.ts, so the flag is exposed
// via isURLTitleSubmitInFlight(). Desktop is unaffected (collapse-on-submit
// removes the control), so the guard is only ever set on the panelOpen path.
let titleSubmitInFlight = false;

export function isURLTitleSubmitInFlight(): boolean {
  return titleSubmitInFlight;
}

// Card panel-open predicate: on mobile the string field's morphed full-width
// Cancel bar (.urlStringCancelBigBtnUpdate) is present + unhidden for the whole
// lifetime the consolidated panel is open, so it is the reliable open signal now
// that the just-submitted field's own wrap stays visible. An absent element
// (panel never opened) reads as not-open rather than throwing.
function isCardEditPanelOpen(urlCard: JQuery): boolean {
  const cancelBar = urlCard.find(".urlStringCancelBigBtnUpdate");
  return (
    isCoarsePointer() && cancelBar.length > 0 && !cancelBar.hasClass("hidden")
  );
}

// Clear the title in-flight flag and its accessible-disabled reflection at a
// real exit of updateURLTitle (mirrors the clearTimeoutIDAndHideLoadingIcon
// exit anchors). Harmless no-op on the desktop path where it was never set.
export function clearTitleSubmitInFlight(titleSubmitBtn: JQuery): void {
  titleSubmitInFlight = false;
  titleSubmitBtn.removeAttr("aria-disabled");
}

type UpdateUrlTitleRequest = Schema<"UpdateURLTitleRequest">;
type UpdateUrlTitleResponse = SuccessResponse<"updateUrlTitle">;
type UpdateUrlTitleError = Schema<"ErrorResponse_URLErrorCodes">;

const UPDATE_URL_TITLE_FIELD_NAMES = ["urlTitle"] as const;

type UpdateUrlTitleFieldName = (typeof UPDATE_URL_TITLE_FIELD_NAMES)[number];

function isUpdateUrlTitleFieldName(
  key: string,
): key is UpdateUrlTitleFieldName {
  return (UPDATE_URL_TITLE_FIELD_NAMES as readonly string[]).includes(key);
}

// Shows the update URL title form
export function showUpdateURLTitleForm({
  urlTitleAndShowUpdateIconWrap,
  urlCard,
  suppressSiblingDisable = false,
}: {
  urlTitleAndShowUpdateIconWrap: JQuery;
  urlCard: JQuery;
  suppressSiblingDisable?: boolean;
}): void {
  // Desktop mutual exclusion: close an open URL-string editor first (restoring
  // its option buttons, go-to icon, and morphed Cancel bar) so the two are never
  // open at once. Skipped on the mobile panel path (suppressSiblingDisable),
  // which deliberately keeps both fields open.
  if (
    !suppressSiblingDisable &&
    !urlCard.find(".updateUrlStringWrap").hasClass("hidden")
  ) {
    hideAndResetUpdateURLStringForm({ urlCard });
  }
  emit({ event: UI_EVENTS.UI_URL_TITLE_EDIT_OPEN });
  setOpenForm(HOME_FORM.URL_TITLE_EDIT);
  urlTitleAndShowUpdateIconWrap.hideClass();
  const updateTitleForm = urlTitleAndShowUpdateIconWrap.siblings(
    ".updateUrlTitleWrap",
  );
  updateTitleForm.showClassFlex();
  const titleInput = updateTitleForm.find("input");

  // Handle case where iOS needs a direct focus not in a timeout, even with animation
  if (isMobile()) {
    titleInput.get(0)?.focus();
  } else {
    titleInput.trigger("focus");
  }

  // Prevent hovering on tags from adding padding
  urlCard.find(".tagBadge").removeClass("tagBadgeHoverable");

  disableClickOnSelectedURLCardToHide(urlCard);
}

// Resets and hides the Update URL form upon cancellation or selection of another URL
export function hideAndResetUpdateURLTitleForm({
  urlCard,
  suppressSiblingDisable = false,
  keepOpen = false,
}: {
  urlCard: JQuery;
  suppressSiblingDisable?: boolean;
  keepOpen?: boolean;
}): void {
  // keepOpen (mobile form-model): the title field stays visually open across a
  // per-field submit while the panel is open, so skip the visual collapse and
  // the tag-hover re-enable. Still run the value resync (idempotent) and,
  // unconditionally, the error-state reset so it never lingers.
  if (!keepOpen) {
    urlCard.find(".updateUrlTitleWrap").hideClass();
    urlCard.find(".urlTitleAndUpdateIconWrap").showClassFlex();
  }
  urlCard.find(".urlTitleUpdate").val(urlCard.find(".urlTitle").text());

  // Enable hovering on tags for deletion
  if (!keepOpen) urlCard.find(".tagBadge").addClass("tagBadgeHoverable");

  resetUpdateURLTitleFailErrors(urlCard);
  if (!suppressSiblingDisable) enableEditingURLString(urlCard);
  // Panel-aware: when the sibling (string) form is still open on mobile, do NOT
  // re-arm the card's click.deselectURL handler — a tap into the still-open
  // sibling input would otherwise deselect the card and discard the in-progress
  // edit. The non-suppressed path (single-field / desktop) re-arms as before.
  const selected = urlCard.attr("urlSelected");
  if (
    !suppressSiblingDisable &&
    typeof selected === "string" &&
    selected.toLowerCase() === "true"
  ) {
    enableClickOnSelectedURLCardToHide(urlCard);
  }
}

// Prepares post request inputs for update of a URL
function updateURLTitleSetup(
  urlTitleInput: JQuery,
  utubID: number,
  utubUrlID: number,
): [string, UpdateUrlTitleRequest] {
  const patchURL = APP_CONFIG.routes.updateURLTitle(utubID, utubUrlID);

  const updatedURLTitle = getInputValue(urlTitleInput);

  const data: UpdateUrlTitleRequest = { urlTitle: updatedURLTitle };

  return [patchURL, data];
}

// Handles update of an existing URL
export async function updateURLTitle(
  urlTitleInput: JQuery,
  urlCard: JQuery,
  utubID: number,
): Promise<void> {
  // Extract data to submit in POST request
  const utubUrlID = parseInt(urlCard.attr("utuburlid") as string);
  const timeoutID: number = setTimeoutAndShowURLCardLoadingIcon(urlCard);
  const panelOpen = isCardEditPanelOpen(urlCard);
  const titleSubmitBtn = urlCard.find(".urlTitleSubmitBtnUpdate");
  if (panelOpen) {
    // Accessible in-flight guard: mark the submit control aria-disabled (not
    // native disabled, which drops focus) so a second overlapping submit is
    // blocked by the entry-point checks in url-title.ts until this settles.
    titleSubmitInFlight = true;
    titleSubmitBtn.attr("aria-disabled", "true");
  }
  try {
    await getUpdatedURL(utubID, utubUrlID, urlCard);

    if (urlTitleInput.val() === urlCard.find(".urlTitle").text()) {
      log("updateURLTitle skipped — value unchanged", { utubUrlID });
      // Panel-aware: on mobile the string form can still be open alongside this
      // title field. Suppress the sibling restore so we don't re-arm the card
      // deselect handler (and re-enable the string's edit affordance) while the
      // string edit is still in progress. keepOpen keeps this field visually
      // open (no tick — value unchanged), and re-registers the open form so a
      // later pagehide doesn't misreport UI_FORM_CANCEL.
      const stringFormStillOpen = !urlCard
        .find(".updateUrlStringWrap")
        .hasClass("hidden");
      hideAndResetUpdateURLTitleForm({
        urlCard,
        suppressSiblingDisable: isCoarsePointer() && stringFormStillOpen,
        keepOpen: panelOpen,
      });
      if (panelOpen) setOpenForm(HOME_FORM.URL_TITLE_EDIT);
      clearTitleSubmitInFlight(titleSubmitBtn);
      clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
      return;
    }

    const [patchURL, data] = updateURLTitleSetup(
      urlTitleInput,
      utubID,
      utubUrlID,
    );

    const request = ajaxCall("patch", patchURL, data);

    // Handle response
    request.done(function (
      response: UpdateUrlTitleResponse,
      _: JQuery.Ajax.SuccessTextStatus,
      xhr: JQuery.jqXHR,
    ) {
      if (xhr.status === 200) {
        resetUpdateURLTitleFailErrors(urlCard);
        if ("URL" in response && "urlTitle" in response.URL)
          updateURLTitleSuccess(response, urlCard);
      }
    });

    request.fail(function (xhr: JQuery.jqXHR) {
      updateURLTitleFail(xhr, urlCard);
    });

    request.always(function () {
      clearTitleSubmitInFlight(titleSubmitBtn);
      clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
    });
  } catch (error) {
    log("updateURLTitle aborted — pre-flight URL fetch rejected", {
      utubUrlID,
    });
    clearTitleSubmitInFlight(titleSubmitBtn);
    clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
    handleRejectFromGetURL(error as JQuery.jqXHR, urlCard, {
      showError: true,
      message: "Another user has deleted this URL",
    });
  }
}

// Displays changes related to a successful update of a URL
function updateURLTitleSuccess(
  response: UpdateUrlTitleResponse,
  urlCard: JQuery,
): void {
  // Extract response data
  const updatedURLTitle = response.URL.urlTitle;

  setState({
    urls: getState().urls.map((existingUrl: UtubUrlItem) =>
      existingUrl.utubUrlID === response.URL.utubUrlID
        ? {
            ...existingUrl,
            urlString: response.URL.urlString,
            urlTitle: response.URL.urlTitle,
            utubUrlTagIDs: response.URL.urlTags.map(
              (urlTag) => urlTag.utubTagID,
            ),
          }
        : existingUrl,
    ),
  });

  // Update URL body with latest published data
  urlCard.find(".urlTitle").text(updatedURLTitle);
  // Panel-aware: on mobile the string form can still be open alongside this
  // title field. Suppress the sibling restore so submitting the title does not
  // re-arm the card deselect handler (which would discard an in-progress string
  // edit) while the string form is still open.
  const panelOpen = isCardEditPanelOpen(urlCard);
  const stringFormStillOpen = !urlCard
    .find(".updateUrlStringWrap")
    .hasClass("hidden");
  hideAndResetUpdateURLTitleForm({
    urlCard,
    suppressSiblingDisable: isCoarsePointer() && stringFormStillOpen,
    keepOpen: panelOpen,
  });
  // Mobile form model: keep the field open, re-register the tracked open form
  // (so a later pagehide doesn't misreport UI_FORM_CANCEL), and flash a
  // transient "Saved ✓" beside the still-open field. updateURLTitleSuccess is
  // only reached on a genuine 200 for a changed value, so no no-op guard needed.
  if (panelOpen) {
    setOpenForm(HOME_FORM.URL_TITLE_EDIT);
    showFieldSavedTick({
      tick: urlCard.find(".updateUrlTitleWrap .field-saved-tick"),
      announce: $("#fieldSavedAnnouncement"),
      label: APP_CONFIG.strings.FIELD_SAVED_LABEL_URL_TITLE,
    });
  }
}

// Displays appropriate prompts and options to user following a failed update of a URL
function updateURLTitleFail(xhr: JQuery.jqXHR, urlCard: JQuery): void {
  if (is429Handled(xhr)) return;
  if (isUtubLockedHandled(xhr)) return;

  if (!("responseJSON" in xhr)) {
    if (
      xhr.status === 403 &&
      xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      // Handle invalid CSRF token error response
      $("body").html(xhr.responseText);
      return;
    }
    window.location.assign(APP_CONFIG.routes.errorPage);
    return;
  }

  switch (xhr.status) {
    case 400: {
      const responseJSON = xhr.responseJSON as UpdateUrlTitleError;
      if (responseJSON.errors) {
        updateURLTitleFailErrors(
          responseJSON.errors as Partial<
            Record<UpdateUrlTitleFieldName, string[]>
          >,
          urlCard,
        );
        break;
      }
    }
    case 403:
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}

function updateURLTitleFailErrors(
  errors: Partial<Record<UpdateUrlTitleFieldName, string[]>>,
  urlCard: JQuery,
): void {
  for (const errorFieldName in errors) {
    if (isUpdateUrlTitleFieldName(errorFieldName)) {
      const errorMessage = errors[errorFieldName]![0];
      displayUpdateURLTitleErrors(errorFieldName, errorMessage, urlCard);
      return;
    }
  }
}

function displayUpdateURLTitleErrors(
  key: string,
  errorMessage: string,
  urlCard: JQuery,
): void {
  urlCard
    .find("." + key + "Update-error")
    .addClass("visible")
    .text(errorMessage);
  urlCard.find("." + key + "Update").addClass("invalid-field");
}

function resetUpdateURLTitleFailErrors(urlCard: JQuery): void {
  urlCard.find(".urlTitleUpdate").removeClass("invalid-field");
  urlCard.find(".urlTitleUpdate-error").removeClass("visible");
}
