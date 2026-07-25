import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import {
  ICON_SIZE_LG,
  INPUT_TYPES,
  KEYS,
  METHOD_TYPES,
} from "../../../lib/constants.js";
import { emit } from "../../../lib/metrics-client.js";
import { clearOpenForm } from "../../../lib/modal-tracking.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";
import { isURLSearchActive, getActiveTagCount } from "../url-context.js";
import { accessLink } from "./access.js";
import {
  updateURL,
  hideAndResetUpdateURLStringForm,
  isURLStringSubmitInFlight,
} from "./update-string.js";
import { isCoarsePointer } from "../../mobile.js";
import {
  makeTextInput,
  makeSubmitButton,
  makeCancelButton,
} from "../../btns-forms.js";
import {
  FORM_CANCEL_TRIGGER,
  FORM_SUBMIT_TRIGGER,
  HOME_FORM,
  SEARCH_ACTIVE,
  URL_ACCESS_TRIGGER,
} from "../../../types/metrics-dim-values.js";

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
          emit({
            event: UI_EVENTS.UI_URL_ACCESS,
            trigger: URL_ACCESS_TRIGGER.URL_TEXT,
            search_active: isURLSearchActive()
              ? SEARCH_ACTIVE.TRUE
              : SEARCH_ACTIVE.FALSE,
            active_tag_count: getActiveTagCount(),
          });
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
    METHOD_TYPES.UPDATE.description!,
    INPUT_TYPES.URL.description!,
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
  const urlStringSubmitBtnUpdate = makeSubmitButton(ICON_SIZE_LG).addClass(
    "urlStringSubmitBtnUpdate",
  );

  urlStringSubmitBtnUpdate.onExact("click.updateUrlString", function () {
    // Block an overlapping submit while a kept-open submit is in flight.
    if (isURLStringSubmitInFlight()) return;
    emit({
      event: UI_EVENTS.UI_FORM_SUBMIT,
      form: HOME_FORM.URL_STRING_EDIT,
      trigger: FORM_SUBMIT_TRIGGER.BUTTON_CLICK,
    });
    clearOpenForm();
    updateURL(urlStringTextInput, urlCard, utubID);
  });

  // Update Url Title cancel button
  const urlStringCancelBtnUpdate = makeCancelButton(ICON_SIZE_LG).addClass(
    "urlStringCancelBtnUpdate",
  );

  urlStringCancelBtnUpdate.onExact("click.updateUrlString", function () {
    emit({
      event: UI_EVENTS.UI_FORM_CANCEL,
      form: HOME_FORM.URL_STRING_EDIT,
      trigger: FORM_CANCEL_TRIGGER.CANCEL_BUTTON,
    });
    clearOpenForm();
    hideAndResetUpdateURLStringForm({ urlCard });
  });

  // Two-level restructure (mirrors the UTub Jinja template's shape): nest the
  // input container + submit/cancel buttons in an inner row, then hang the
  // "Saved ✓" tick slot below as a sibling row. On touch devices the
  // coarse-pointer CSS override (urls.css) stacks these two children as a
  // column so the tick lands below the input; desktop keeps the inherited
  // side-by-side flex-row layout from makeTextInput's wrap.
  const urlStringInputInnerRow = $(document.createElement("div"))
    .addClass("flex-row full-width")
    .append(urlStringUpdateTextInputContainer.find(".text-input-container"))
    .append(urlStringSubmitBtnUpdate)
    .append(urlStringCancelBtnUpdate);

  const urlStringSavedTickSlot = $(document.createElement("div"))
    .addClass("field-saved-tick-slot")
    .append(
      $(document.createElement("span"))
        .addClass("field-saved-tick opa-0")
        .attr("aria-hidden", "true")
        .html(`${APP_CONFIG.strings.FIELD_SAVED} <i class="bi bi-check"></i>`),
    );

  urlStringUpdateTextInputContainer
    .append(urlStringInputInnerRow)
    .append(urlStringSavedTickSlot);

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
            // Block an overlapping submit while a kept-open submit is in flight.
            if (isURLStringSubmitInFlight()) return;
            // Handle enter key pressed
            emit({
              event: UI_EVENTS.UI_FORM_SUBMIT,
              form: HOME_FORM.URL_STRING_EDIT,
              trigger: FORM_SUBMIT_TRIGGER.ENTER_KEY,
            });
            clearOpenForm();
            updateURL(urlStringInput, urlCard, utubID);
            break;
          case KEYS.ESCAPE:
            // On mobile, defer to the panel-level document Escape handler
            // (bound in openURLEditPanel) so both fields close together and the
            // two mechanisms don't double-fire.
            if (isCoarsePointer()) break;
            // Handle escape key pressed
            emit({
              event: UI_EVENTS.UI_FORM_CANCEL,
              form: HOME_FORM.URL_STRING_EDIT,
              trigger: FORM_CANCEL_TRIGGER.ESCAPE_KEY,
            });
            clearOpenForm();
            hideAndResetUpdateURLStringForm({ urlCard });
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
