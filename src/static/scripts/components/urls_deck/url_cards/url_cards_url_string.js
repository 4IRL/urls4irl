"use strict";

// Element to displayu the URL string
function createURLString(urlStringText) {
  const displayURL = modifyURLStringForDisplay(urlStringText);
  return $(document.createElement("a"))
    .addClass("urlString long-text-ellipsis tabbable")
    .attr({
      href: urlStringText,
      target: "_blank",
    })
    .text(displayURL)
    .offAndOn("click.defaultlinkbehavior", function (e) {
      // Only allow a URL to be clickable when the Card is selected
      e.preventDefault();
      if ($(e.target).closest(".urlRow").attr("urlSelected") === "true") {
        accessLink(urlStringText);
      }
    });
}

// Create the container for both displaying URL string, and updating the URL string
function createURLStringAndUpdateBlock(urlStringText, urlCard, utubID) {
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
function createUpdateURLStringInput(urlStringText, urlCard, utubID) {
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

  urlStringSubmitBtnUpdate
    .find(".submitButton")
    .on("click.updateUrlString", function () {
      updateURL(urlStringTextInput, urlCard, utubID);
    })
    .on("focus.updateUrlString", function () {
      $(document).on("keyup.updateUrlString", function (e) {
        if (e.key === KEYS.ENTER)
          updateURL(urlStringTextInput, urlCard, utubID);
      });
    })
    .on("blur.updateUrlString", function () {
      $(document).off("keyup.updateUrlString");
    });

  // Update Url Title cancel button
  const urlStringCancelBtnUpdate = makeCancelButton(30).addClass(
    "urlStringCancelBtnUpdate",
  );

  urlStringCancelBtnUpdate
    .find(".cancelButton")
    .on("click.updateUrlString", function (e) {
      e.stopPropagation();
      hideAndResetUpdateURLStringForm(urlCard);
    })
    .offAndOn("focus.updateUrlString", function () {
      $(document).on("keyup.updateUrlString", function (e) {
        if (e.key === KEYS.ENTER) hideAndResetUpdateURLStringForm(urlCard);
      });
    })
    .offAndOn("blur.updateUrlString", function () {
      $(document).off("keyup.updateUrlString");
    });

  urlStringUpdateTextInputContainer
    .append(urlStringSubmitBtnUpdate)
    .append(urlStringCancelBtnUpdate);

  return urlStringUpdateTextInputContainer;
}

function setFocusEventListenersOnUpdateURLStringInput(
  urlStringInput,
  urlCard,
  utubID,
) {
  urlStringInput.offAndOn("focus.updateURLStringFocus", function () {
    $(document).offAndOn("keyup.updateURLStringFocus", function (e) {
      switch (e.key) {
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
    });
  });

  urlStringInput.offAndOn("blur.updateURLStringFocus", function () {
    $(document).off("keyup.updateURLStringFocus");
  });
}

function modifyURLStringForDisplay(urlString) {
  // Remove https://, http://, and www. (in any combination) from the start
  return urlString.replace(/^(?:https?:\/\/)?(?:www\.)?/, "");
}
