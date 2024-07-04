/** U4I UI Interactions **/

$(document).ready(function () {
  // Dev tracking of click-triggered objects
  $(document).on("click", function (e) {
    console.log($(e.target)[0]);
  });

  // CSRF token initialization for non-modal POST requests
  let csrftoken = $("meta[name=csrf-token]").attr("content");
  $.ajaxSetup({
    beforeSend: function (xhr, settings) {
      if (
        !/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) &&
        !this.crossDomain
      ) {
        xhr.setRequestHeader("X-CSRFToken", csrftoken);
      }
    },
  });

  // Prevent form refresh of page on submittal
  $("form").on("submit", function () {
    return false;
  });

  // Provide responsiveness to the custom text input boxes
  const textInputs = $(".text-input");
  let textInput;
  for (let i = 0; i < textInputs.length; i++) {
    textInput = $(textInputs[i]);
    textInput.on("focus", handleFocus);
    textInput.on("blur", handleBlur);
  }
});

// Keyboard navigation between selected UTubs or URLs
function bindURLKeyboardEventListenersWhenUpdatesNotOccurring() {
  $(document)
    .off("keyup.switchurls")
    .on("keyup.switchurls", function (e) {
      if (isNaN(getSelectedURLID())) return;
      e.stopPropagation();
      const keycode = e.keyCode ? e.keyCode : e.which;
      const prev = keycode === 37 || keycode === 38; // UP and LEFT keys
      const next = keycode === 39 || keycode === 40; // DOWN and RIGHT keys

      const UPRCards = $("#UPRRow").children(".cardCol");
      const LWRCards = $("#LWRRow").children(".cardCol");

      const UPRcardsCount = UPRCards.length;
      const LWRcardsCount = LWRCards.length;

      if (prev) {
        let urlID;
        if (UPRcardsCount > 0) {
          // User wants to highlight previous URL
          const cardCol = $($(UPRCards)[UPRcardsCount - 1]);
          urlID = $(cardCol[0].children).attr("urlid");
        } else {
          // Highlight last card in lower row
          const cardCol = $($(LWRCards)[LWRcardsCount - 1]);
          urlID = $(cardCol[0].children).attr("urlid");
        }
        toggleSelectedURL(urlID);
        bindEscapeToUnselectURL(urlID);
      } else if (next) {
        let urlID;
        if (LWRcardsCount === 0) {
          // User hit the last URL and should cycle back
          const cardCol = $($(UPRCards)[0]);
          urlID = $(cardCol[0].children).attr("urlid");
        } else {
          // User has another URL in the LWRRow to select
          const cardCol = $($(LWRCards)[0]);
          urlID = $($(cardCol)[0].children).attr("urlid");
        }
        toggleSelectedURL(urlID);
        bindEscapeToUnselectURL(urlID);
      }

      //REHCH Goal: No URL selected, switch UTubs
    });
}

function unbindURLKeyboardEventListenersWhenUpdatesOccurring() {
  $(document).off("keyup.switchurls");
}

function unbindEscapeKey() {
  $(document).unbind("keyup.27");
}

// General Functions

// Request user text input by showing the appropriate text input element and await valid input
function showInput(handle) {
  let inputEl = $(handle);
  let inputDiv = inputEl.closest(".createDiv");
  showIfHidden(inputDiv);

  highlightInput(inputEl);
}

// Highlight the input field. Typically if user requests action that is already displayed
function highlightInput(inputEl) {
  inputEl.focus();
  if (inputEl[0].value) {
    inputEl[0].setSelectionRange(0, inputEl[0].value.length);
  }
}

// Hides any active input fields
function hideInputs() {
  // Show UTub creation instead of UTub form
  if (!isHidden($("#createUTubWrap"))) addUTubHideInput();
  // Show UTub name instead of edit UTub name form
  if (isHidden($("#URLDeckHeader"))) updateUTubNameHideInput();
  // Show UTub description instead of edit UTub description form
  if (
    isHidden($("#URLDeckSubheader")) &&
    $("#URLDeckSubheader").text().length !== 0
  )
    updateUTubDescriptionHideInput();
  // Show members instead of add member form
  if (isHidden($("#displayMemberWrap"))) addMemberHideInput();

  /*
  $(".createDiv").each(function () {
    hideIfShown($(this));
  });
  */
  // editURLHideInput();
  // editUTubNameHideInput();
  // editUTubDescriptionHideInput();
}

// Hide specified input field. Typically done if user successfully completes, or cancels an action
function hideInput(handle) {
  let inputEl = $(handle);
  let inputDiv = inputEl.closest(".createDiv");
  hideIfShown(inputDiv);
}

// Clears any active input fields
function clearInputs() {
  $(".userInput").val("");
}

// Clear specified input field. Typically done if user successfully completes, or cancels an action
function clearInput(handle) {
  $("#" + handle).val("");
}

function isEmpty(el) {
  return !$.trim(el.html());
}

// Where el is the DOM element you'd like to test for visibility
function isHidden(el) {
  return el.offsetParent === null || $(el).get(0).offsetParent === null;
}

