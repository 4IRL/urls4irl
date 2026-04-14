import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { KEYS, METHOD_TYPES, INPUT_TYPES } from "../../../lib/constants.js";
import { accessLink } from "./access.js";
import { updateURL, hideAndResetUpdateURLStringForm } from "./update-string.js";
import {
  makeTextInput,
  makeSubmitButton,
  makeCancelButton,
} from "../../btns-forms.js";

// Element to displayu the URL string
export function createURLString(urlStringText: string): JQuery<HTMLElement> {
  const displayURL = modifyURLStringForDisplay(urlStringText);
  return $(document.createElement("a"))
    .addClass("urlString long-text-ellipsis tabbable")
    .attr({
      href: urlStringText,
      target: "_blank",
    })
    .text(displayURL)
    .offAndOn(
      "click.defaultlinkbehavior",
      function (event: JQuery.TriggeredEvent) {
        // Only allow a URL to be clickable when the Card is selected
        event.preventDefault();
        if ($(event.target).closest(".urlRow").attr("urlSelected") === "true") {
          accessLink(urlStringText);
        }
      },
    );
}

// Create the container for both displaying URL string, and updating the URL string
export function createURLStringAndUpdateBlock(
  urlStringText: string,
  urlCard: JQuery,
  utubID: number,
): JQuery<HTMLElement> {
  // Overall container for string and updating string
  const urlStringAndUpdateWrap = $(document.createElement("div")).addClass(
    "flex-row ninetyfive-width",
  );

  urlStringAndUpdateWrap
    .append(createURLString(urlStringText))
    .append(createUpdateURLStringInput(urlStringText, urlCard, utubID));

  return urlStringAndUpdateWrap;
}

// Create form to update the URL
function createUpdateURLStringInput(
  urlStringText: string,
  urlCard: JQuery,
  utubID: number,
): JQuery<HTMLElement> {
  const urlStringUpdateTextInputContainer = makeTextInput(
    "urlString",
    METHOD_TYPES.UPDATE.description,
    INPUT_TYPES.URL.description,
  ).addClass("updateUrlStringWrap hidden gap-5p");

  urlStringUpdateTextInputContainer.find("label").text("URL");

  // Customize the input text box for the Url title
  const urlStringTextInput = urlStringUpdateTextInputContainer
    .find("input")
    .prop("minLength", APP_CONFIG.constants.URLS_MIN_LENGTH)
    .prop("maxLength", APP_CONFIG.constants.URLS_MAX_LENGTH)
    .val(urlStringText);

  setFocusEventListenersOnUpdateURLStringInput(
    urlStringTextInput,
    urlCard,
    utubID,
  );

  // Update Url Title submit button
  const urlStringSubmitBtnUpdate = makeSubmitButton(30).addClass(
    "urlStringSubmitBtnUpdate",
  );

  urlStringSubmitBtnUpdate.onExact("click.updateUrlString", function () {
    updateURL(urlStringTextInput, urlCard, utubID);
  });

  // Update Url Title cancel button
  const urlStringCancelBtnUpdate = makeCancelButton(30).addClass(
    "urlStringCancelBtnUpdate",
  );

  urlStringCancelBtnUpdate.onExact("click.updateUrlString", function () {
    hideAndResetUpdateURLStringForm(urlCard);
  });

  urlStringUpdateTextInputContainer
    .append(urlStringSubmitBtnUpdate)
    .append(urlStringCancelBtnUpdate);

  return urlStringUpdateTextInputContainer;
}

function setFocusEventListenersOnUpdateURLStringInput(
  urlStringInput: JQuery,
  urlCard: JQuery,
  utubID: number,
): void {
  urlStringInput.offAndOn("focus.updateURLStringFocus", function () {
    $(document).offAndOn(
      "keyup.updateURLStringFocus",
      function (event: JQuery.TriggeredEvent) {
        switch (event.key) {
          case KEYS.ENTER:
            // Handle enter key pressed
            updateURL(urlStringInput, urlCard, utubID);
            break;
          case KEYS.ESCAPE:
            // Handle escape key pressed
            hideAndResetUpdateURLStringForm(urlCard);
            break;
          default:
          /* no-op */
        }
      },
    );
  });

  urlStringInput.offAndOn("blur.updateURLStringFocus", function () {
    $(document).off("keyup.updateURLStringFocus");
  });
}

export function modifyURLStringForDisplay(urlString: string): string {
  // Remove https://, http://, and www. (in any combination) from the start
  return urlString.replace(/^(?:https?:\/\/)?(?:www\.)?/, "");
}
