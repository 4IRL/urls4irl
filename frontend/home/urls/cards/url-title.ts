import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import {
  ICON_SIZE_LG,
  ICON_SIZE_SM,
  KEYS,
  METHOD_TYPES,
} from "../../../lib/constants.js";
import { emit } from "../../../lib/metrics-client.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";
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
import {
  FORM_CANCEL_TRIGGER,
  FORM_SUBMIT_TRIGGER,
  HOME_FORM,
} from "../../../types/metrics-dim-values.js";

// Element to display the URL title
export function createURLTitle(urlTitleText: string): JQuery<HTMLElement> {
  return $(document.createElement("h6"))
    .addClass("urlTitle long-text-ellipsis")
    .text(urlTitleText);
}

// Creates a container that allows editing of the URL title for member with valid permissions
export function createURLTitleAndUpdateBlock(
  urlTitleText: string,
  urlCard: JQuery,
  utubID: number,
): JQuery<HTMLElement> {
  // Overall container for title and updating title
  const urlTitleAndUpdateWrap = $(document.createElement("div")).addClass(
    "flex-row ninetyfive-width",
  );

  // Contains the url title and icon to show the updating input box.
  // The wrap itself is the click target — tapping anywhere on the row
  // opens the edit form when the card is selected, mirroring the UTub
  // name/description edit pattern (see #UTubNameUpdateWrap in
  // backend/templates/components/home/URLDeck/URLDeckHeader.html).
  const urlTitleAndShowUpdateIconWrap = $(document.createElement("div"))
    .addClass(
      "flex-row ninetyfive-width urlTitleAndUpdateIconWrap editable-wrap",
    )
    .onExact(
      "click.showUpdateURLTitle",
      function (event: JQuery.TriggeredEvent) {
        if (urlCard.attr("urlSelected") !== "true") return;
        const wrapEl = $(event.currentTarget) as JQuery;
        showUpdateURLTitleForm(wrapEl, urlCard);
      },
    );
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

// Create the icon hint that the title row is editable.
// Click is handled by the surrounding wrap (see urlTitleAndShowUpdateIconWrap
// above) — keydown stays here so a keyboard user who tabs onto the pencil
// can activate edit mode with Enter/Space.
function createShowUpdateURLTitleIcon(urlCard: JQuery): JQuery<HTMLElement> {
  return makeUpdateButton(ICON_SIZE_SM)
    .addClass("urlTitleBtnUpdate edit-pencil-icon")
    .addClass("tabbable")
    .attr({
      "aria-label": APP_CONFIG.strings.EDIT_URL_TITLE_TOOLTIP,
      type: "button",
    })
    .onExact(
      "keydown.showUpdateURLTitle",
      function (event: JQuery.TriggeredEvent) {
        if (event.key === KEYS.ENTER || event.key === KEYS.SPACE) {
          event.preventDefault();
          const urlTitleAndIcon = $(event.target).closest(
            ".urlTitleAndUpdateIconWrap",
          );
          showUpdateURLTitleForm(urlTitleAndIcon, urlCard);
        }
      },
    );
}

// Create the form to update the URL Title
function createUpdateURLTitleInput(
  urlTitleText: string,
  urlCard: JQuery,
  utubID: number,
): JQuery<HTMLElement> {
  // Create the update title text box
  const urlTitleUpdateInputContainer = makeTextInput(
    "urlTitle",
    METHOD_TYPES.UPDATE.description!,
  ).addClass("updateUrlTitleWrap hidden");

  urlTitleUpdateInputContainer.find("label").text("URL Title");

  // Customize the input text box for the Url title
  const urlTitleTextInput = urlTitleUpdateInputContainer.find("input");

  urlTitleTextInput
    .prop("minLength", APP_CONFIG.constants.URLS_TITLE_MIN_LENGTH)
    .prop("maxLength", APP_CONFIG.constants.URLS_TITLE_MAX_LENGTH)
    .val(urlTitleText);

  urlTitleTextInput.offAndOn("focus.updateURLTitleInputFocus", function () {
    urlTitleTextInput.on(
      "keydown.updateURLTitleSubmitEscape",
      function (event: JQuery.TriggeredEvent) {
        if ((event.originalEvent as KeyboardEvent).repeat) return;
        switch (event.key) {
          case KEYS.ENTER:
            emit({
              event: UI_EVENTS.UI_FORM_SUBMIT,
              form: HOME_FORM.URL_TITLE_EDIT,
              trigger: FORM_SUBMIT_TRIGGER.ENTER_KEY,
            });
            updateURLTitle(urlTitleTextInput, urlCard, utubID);
            break;
          case KEYS.ESCAPE:
            emit({
              event: UI_EVENTS.UI_FORM_CANCEL,
              form: HOME_FORM.URL_TITLE_EDIT,
              trigger: FORM_CANCEL_TRIGGER.ESCAPE_KEY,
            });
            hideAndResetUpdateURLTitleForm(urlCard);
            break;
          default:
          /* no-op */
        }
      },
    );
  });

  urlTitleTextInput.offAndOn("blur.updateURLTitleInputFocus", function () {
    urlTitleTextInput.off("keydown.updateURLTitleSubmitEscape");
  });

  // Update Url Title submit button
  const urlTitleSubmitBtnUpdate = makeSubmitButton(ICON_SIZE_LG).addClass(
    "urlTitleSubmitBtnUpdate",
  );

  urlTitleSubmitBtnUpdate.onExact("click.updateUrlTitle", function () {
    emit({
      event: UI_EVENTS.UI_FORM_SUBMIT,
      form: HOME_FORM.URL_TITLE_EDIT,
      trigger: FORM_SUBMIT_TRIGGER.BUTTON_CLICK,
    });
    updateURLTitle(urlTitleTextInput, urlCard, utubID);
  });

  // Update Url Title cancel button
  const urlTitleCancelBtnUpdate = makeCancelButton(ICON_SIZE_LG).addClass(
    "urlTitleCancelBtnUpdate tabbable",
  );

  urlTitleCancelBtnUpdate.onExact("click.updateUrlTitle", function () {
    emit({
      event: UI_EVENTS.UI_FORM_CANCEL,
      form: HOME_FORM.URL_TITLE_EDIT,
      trigger: FORM_CANCEL_TRIGGER.CANCEL_BUTTON,
    });
    hideAndResetUpdateURLTitleForm(urlCard);
  });

  urlTitleUpdateInputContainer
    .append(urlTitleSubmitBtnUpdate)
    .append(urlTitleCancelBtnUpdate);

  return urlTitleUpdateInputContainer;
}