// Checks jqueryObj display status, and shows it if hidden
function showIfHidden(jqueryObj) {
  for (let i = 0; i < jqueryObj.length; i++)
    if (isHidden(jqueryObj[i])) {
      jqueryObj.show();
    }
}

// Checks jqueryObj display status, and hides it if shown
function hideIfShown(jqueryObj) {
  for (let i = 0; i < jqueryObj.length; i++)
    if (!isHidden(jqueryObj[i])) {
      jqueryObj.hide();
    }
}

// AJAX request
function AJAXCall(type, url, data) {
  return (request = $.ajax({
    type: type,
    url: url,
    data: data,
  }));
}

// Creates edit button
function makeUpdateButton(wh) {
  const editBtn = document.createElement("i");

  // Edit icon box
  let htmlString =
    '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" class="bi bi-pencil-square editIcon" viewBox="0 0 16 16" width="' +
    wh +
    '" height="' +
    wh +
    '">' +
    '<path d="M15.502 1.94a.5.5 0 0 1 0 .706L14.459 3.69l-2-2L13.502.646a.5.5 0 0 1 .707 0l1.293 1.293zm-1.75 2.456-2-2L4.939 9.21a.5.5 0 0 0-.121.196l-.805 2.414a.25.25 0 0 0 .316.316l2.414-.805a.5.5 0 0 0 .196-.12l6.813-6.814z"/><path fill-rule="evenodd" d="M1 13.5A1.5 1.5 0 0 0 2.5 15h11a1.5 1.5 0 0 0 1.5-1.5v-6a.5.5 0 0 0-1 0v6a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5v-11a.5.5 0 0 1 .5-.5H9a.5.5 0 0 0 0-1H2.5A1.5 1.5 0 0 0 1 2.5z"/>' +
    "</svg>";

  $(editBtn)
    .addClass("mx-1 flex-row align-center")
    .attr({
      style: "color: #545454",
    })
    .html(htmlString);

  return editBtn;
}

// Creates submit button
function makeSubmitButton(wh) {
  const submitBtn = document.createElement("i");

  // Submit checkbox
  let htmlString =
    '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" class="bi bi-check-square-fill" viewBox="0 0 16 16" width="' +
    wh +
    '" height="' +
    wh +
    '">' +
    '<path d="M2 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2zm10.03 4.97a.75.75 0 0 1 .011 1.05l-3.992 4.99a.75.75 0 0 1-1.08.02L4.324 8.384a.75.75 0 1 1 1.06-1.06l2.094 2.093 3.473-4.425a.75.75 0 0 1 1.08-.022z"/>' +
    "</svg>";

  $(submitBtn).addClass("mx-1 green-clickable").html(htmlString);

  return submitBtn;
}

// Creates cancel button
function makeCancelButton(wh) {
  const cancelBtn = document.createElement("i");

  // Cancel x-box
  htmlString =
    '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" class="bi bi-x-square-fill cancelButton" viewBox="0 0 16 16" width="' +
    wh +
    '" height="' +
    wh +
    '">' +
    '<path d="M2 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2zm3.354 4.646L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 1 1 .708-.708"/>' +
    "</svg>";

  $(cancelBtn).addClass("mx-1").html(htmlString);

  return cancelBtn;
}

// Disables buttons
function disable(jqueryObj) {
  $(jqueryObj).prop("disabled", true);
}

// Enables buttons
function enable(jqueryObj) {
  $(jqueryObj).prop("disabled", false);
}

// Fancy text box creation
function makeTextInput(textInputID) {
  const inputContainer = document.createElement("div");
  const inputInputBox = document.createElement("input");
  const inputLabel = document.createElement("label");
  const inputErrorMessage = document.createElement("span");

  $(inputInputBox)
    .addClass("text-input")
    .attr({
      type: "text",
      id: textInputID,
      name: textInputID,
    })
    .prop("required", true);

  $(inputLabel)
    .addClass("text-input-label")
    .attr({
      for: textInputID,
    })
    .text(textInputID);

  $(inputErrorMessage)
    .addClass("text-input-error-message")
    .attr({
      id: textInputID + "-error",
    })
    .text("Error check");

  $(inputContainer)
    .addClass("text-input-container")
    .append(inputInputBox)
    .append(inputLabel)
    .append(inputErrorMessage);

  $(inputInputBox).on("focus", handleFocus).on("blur", handleBlur);
  $(".text-input").forEach((textInput) => {
    textInput.on("focus", handleFocus);
    textInput.on("blur", handleBlur);
  });

  return inputContainer;
}

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

function displayState0() {
  hideInputs();
  displayState0TagDeck();
  resetTagDeck();
  displayState0URLDeck();
  resetURLDeck();
  displayState0MemberDeck();
  resetMemberDeck();
}

function displayState1() {
  displayState1UTubDeck(null, null);
  displayState1TagDeck();
  displayState1URLDeck();
  displayState1MemberDeck();
}
