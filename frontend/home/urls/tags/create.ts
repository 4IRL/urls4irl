import type { components, operations } from "../../../types/api.d.ts";
import type { UtubUrlItem } from "../../../types/url.js";

import { $, bootstrap } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { METHOD_TYPES } from "../../../lib/constants.js";
import {
  makeTextInput,
  makeSubmitButton,
  makeCancelButton,
} from "../../btns-forms.js";
import {
  setFocusEventListenersOnCreateURLTagInput,
  createTagBadgeInURL,
} from "./tags.js";
import {
  disableTagRemovalInURLCard,
  enableTagRemovalInURLCard,
} from "./tags.js";
import {
  setTimeoutAndShowURLCardLoadingIcon,
  clearTimeoutIDAndHideLoadingIcon,
} from "../cards/loading.js";
import { getUpdatedURL, handleRejectFromGetURL } from "../cards/get.js";
import {
  disableEditingURLTitle,
  enableEditingURLTitle,
} from "../cards/utils.js";
import {
  disableClickOnSelectedURLCardToHide,
  enableClickOnSelectedURLCardToHide,
} from "../cards/selection.js";
import { isMobile } from "../../mobile.js";
import {
  enableTabbableChildElements,
  disableTabbableChildElements,
} from "../../../lib/jquery-plugins.js";
import { createAddTagIcon } from "../cards/options/tag-btn.js";
import { isTagInUTubTagDeck } from "../../tags/utils.js";
import { buildTagFilterInDeck } from "../../tags/tags.js";
import { updateTagFilterCount, TagCountOperation } from "../cards/filtering.js";
import { getState, setState } from "../../../store/app-store.js";

type AddTagRequest = components["schemas"]["AddTagRequest"];
type UrlTagModifiedResponse =
  operations["createUtubUrlTag"]["responses"][200]["content"]["application/json"];
type UrlTagError = components["schemas"]["ErrorResponse_URLTagErrorCodes"];

const CREATE_URL_TAG_FIELD_NAMES = ["tagString"] as const;

type CreateUrlTagFieldName = (typeof CREATE_URL_TAG_FIELD_NAMES)[number];

function isCreateUrlTagFieldName(key: string): key is CreateUrlTagFieldName {
  return (CREATE_URL_TAG_FIELD_NAMES as readonly string[]).includes(key);
}

export function createTagInputBlock(
  urlCard: JQuery,
  utubID: number,
): JQuery<HTMLElement> {
  const urlTagCreateTextInputContainer = makeTextInput(
    "urlTag",
    METHOD_TYPES.CREATE.description,
  ).addClass("createUrlTagWrap hidden flex-start gap-5p");

  urlTagCreateTextInputContainer.find("label").text("Tag");

  // Customize the input text box for the Url title
  const urlTagTextInput = urlTagCreateTextInputContainer
    .find("input")
    .prop("minLength", APP_CONFIG.constants.TAGS_MIN_LENGTH)
    .prop("maxLength", APP_CONFIG.constants.TAGS_MAX_LENGTH);

  setFocusEventListenersOnCreateURLTagInput(urlTagTextInput, urlCard, utubID);

  // Create Url Title submit button
  const urlTagSubmitBtnCreate = makeSubmitButton(30).addClass(
    "urlTagSubmitBtnCreate",
  );

  urlTagSubmitBtnCreate.onExact("click.createURLTag", function () {
    createURLTag(urlTagTextInput, urlCard, utubID);
  });

  // Create Url Title cancel button
  const urlTagCancelBtnCreate = makeCancelButton(30).addClass(
    "urlTagCancelBtnCreate",
  );

  urlTagCancelBtnCreate.onExact("click.createURLTag", function () {
    hideAndResetCreateURLTagForm(urlCard);
  });

  urlTagCreateTextInputContainer
    .append(urlTagSubmitBtnCreate)
    .append(urlTagCancelBtnCreate);

  return urlTagCreateTextInputContainer;
}

/**
 * Displays new Tag input prompt on selected URL
 */
