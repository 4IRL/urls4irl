import type { Schema, SuccessResponse } from "../../../types/api-helpers.d.ts";
import type { UtubUrlItem } from "../../../types/url.js";

import { $, bootstrap, getInputValue } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { isUtubLockedHandled } from "../../utub-locked.js";
import {
  enableTabbableChildElements,
  disableTabbableChildElements,
} from "../../../lib/jquery-plugins.js";
import { emit } from "../../../lib/metrics-client.js";
import { setOpenForm } from "../../../lib/modal-tracking.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";
import { enableEditingURLTitle, isEmptyString } from "./utils.js";
import { hideAndResetUpdateURLTitleForm } from "./update-title.js";
import { isValidURL } from "../validation.js";
import { isURLSearchActive, getActiveTagCount } from "../url-context.js";
import { getUpdatedURL, handleRejectFromGetURL } from "./get.js";
import {
  setTimeoutAndShowURLCardLoadingIcon,
  clearTimeoutIDAndHideLoadingIcon,
} from "./loading.js";
import { accessLink } from "./access.js";
import { copyURLString } from "./copy.js";
import {
  disableClickOnSelectedURLCardToHide,
  enableClickOnSelectedURLCardToHide,
} from "./selection.js";
import { isMobile, isCoarsePointer } from "../../mobile.js";
import { showFieldSavedTick } from "../field-saved-tick.js";
import { highlightInput } from "../../btns-forms.js";
import {
  disableTagRemovalInURLCard,
  enableTagRemovalInURLCard,
} from "../tags/tags.js";
import {
  createEditURLIcon,
  bindURLStringEditClickHandler,
} from "./options/edit-string-btn.js";
import { closeURLEditPanel } from "./update-url-panel.js";
import { checkForStaleDataOn409 } from "./conflict-handler.js";
import { getState, setState } from "../../../store/app-store.js";
import {
  HOME_FORM,
  SEARCH_ACTIVE,
  URL_ACCESS_TRIGGER,
  VALIDATION_FORM,
} from "../../../types/metrics-dim-values.js";
import { debug } from "../../../lib/debug.js";

const log = debug("urls:cards");

// Per-field in-flight guard for the mobile keep-open path. While the string
// field stays open across a submit, a second submit (double-tap / repeated
// Enter) must be blocked until the fire-and-forget PATCH settles. The entry
// points (click/Enter handlers) live in url-string.ts, so the flag is exposed
// via isURLStringSubmitInFlight(). Desktop is unaffected (collapse-on-submit
// removes the control), so the guard is only ever set on the panelOpen path.
let stringSubmitInFlight = false;

