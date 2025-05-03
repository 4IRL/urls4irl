"use strict";

// To differentiate between the text box types when dynamically creating input text boxes
const METHOD_TYPES = Object.freeze({
  CREATE: Symbol("Create"),
  UPDATE: Symbol("Update"),
});

const INPUT_TYPES = Object.freeze({
  TEXT: Symbol("text"),
  URL: Symbol("url"),
  EMAIL: Symbol("email"),
});

$(document).ready(function () {
  // Prevent form refresh of page on submittal
  $("form").on("submit", function () {
    return false;
  });

  // Provide responsiveness to the custom text input boxes
  const textInputs = $(".text-input");
  let textInput;
  for (let i = 0; i < textInputs.length; i++) {
    textInput = $(textInputs[i]);
    textInput.val("");
    if (textInput.hasClass("search-input")) {
      textInput.on("blur", handleSearchInputBlur);
      continue;
    }
    textInput.on("focus", handleFocus);
    textInput.on("blur", handleBlur);
  }
});

// Handle focus for the text input box
function handleFocus(event) {
  const label = event.target.nextElementSibling;
  label.style.top = "0px";
  label.style.left = "10px";
  label.style.fontSize = "14px";
}

// Handle blur for the text input box
function handleBlur(event) {
  if (event.target.value === "") {
    const label = event.target.nextElementSibling;
    label.style.top = "50%";
    label.style.left = "10px";
    label.style.fontSize = "16px";
  }
}

// Handle blur for the search text input boxes
function handleSearchInputBlur(event) {
  const label = event.target.nextElementSibling;
  event.target.value === "" ? $(label).show() : $(label).hide();
}

// Request user text input by showing the appropriate text input element and await valid input
function showInput(handle) {
  const inputEl = $(handle);
  const inputDiv = inputEl.closest(".createDiv");
  showIfHidden(inputDiv);

  //highlightInput(inputEl);
}

// Highlight the input field. Typically if user requests action that is already displayed
function highlightInput(inputEl) {
  $(inputEl).trigger("focus");
  if (inputEl[0].value) {
    inputEl[0].setSelectionRange(0, inputEl[0].value.length);
  }
}

// Hides any active input fields
function hideInputs() {
  // Show UTub creation instead of UTub form
  if (!isHidden($("#createUTubWrap"))) createUTubHideInput();
  // Show UTub name instead of update UTub name form
  if (isHidden($("#URLDeckHeader"))) updateUTubNameHideInput();
  // Show UTub description instead of update UTub description form
  if (
    isHidden($("#URLDeckSubheader")) &&
    $("#URLDeckSubheader").text().length !== 0
  )
    updateUTubDescriptionHideInput();
  // Show members instead of add member form
  if (isHidden($("#displayMemberWrap"))) createMemberHideInput();
}

// Hide specified input field. Typically done if user successfully completes, or cancels an action
function hideInput(handle) {
  const inputEl = $(handle);
  const inputDiv = inputEl.closest(".createDiv");
  hideIfShown(inputDiv);
}

// Creates update button
function makeUpdateButton(wh) {
  const updateBtn = $(document.createElement("i"));

  // update icon box
  const htmlString =
    '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" class="bi bi-pencil-square updateIcon" viewBox="0 0 16 16" width="' +
    wh +
    '" height="' +
    wh +
    '">' +
    '<path d="M15.502 1.94a.5.5 0 0 1 0 .706L14.459 3.69l-2-2L13.502.646a.5.5 0 0 1 .707 0l1.293 1.293zm-1.75 2.456-2-2L4.939 9.21a.5.5 0 0 0-.121.196l-.805 2.414a.25.25 0 0 0 .316.316l2.414-.805a.5.5 0 0 0 .196-.12l6.813-6.814z"/><path fill-rule="evenodd" d="M1 13.5A1.5 1.5 0 0 0 2.5 15h11a1.5 1.5 0 0 0 1.5-1.5v-6a.5.5 0 0 0-1 0v6a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5v-11a.5.5 0 0 1 .5-.5H9a.5.5 0 0 0 0-1H2.5A1.5 1.5 0 0 0 1 2.5z"/>' +
    "</svg>";

  updateBtn
    .addClass("mx-1 flex-row align-center")
    .attr({
      style: "color: #545454",
    })
    .html(htmlString);

  return updateBtn;
}

// Creates submit button
function makeSubmitButton(wh) {
  const submitBtn = $(document.createElement("i"));

  // Submit checkbox
  const htmlString =
    '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" class="bi bi-check-square-fill submitButton tabbable" viewBox="0 0 16 16" width="' +
    wh +
    '" height="' +
    wh +
    '">' +
    '<path d="M2 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2zm10.03 4.97a.75.75 0 0 1 .011 1.05l-3.992 4.99a.75.75 0 0 1-1.08.02L4.324 8.384a.75.75 0 1 1 1.06-1.06l2.094 2.093 3.473-4.425a.75.75 0 0 1 1.08-.022z"/>' +
    "</svg>";

  submitBtn.addClass("mx-1 my-2 green-clickable").html(htmlString);

  return submitBtn;
}

// Creates cancel button
function makeCancelButton(wh) {
  const cancelBtn = $(document.createElement("i"));

  // Cancel x-box
  const htmlString =
    '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" class="bi bi-x-square-fill cancelButton tabbable" viewBox="0 0 16 16" width="' +
    wh +
    '" height="' +
    wh +
    '">' +
    '<path d="M2 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2zm3.354 4.646L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 1 1 .708-.708"/>' +
    "</svg>";

  cancelBtn.addClass("mx-1 my-2").html(htmlString);

  return cancelBtn;
}

// Fancy text box creation
function makeTextInput(
  textInputID,
  method,
  type = INPUT_TYPES.TEXT.description,
) {
  const inputAndButtonWrap = $(document.createElement("div")).addClass(
    "createDiv flex-row full-width pad-top-5p",
  );
  const inputOuterContainer = $(document.createElement("div")).addClass(
    "text-input-container",
  );
  const inputInnerContainer = $(document.createElement("div")).addClass(
    "text-input-inner-container",
  );
  const inputInputBox = $(document.createElement("input"))
    .addClass("text-input")
    .prop("required", true);
  const inputLabel = $(document.createElement("label")).addClass(
    "text-input-label",
  );
  const inputErrorMessage = $(document.createElement("span")).addClass(
    "text-input-error-message",
  );

  inputInputBox
    .attr({
      type: type,
      name: textInputID,
    })
    .addClass(textInputID + method);

  inputLabel.attr({ for: textInputID });

  inputErrorMessage.addClass(textInputID + method + "-error");

  inputInnerContainer.append(inputInputBox).append(inputLabel);

  inputOuterContainer.append(inputInnerContainer).append(inputErrorMessage);

  inputInputBox.on("focus", handleFocus).on("blur", handleBlur);
  inputAndButtonWrap.append(inputOuterContainer);
  return inputAndButtonWrap;
}

// Disables buttons
function disable(jqueryObj) {
  $(jqueryObj).prop("disabled", true);
}

// Enables buttons
function enable(jqueryObj) {
  $(jqueryObj).prop("disabled", false);
}
