"use strict";

// Element to displayu the URL string
function createURLString(urlStringText) {
  let displayURL = urlStringText.replace(/^https:\/\//, "");
  displayURL = displayURL.replace(/^www\./, "");
  return $(document.createElement("a"))
    .addClass("urlString long-text-ellipsis tabbable")
    .attr({
      href: urlStringText,
      target: "_blank",
    })
    .text(displayURL)
    .offAndOn("click.defaultlinkbehavior", function (e) {
      e.preventDefault();
    });
}

// Create the container for both displaying URL string, and updating the URL string
function createURLStringAndUpdateBlock(urlStringText, urlCard) {
  // Overall container for string and updating string
  const urlStringAndUpdateWrap = $(document.createElement("div")).addClass(
    "flex-row ninetyfive-width",
  );

  urlStringAndUpdateWrap
    .append(createURLString(urlStringText))
    .append(createUpdateURLStringInput(urlStringText, urlCard));

  return urlStringAndUpdateWrap;
}

// Create form to update the URL
function createUpdateURLStringInput(urlStringText, urlCard) {
  const urlStringUpdateTextInputContainer = makeTextInput(
    "urlString",
    METHOD_TYPES.UPDATE.description,
    INPUT_TYPES.URL.description,
  )
    .addClass("updateUrlStringWrap")
    .css("display", "none");

  urlStringUpdateTextInputContainer.find("label").text("URL");

  // Customize the input text box for the Url title
  const urlStringTextInput = urlStringUpdateTextInputContainer
    .find("input")
    .prop("minLength", CONSTANTS.URLS_MIN_LENGTH)
    .prop("maxLength", CONSTANTS.URLS_MAX_LENGTH)
    .val(urlStringText);

  setFocusEventListenersOnUpdateURLStringInput(urlStringTextInput, urlCard);

  // Update Url Title submit button
  const urlStringSubmitBtnUpdate = makeSubmitButton(30).addClass(
    "urlStringSubmitBtnUpdate",
  );

  urlStringSubmitBtnUpdate
    .find(".submitButton")
    .on("click.updateUrlString", function () {
      updateURL(urlStringTextInput, urlCard);
    })
    .on("focus.updateUrlString", function () {
      $(document).on("keyup.updateUrlString", function (e) {
        if (e.which === 13) updateURL(urlStringTextInput, urlCard);
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
        if (e.which === 13) hideAndResetUpdateURLStringForm(urlCard);
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

function setFocusEventListenersOnUpdateURLStringInput(urlStringInput, urlCard) {
  urlStringInput.offAndOn("focus.updateURLStringFocus", function () {
    $(document).offAndOn("keyup.updateURLStringFocus", function (e) {
      switch (e.which) {
        case 13:
          // Handle enter key pressed
          updateURL(urlStringInput, urlCard);
          break;
        case 27:
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