export function isURLStringSubmitInFlight(): boolean {
  return stringSubmitInFlight;
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

// Clear the string in-flight flag and its accessible-disabled reflection at a
// real exit of updateURL (mirrors the clearTimeoutIDAndHideLoadingIcon exit
// anchors). Harmless no-op on the desktop path where it was never set.
export function clearStringSubmitInFlight(stringSubmitBtn: JQuery): void {
  stringSubmitInFlight = false;
  stringSubmitBtn.removeAttr("aria-disabled");
}

type UpdateUrlStringRequest = Schema<"UpdateURLStringRequest">;
type UpdateUrlStringResponse = SuccessResponse<"updateUrl">;
type UpdateUrlStringError = Schema<"ErrorResponse_URLErrorCodes">;

const UPDATE_URL_STRING_FIELD_NAMES = ["urlString"] as const;

type UpdateUrlStringFieldName = (typeof UPDATE_URL_STRING_FIELD_NAMES)[number];

function isUpdateUrlStringFieldName(
  key: string,
): key is UpdateUrlStringFieldName {
  return (UPDATE_URL_STRING_FIELD_NAMES as readonly string[]).includes(key);
}

// Shows update URL inputs
export function showUpdateURLStringForm({
  urlCard,
  urlStringBtnUpdate,
  suppressSiblingDisable = false,
}: {
  urlCard: JQuery;
  urlStringBtnUpdate: JQuery;
  suppressSiblingDisable?: boolean;
}): void {
  // Desktop mutual exclusion: close an open URL-title editor first (restoring
  // the title pencil affordance) so the two are never open at once. Skipped on
  // the mobile panel path (suppressSiblingDisable), which deliberately keeps
  // both fields open.
  if (
    !suppressSiblingDisable &&
    !urlCard.find(".updateUrlTitleWrap").hasClass("hidden")
  ) {
    hideAndResetUpdateURLTitleForm({ urlCard });
  }
  emit({ event: UI_EVENTS.UI_URL_STRING_EDIT_OPEN });
  setOpenForm(HOME_FORM.URL_STRING_EDIT);
  urlCard.find(".urlString").hideClass();
  const updateURLStringWrap = urlCard.find(".updateUrlStringWrap");
  enableTabbableChildElements(updateURLStringWrap);
  updateURLStringWrap.showClassFlex();

  // Handle case where iOS needs a direct focus not in a timeout, even with animation
  if (isMobile()) {
    updateURLStringWrap.find("input").focus();
  }

  // Set timeout in case user pressed enter to avoid propagation through to URL string update
  setTimeout(function () {
    highlightInput(updateURLStringWrap.find("input"));
  }, 100);

  // Disable URL Buttons as URL is being edited
  urlCard.find(".urlBtnAccess").hideClass();
  urlCard.find(".urlTagBtnCreate").hideClass();
  urlCard.find(".urlBtnDelete").hideClass();
  urlCard.find(".urlBtnCopy").hideClass();

  // Disable Go To URL Icon
  urlCard.find(".goToUrlIcon").removeClass("visible-flex").addClass("hidden");

  // Prevent hovering on tags from adding padding
  urlCard.find(".tagBadge").removeClass("tagBadgeHoverable");

  const tooltipElement = urlStringBtnUpdate.get(0);
  const tooltip = tooltipElement
    ? bootstrap.Tooltip.getInstance(tooltipElement)
    : null;
  if (tooltip) {
    tooltip.hide();
    tooltip.disable();
  }

  // Update URL Button text to exit editing
  urlStringBtnUpdate
    .removeClass("urlStringBtnUpdate fourty-p-width")
    .addClass("urlStringCancelBigBtnUpdate")
    .text(isCoarsePointer() ? "Close" : "Cancel")
    .offAndOnExact("click", function () {
      if (isCoarsePointer()) {
        // Panel is open on mobile — closing "Close" closes both the title and
        // string fields together and returns focus to the trigger button.
        closeURLEditPanel(urlCard);
      } else {
        hideAndResetUpdateURLStringForm({ urlCard });
        if (tooltip) tooltip.enable();
      }
    });

  disableTagRemovalInURLCard(urlCard);
  disableClickOnSelectedURLCardToHide(urlCard);
}

// Resets and hides the Update URL form upon cancellation or selection of another URL
export function hideAndResetUpdateURLStringForm({
  urlCard,
  suppressSiblingDisable = false,
  keepOpen = false,
}: {
  urlCard: JQuery;
  suppressSiblingDisable?: boolean;
  keepOpen?: boolean;
}): void {
  // keepOpen (mobile form-model): the string field stays visually open across a
  // per-field submit while the panel is open. Skip the entire visual restore
  // (wrap hide, URL re-show, Cancel-bar → edit-button morph, action buttons,
  // go-to-URL icon, tag-hover/tag-removal re-enable) so the field stays in its
  // "still editing" state; keeping .urlStringCancelBigBtnUpdate present/unhidden
  // also preserves the card panel-open signal. Still run the input resync
  // (idempotent) and, unconditionally, the error-state reset so it never lingers.
  const updateURLStringWrap = urlCard.find(".updateUrlStringWrap");
  if (!keepOpen) {
    // Toggle input form and display of URL
    updateURLStringWrap.hideClass();
    disableTabbableChildElements(updateURLStringWrap);
    urlCard.find(".urlString").showClassNormal();
  }

  // Update the input with current value of url string element
  const urlStringElem = urlCard.find(".urlString");
  urlCard.find(".urlStringUpdate").val(urlStringElem.attr("href") as string);

  if (!keepOpen) {
    // Make the Update URL button now allow updating again
    const urlStringBtnUpdate = urlCard.find(".urlStringCancelBigBtnUpdate");
    urlStringBtnUpdate
      .removeClass("urlStringCancelBigBtnUpdate")
      .addClass("urlStringBtnUpdate")
      .text("")
      .append(createEditURLIcon());

    // Rebind via the shared helper so the mobile (panel-open) branch survives an
    // open/close cycle — a bare showUpdateURLStringForm rebind here would revert
    // the button to the desktop-only path after the first close.
    bindURLStringEditClickHandler({ urlCard, urlStringBtnUpdate });

    // For tablets or in case of resize, change some of the sizing
    urlStringBtnUpdate.addClass("fourty-p-width");

    // Enable URL Buttons
    urlCard.find(".urlBtnAccess").showClassFlex();
    urlCard.find(".urlTagBtnCreate").showClassFlex();
    urlCard.find(".urlBtnDelete").showClassFlex();
    urlCard.find(".urlBtnCopy").showClassFlex();
    if (!suppressSiblingDisable) enableEditingURLTitle(urlCard);

    // Enable Go To URL Icon
    const selected = urlCard.attr("urlSelected");
    if (typeof selected === "string" && selected.toLowerCase() === "true") {
      urlCard
        .find(".goToUrlIcon")
        .removeClass("hidden")
        .addClass("visible-flex");
    }

    // Enable hovering on tags for deletion
    urlCard.find(".tagBadge").addClass("tagBadgeHoverable");
  }

  resetUpdateURLFailErrors(urlCard);
  if (!keepOpen) enableTagRemovalInURLCard(urlCard);
  // Panel-aware: when the sibling (title) form is still open on mobile, do NOT
  // re-arm the card's click.deselectURL handler — a tap into the still-open
  // sibling input would otherwise deselect the card and discard the in-progress
  // edit. The non-suppressed path (single-field / desktop) re-arms as before.
  const selectedAgain = urlCard.attr("urlSelected");
  if (
    !suppressSiblingDisable &&
    typeof selectedAgain === "string" &&
    selectedAgain.toLowerCase() === "true"
  ) {
    enableClickOnSelectedURLCardToHide(urlCard);
  }
}

// Prepares post request inputs for update of a URL
function updateURLSetup(
  urlStringUpdateInput: JQuery,
  utubID: number,
  utubUrlID: number,
): [string, UpdateUrlStringRequest] {
  const postURL = APP_CONFIG.routes.updateURL(utubID, utubUrlID);

  const updatedURL = getInputValue(urlStringUpdateInput).trim();

  const data: UpdateUrlStringRequest = { urlString: updatedURL };

  return [postURL, data];
}

// Handles update of an existing URL
export async function updateURL(
  urlStringUpdateInput: JQuery,
  urlCard: JQuery,
  utubID: number,
): Promise<void> {
  const utubUrlID = parseInt(urlCard.attr("utuburlid") as string);
  const timeoutID: number = setTimeoutAndShowURLCardLoadingIcon(urlCard);
  const panelOpen = isCardEditPanelOpen(urlCard);
  const stringSubmitBtn = urlCard.find(".urlStringSubmitBtnUpdate");
  if (panelOpen) {
    // Accessible in-flight guard: mark the submit control aria-disabled (not
    // native disabled, which drops focus) so a second overlapping submit is
    // blocked by the entry-point checks in url-string.ts until this settles.
    stringSubmitInFlight = true;
    stringSubmitBtn.attr("aria-disabled", "true");
  }
  try {
    await getUpdatedURL(utubID, utubUrlID, urlCard);

    // Extract data to submit in POST request
    const [patchURL, data] = updateURLSetup(
      urlStringUpdateInput,
      utubID,
      utubUrlID,
    );

    if (data.urlString === urlCard.find(".urlString").attr("href")) {
      log("updateURL skipped — value unchanged", { utubUrlID });
      // Panel-aware: on mobile the title form can still be open alongside this
      // string field. Suppress the sibling restore so we don't re-arm the card
      // deselect handler (and drop the go-to-URL icon / re-enable the title's
      // edit affordance) while the title edit is still in progress. keepOpen
      // keeps this field visually open (no tick — value unchanged) and
      // re-registers the open form so a later pagehide doesn't misreport CANCEL.
      const titleFormStillOpen = !urlCard
        .find(".updateUrlTitleWrap")
        .hasClass("hidden");
      hideAndResetUpdateURLStringForm({
        urlCard,
        suppressSiblingDisable: isCoarsePointer() && titleFormStillOpen,
        keepOpen: panelOpen,
      });
      if (panelOpen) setOpenForm(HOME_FORM.URL_STRING_EDIT);
      clearStringSubmitInFlight(stringSubmitBtn);
      clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
      return;
    }

    if (!isEmptyString(data.urlString) && !isValidURL(data.urlString)) {
      log("updateURL rejected by client-side URL validation", { utubUrlID });
      emit({
        event: UI_EVENTS.UI_VALIDATION_ERROR,
        form: VALIDATION_FORM.URL_STRING_EDIT,
      });
      displayUpdateURLErrors(
        "urlString",
        APP_CONFIG.strings.INVALID_URL,
        urlCard,
      );
      clearStringSubmitInFlight(stringSubmitBtn);
      clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
      return;
    }

    const request = ajaxCall("patch", patchURL, data, 35000);

    request.done(function (
      response: UpdateUrlStringResponse,
      _: JQuery.Ajax.SuccessTextStatus,
      xhr: JQuery.jqXHR,
    ) {
      if (xhr.status === 200) {
        updateURLSuccess(response, urlCard);
      }
    });

    request.fail(function (xhr: JQuery.jqXHR) {
      resetUpdateURLFailErrors(urlCard);
      updateURLFail(xhr, urlCard, utubID);
    });

    request.always(function () {
      clearStringSubmitInFlight(stringSubmitBtn);
      clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
    });
  } catch (error) {
    log("updateURL aborted — pre-flight URL fetch rejected", { utubUrlID });
    clearStringSubmitInFlight(stringSubmitBtn);
    clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
    handleRejectFromGetURL(error as JQuery.jqXHR, urlCard, {
      showError: true,
      message: "Another user has deleted this URL",
    });
  }
}

// Displays changes related to a successful update of a URL
function updateURLSuccess(
  response: UpdateUrlStringResponse,
  urlCard: JQuery,
): void {
  // Extract response data
  const updatedURLString = response.URL.urlString;

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
  urlCard
    .find(".urlString")
    .attr({ href: updatedURLString })
    .text(updatedURLString);

  // Update URL options. Dimensions (search_active, active_tag_count) are read
  // at click time so values reflect the deck state at the moment the user
  // activates the rebound button — not at updateURLSuccess time.
  urlCard.find(".urlBtnAccess").offAndOnExact("click", function () {
    emit({
      event: UI_EVENTS.UI_URL_ACCESS,
      trigger: URL_ACCESS_TRIGGER.MAIN_BUTTON,
      search_active: isURLSearchActive()
        ? SEARCH_ACTIVE.TRUE
        : SEARCH_ACTIVE.FALSE,
      active_tag_count: getActiveTagCount(),
    });
    accessLink(updatedURLString);
  });

  urlCard.find(".goToUrlIcon").offAndOnExact("click", function () {
    emit({
      event: UI_EVENTS.UI_URL_ACCESS,
      trigger: URL_ACCESS_TRIGGER.CORNER_BUTTON,
      search_active: isURLSearchActive()
        ? SEARCH_ACTIVE.TRUE
        : SEARCH_ACTIVE.FALSE,
      active_tag_count: getActiveTagCount(),
    });
    accessLink(updatedURLString);
  });

  urlCard
    .find(".urlBtnCopy")
    .offAndOnExact("click", function (this: HTMLElement) {
      copyURLString(updatedURLString, this);
    });

  // Panel-aware: on mobile the title form can still be open alongside this
  // string field. Suppress the sibling restore so submitting the string does
  // not re-arm the card deselect handler (which would discard an in-progress
  // title edit) while the title form is still open.
  const panelOpen = isCardEditPanelOpen(urlCard);
  const titleFormStillOpen = !urlCard
    .find(".updateUrlTitleWrap")
    .hasClass("hidden");
  hideAndResetUpdateURLStringForm({
    urlCard,
    suppressSiblingDisable: isCoarsePointer() && titleFormStillOpen,
    keepOpen: panelOpen,
  });
  // Mobile form model: keep the field open (action buttons stay hidden until
  // panel close), re-register the tracked open form (so a later pagehide doesn't
  // misreport UI_FORM_CANCEL), and flash a transient "Saved ✓" beside the
  // still-open field. updateURLSuccess is only reached on a genuine 200 for a
  // changed value, so no no-op guard needed.
  if (panelOpen) {
    setOpenForm(HOME_FORM.URL_STRING_EDIT);
    showFieldSavedTick({
      tick: urlCard.find(".updateUrlStringWrap .field-saved-tick"),
      announce: $("#fieldSavedAnnouncement"),
      label: APP_CONFIG.strings.FIELD_SAVED_LABEL_URL,
    });
  }
}

// Displays appropriate prompts and options to user following a failed update of a URL
function updateURLFail(
  xhr: JQuery.jqXHR,
  urlCard: JQuery,
  utubID: number,
): void {
  if (is429Handled(xhr)) return;
  if (isUtubLockedHandled(xhr)) return;

  log("updateURL failed", {
    status: xhr.status,
    utubUrlID: urlCard.attr("utuburlid"),
  });

  if (!("responseJSON" in xhr)) {
    if (
      xhr.status === 403 &&
      xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      // Handle invalid CSRF token error response
      $("body").html(xhr.responseText);
      return;
    }
    displayUpdateURLErrors(
      "urlString",
      "Server timed out while validating URL. Try again later.",
      urlCard,
    );
    return;
  }
  const responseJSON = xhr.responseJSON as UpdateUrlStringError;
  switch (xhr.status) {
    case 400:
      if (responseJSON.errors) {
        updateURLFailErrors(
          responseJSON.errors as Partial<
            Record<UpdateUrlStringFieldName, string[]>
          >,
          urlCard,
        );
        break;
      }
      if (responseJSON.message) {
        displayUpdateURLErrors(
          "urlString",
          responseJSON.message as string,
          urlCard,
        );
        break;
      }
    case 409:
      checkForStaleDataOn409(responseJSON, utubID);
      displayUpdateURLErrors(
        "urlString",
        responseJSON.message as string,
        urlCard,
      );
      break;
    case 403:
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}

function updateURLFailErrors(
  errors: Partial<Record<UpdateUrlStringFieldName, string[]>>,
  urlCard: JQuery,
): void {
  for (const errorFieldName in errors) {
    if (isUpdateUrlStringFieldName(errorFieldName)) {
      const errorMessage = errors[errorFieldName]![0];
      displayUpdateURLErrors(errorFieldName, errorMessage, urlCard);
      return;
    }
  }
}

function displayUpdateURLErrors(
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

function resetUpdateURLFailErrors(urlCard: JQuery): void {
  urlCard.find(".urlStringUpdate").removeClass("invalid-field");
  urlCard.find(".urlStringUpdate-error").removeClass("visible");
}
