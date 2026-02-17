import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { KEYS, METHOD_TYPES } from "../../../lib/constants.js";
import {
  updateURLTitle,
  showUpdateURLTitleForm,
  hideAndResetUpdateURLTitleForm,
} from "./update-title.js";
import {
  makeUpdateButton,
  makeTextInput,
  makeSubmitButton,
  makeCancelButton,
} from "../../btns-forms.js";

// Element to display the URL title
export function createURLTitle(urlTitleText) {
  return $(document.createElement("h6"))
    .addClass("urlTitle long-text-ellipsis")
    .text(urlTitleText);
}

// Creates a container that allows editing of the URL title for member with valid permissions
export function createURLTitleAndUpdateBlock(urlTitleText, urlCard, utubID) {
  // Overall container for title and updating title
  const urlTitleAndUpdateWrap = $(document.createElement("div")).addClass(
    "flex-row ninetyfive-width",
  );

  // Contains the url title and icon to show the updating input box
  const urlTitleAndShowUpdateIconWrap = $(
    document.createElement("div"),
  ).addClass("flex-row ninetyfive-width urlTitleAndUpdateIconWrap");
  // Parent container with both show update icon and url title, allows hover to show the update icon
  const urlTitleAndShowUpdateIconInnerWrap = $(
    document.createElement("div"),
  ).addClass("flex-row full-width urlTitleAndUpdateIconInnerWrap");

  // Add icon and title to the container
  urlTitleAndShowUpdateIconInnerWrap
    .append(createURLTitle(urlTitleText))
    .append(createShowUpdateURLTitleIcon(urlCard));
  urlTitleAndShowUpdateIconWrap.append(urlTitleAndShowUpdateIconInnerWrap);

  // Add icon + title container, and update input container to the parent container
  urlTitleAndUpdateWrap
    .append(urlTitleAndShowUpdateIconWrap)
    .append(createUpdateURLTitleInput(urlTitleText, urlCard, utubID));

  return urlTitleAndUpdateWrap;
}

// Create the icon that will show the update URL title form
function createShowUpdateURLTitleIcon(urlCard) {
  return makeUpdateButton(20)
    .addClass("urlTitleBtnUpdate")
    .onExact("click.showUpdateURLTitle", function (e) {
      const urlTitleAndIcon = $(e.target).closest(".urlTitleAndUpdateIconWrap");
      showUpdateURLTitleForm(urlTitleAndIcon, urlCard);
    });
}

// Create the form to update the URL Title
function createUpdateURLTitleInput(urlTitleText, urlCard, utubID) {
  // Create the update title text box
  const urlTitleUpdateInputContainer = makeTextInput(
    "urlTitle",
    METHOD_TYPES.UPDATE.description,
  ).addClass("updateUrlTitleWrap hidden");

  urlTitleUpdateInputContainer.find("label").text("URL Title");

  // Customize the input text box for the Url title
  const urlTitleTextInput = urlTitleUpdateInputContainer.find("input");

  urlTitleTextInput
    .prop("minLength", APP_CONFIG.constants.URLS_TITLE_MIN_LENGTH)
    .prop("maxLength", APP_CONFIG.constants.URLS_TITLE_MAX_LENGTH)
    .val(urlTitleText);

  urlTitleTextInput.offAndOn("focus.updateURLTitleInputFocus", function () {
    urlTitleTextInput.on("keydown.updateURLTitleSubmitEscape", function (e) {
      if (e.originalEvent.repeat) return;
      switch (e.key) {
        case KEYS.ENTER:
          updateURLTitle(urlTitleTextInput, urlCard, utubID);
          break;
        case KEYS.ESCAPE:
          hideAndResetUpdateURLTitleForm(urlCard);
          break;
        default:
        /* no-op */
      }
    });
  });

  urlTitleTextInput.offAndOn("blur.updateURLTitleInputFocus", function () {
    urlTitleTextInput.off("keydown.updateURLTitleSubmitEscape");
  });

  // Update Url Title submit button
  const urlTitleSubmitBtnUpdate = makeSubmitButton(30).addClass(
    "urlTitleSubmitBtnUpdate",
  );

  urlTitleSubmitBtnUpdate.onExact("click.updateUrlTitle", function (e) {
    updateURLTitle(urlTitleTextInput, urlCard, utubID);
  });

  // Update Url Title cancel button
  const urlTitleCancelBtnUpdate = makeCancelButton(30).addClass(
    "urlTitleCancelBtnUpdate tabbable",
  );

  urlTitleCancelBtnUpdate.onExact("click.updateUrlTitle", function (e) {
    hideAndResetUpdateURLTitleForm(urlCard);
  });

  urlTitleUpdateInputContainer
    .append(urlTitleSubmitBtnUpdate)
    .append(urlTitleCancelBtnUpdate);

  return urlTitleUpdateInputContainer;
}