export function showCreateURLTagForm(
  urlCard: JQuery,
  urlTagBtnCreate: JQuery,
): void {
  // Show form to add a tag to this URL
  const tagInputFormContainer = urlCard.find(".createUrlTagWrap");
  enableTabbableChildElements(tagInputFormContainer);
  $(tagInputFormContainer).showClassFlex();

  // Handle case where iOS needs a direct focus not in a timeout, even with animation
  if (isMobile()) {
    tagInputFormContainer.find("input").focus();
  }

  // Focus on the input to add a tag - with delay in case user opened by pressing enter
  setTimeout(function () {
    tagInputFormContainer.find("input").trigger("focus");
  }, 100);

  // Disable URL Buttons as url Tag is being created
  urlCard.find(".urlBtnAccess").hideClass();
  urlCard.find(".urlStringBtnUpdate").hideClass();
  urlCard.find(".urlBtnDelete").hideClass();
  urlCard.find(".urlBtnCopy").hideClass();

  // Prevent hovering on tags from adding padding
  urlCard.find(".tagBadge").removeClass("tagBadgeHoverable");

  const tooltipElement = urlTagBtnCreate.get(0);
  const tooltip = tooltipElement
    ? bootstrap.Tooltip.getInstance(tooltipElement)
    : null;
  if (tooltip) {
    tooltip.hide();
    tooltip.disable();
  }

  // Modify add tag button
  urlTagBtnCreate
    .removeClass("fourty-p-width")
    .addClass("cancel urlTagCancelBigBtnCreate")
    .text("Cancel")
    .offAndOnExact("click", function () {
      hideAndResetCreateURLTagForm(urlCard);
      if (tooltip) tooltip.enable();
    });

  disableTagRemovalInURLCard(urlCard);
  disableEditingURLTitle(urlCard);
  disableClickOnSelectedURLCardToHide(urlCard);
}

export function hideAndResetCreateURLTagForm(urlCard: JQuery): void {
  resetCreateURLTagFailErrors(urlCard);

  // Modify add tag button
  const urlTagBtnCreate = urlCard.find(".urlTagBtnCreate");
  urlTagBtnCreate
    .removeClass("cancel urlTagCancelBigBtnCreate")
    .addClass("fourty-p-width")
    .offAndOnExact("click", function () {
      showCreateURLTagForm(urlCard, urlTagBtnCreate);
    })
    .text("")
    .append(createAddTagIcon());

  // Hide form to add a tag to this URL
  const tagInputFormContainer = urlCard.find(".createUrlTagWrap");
  disableTabbableChildElements(tagInputFormContainer);
  tagInputFormContainer.hideClass();

  // Reset input form
  tagInputFormContainer.find("input").val("");

  // Enable URL Buttons as url Tag creation form is hidden
  urlCard.find(".urlBtnAccess").showClassFlex();
  urlCard.find(".urlStringBtnUpdate").showClassFlex();
  urlCard.find(".urlBtnDelete").showClassFlex();
  urlCard.find(".urlBtnCopy").showClassFlex();

  // Enable hovering on tags for deletion
  urlCard.find(".tagBadge").addClass("tagBadgeHoverable");

  enableTagRemovalInURLCard(urlCard);
  enableEditingURLTitle(urlCard);
  const selectedAttr = urlCard.attr("urlSelected");
  if (
    typeof selectedAttr === "string" &&
    selectedAttr.toLowerCase() === "true"
  ) {
    enableClickOnSelectedURLCardToHide(urlCard);
  }
}

/**
 * Prepares post request inputs for addition of a new Tag to URL
 */
function createURLTagSetup(
  urlTagCreateInput: JQuery,
  utubID: number,
  utubUrlID: number,
): [string, AddTagRequest] {
  // Assemble post request route
  const postURL = APP_CONFIG.routes.createURLTag(utubID, utubUrlID);

  // Assemble submission data
  const data: AddTagRequest = {
    tagString: urlTagCreateInput.val() as string,
  };

  return [postURL, data];
}

/**
 * Handles addition of new Tag to URL after user submission
 */
export async function createURLTag(
  urlTagCreateInput: JQuery,
  urlCard: JQuery,
  utubID: number,
): Promise<void> {
  const utubUrlID = parseInt(urlCard.attr("utuburlid") as string);
  // Extract data to submit in POST request
  const [postURL, data] = createURLTagSetup(
    urlTagCreateInput,
    utubID,
    utubUrlID,
  );

  const timeoutID: number = setTimeoutAndShowURLCardLoadingIcon(urlCard);
  try {
    await getUpdatedURL(utubID, utubUrlID, urlCard);

    const request = ajaxCall("post", postURL, data);

    // Handle response
    request.done(function (
      response: UrlTagModifiedResponse,
      _: JQuery.Ajax.SuccessTextStatus,
      xhr: JQuery.jqXHR,
    ) {
      if (xhr.status === 200) {
        resetCreateURLTagFailErrors(urlCard);
        createURLTagSuccess(response, urlCard, utubID);
      }
    });

    request.fail(function (xhr: JQuery.jqXHR) {
      createURLTagFail(xhr, urlCard);
    });

    request.always(function () {
      clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
    });
  } catch (error) {
    clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
    handleRejectFromGetURL(error as JQuery.jqXHR, urlCard, {
      showError: true,
      message: "Another user has deleted this URL",
    });
  }
}

/**
 * Displays changes related to a successful addition of a new Tag
 */
function createURLTagSuccess(
  response: UrlTagModifiedResponse,
  urlCard: JQuery,
  utubID: number,
): void {
  // Clear and reset input field
  hideAndResetCreateURLTagForm(urlCard);

  const urlID = parseInt(urlCard.attr("utuburlid") as string);
  setState({
    urls: getState().urls.map((existingUrl: UtubUrlItem) =>
      existingUrl.utubUrlID === urlID
        ? { ...existingUrl, utubUrlTagIDs: response.utubUrlTagIDs }
        : existingUrl,
    ),
    tags: getState().tags.map((tag) =>
      tag.id === response.utubTag.utubTagID
        ? { ...tag, tagApplied: response.tagCountsInUtub }
        : tag,
    ),
  });

  // Extract response data
  const utubTagID = response.utubTag.utubTagID;
  const tagString = response.utubTag.tagString;
  const tagCount = response.tagCountsInUtub;

  // Update tags in URL
  urlCard
    .find(".urlTagsContainer")
    .append(createTagBadgeInURL(utubTagID, tagString, urlCard, utubID));

  const currentURLTagIDs = urlCard.attr("data-utub-url-tag-ids") || "";

  if (currentURLTagIDs.trim()) {
    urlCard.attr("data-utub-url-tag-ids", currentURLTagIDs + `,${utubTagID}`);
  } else {
    urlCard.attr("data-utub-url-tag-ids", String(utubTagID));
  }

  // Add SelectAll button if not yet there
  $("#unselectAllTagFilters").showClassNormal();

  if (!isTagInUTubTagDeck(utubTagID)) {
    const newTag = buildTagFilterInDeck(utubID, utubTagID, tagString, tagCount);
    // If max number of tags already selected
    if (
      $(".tagFilter.selected").length === APP_CONFIG.constants.TAGS_MAX_ON_URL
    ) {
      newTag.addClass("disabled").off(".tagFilterSelected");
    }
    $("#listTags").append(newTag);
    $("#utubTagBtnUpdateAllOpen").showClassNormal();
  } else {
    // Update tag filter in Tag Deck
    updateTagFilterCount(utubTagID, tagCount, TagCountOperation.INCREMENT);
  }
}

/**
 * Displays appropriate prompts and options to user following a failed addition of a new Tag
 */
function createURLTagFail(xhr: JQuery.jqXHR, urlCard: JQuery): void {
  if (is429Handled(xhr)) return;

  if (!xhr.hasOwnProperty("responseJSON")) {
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
      const responseJSON = xhr.responseJSON as UrlTagError;
      if (responseJSON.hasOwnProperty("message")) {
        if (responseJSON.hasOwnProperty("errors")) {
          createURLTagFailErrors(
            responseJSON.errors as Partial<
              Record<CreateUrlTagFieldName, string[]>
            >,
            urlCard,
          );
        } else {
          displayCreateURLTagErrors(
            "urlTag",
            responseJSON.message as string,
            urlCard,
          );
        }
      }
      break;
    }
    case 403:
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}

function createURLTagFailErrors(
  errors: Partial<Record<CreateUrlTagFieldName, string[]>>,
  urlCard: JQuery,
): void {
  for (const errorFieldName in errors) {
    if (isCreateUrlTagFieldName(errorFieldName)) {
      const errorMessage = errors[errorFieldName]![0];
      displayCreateURLTagErrors("urlTag", errorMessage, urlCard);
      return;
    }
  }
}

function displayCreateURLTagErrors(
  key: string,
  errorMessage: string,
  urlCard: JQuery,
): void {
  urlCard
    .find("." + key + "Create-error")
    .addClass("visible")
    .text(errorMessage);
  urlCard.find("." + key + "Create").addClass("invalid-field");
}

function resetCreateURLTagFailErrors(urlCard: JQuery): void {
  urlCard.find(".urlTagCreate").removeClass("invalid-field");
  urlCard.find(".urlTagCreate-error").removeClass("visible");
}
