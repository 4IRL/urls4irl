/** U4I UI Interactions **/

const TABLET_WIDTH = 992;
const NAVBAR_TOGGLER = { toggler: null };

$(document).ready(function () {
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
      return true;
    },
  });

  // Prevent form refresh of page on submittal
  $("form").on("submit", function () {
    return false;
  });

  bindSwitchURLKeyboardEventListeners();

  // Provide responsiveness to the custom text input boxes
  const textInputs = $(".text-input");
  let textInput;
  for (let i = 0; i < textInputs.length; i++) {
    textInput = $(textInputs[i]);
    textInput.on("focus", handleFocus);
    textInput.on("blur", handleBlur);
  }

  // Grab toggler for the navbar
  NAVBAR_TOGGLER.toggler = new bootstrap.Collapse("#NavbarNavDropdown", {
    toggle: false,
  });

  // Event listeners when hiding and showing the mobile navbar
  $("#NavbarNavDropdown")
    .on("show.bs.collapse", () => {
      onMobileNavbarOpened();
    })
    .on("hide.bs.collapse", () => {
      onMobileNavbarClosed();
    });
});

function onMobileNavbarOpened() {
  const navbarBackdrop = $(document.createElement("div")).addClass(
    "navbar-backdrop",
  );

  navbarBackdrop.on("click", function () {
    NAVBAR_TOGGLER.toggler.hide();
  });

  setTimeout(function () {
    navbarBackdrop.addClass("navbar-backdrop-show");
  }, 0);

  $(".navbar-brand").addClass("z9999");
  $(".navbar-toggler").addClass("z9999");
  $("#NavbarNavDropdown").addClass("z9999");

  $("#mainNavbar").append(navbarBackdrop);
}

function onMobileNavbarClosed() {
  const navbarBackdrop = $(".navbar-backdrop");
  navbarBackdrop.addClass("navbar-backdrop-fade");

  setTimeout(function () {
    navbarBackdrop.remove();
  }, 300);

  $(".navbar-brand").removeClass("z9999");
  $(".navbar-toggler").removeClass("z9999");
  $("#NavbarNavDropdown").removeClass("z9999");
}

$(window).on("focus", () => {
  const prevFocusedElem = $(".focus");
  if (prevFocusedElem.length === 0) return;
  if (prevFocusedElem.length > 1) {
    // Only one should've been focused before
    prevFocusedElem.removeClass("focus");
    return;
  }
  // Find the first URL card closest to last focused item
  const urlCard = prevFocusedElem.closest(".urlRow");

  if (prevFocusedElem.hasClass("goToUrlIcon")) {
    urlCard.find(".goToUrlIcon").addClass("visible-on-focus").trigger("focus");
  }
});

// Refocus when going to another tab
$(window).on("blur", () => {
  if (document.activeElement !== null) {
    $(document.activeElement).addClass("focus");
    console.log($(document.activeElement));
  }
});

const globalBeforeSend = function (xhr, settings) {
  const csrftoken = $("meta[name=csrf-token]").attr("content");
  if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
    xhr.setRequestHeader("X-CSRFToken", csrftoken);
  }
};

// Keyboard navigation between selected UTubs or URLs
function bindSwitchURLKeyboardEventListeners() {
  $(document).offAndOn("keyup.switchurls", function (e) {
    const keycode = e.keyCode ? e.keyCode : e.which;
    const prev = keycode === 38; // UP
    const next = keycode === 40; // DOWN

    if (!prev && !next) return;
    const selectedURLCard = getSelectedURLCard();

    const allURLs = $(".urlRow");
    const allURLsLength = allURLs.length;
    if (allURLsLength === 0) return;

    if (selectedURLCard === null) {
      // Select first url if none are selected
      selectURLCard($(allURLs[0]));
      return;
    }

    const currentIndex = allURLs.index(selectedURLCard);

    if (prev) {
      if (currentIndex === 0) {
        // Wrap to select the bottom URL instead
        selectURLCard($(allURLs[allURLsLength - 1]));
      } else {
        selectURLCard($(allURLs[currentIndex - 1]));
      }
    }

    if (next) {
      if (currentIndex === allURLsLength - 1) {
        // Wrap to select first URL
        selectURLCard($(allURLs[0]));
      } else {
        selectURLCard($(allURLs[currentIndex + 1]));
      }
    }
  });
}

// To differentiate between the text box types when dynamically creating input text boxes
const INPUT_TYPES = Object.freeze({
  CREATE: Symbol("Create"),
  UPDATE: Symbol("Update"),
});

// General Functions

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
function ajaxCall(type, url, data) {
  return (request = $.ajax({
    type: type,
    url: url,
    data: data,
  }));
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

// Disables buttons
function disable(jqueryObj) {
  $(jqueryObj).prop("disabled", true);
}

// Enables buttons
function enable(jqueryObj) {
  $(jqueryObj).prop("disabled", false);
}

// Enable all child elements to be tabbable
function enableTabbableChildElements(parent) {
  $(parent).find(".tabbable").enableTab();
}

function disableTabbableChildElements(parent) {
  $(parent).find(".tabbable").disableTab();
}

// Fancy text box creation
function makeTextInput(textInputID, type) {
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
      type: "text",
      name: textInputID,
    })
    .addClass(textInputID + type);

  inputLabel.attr({ for: textInputID });

  inputErrorMessage.addClass(textInputID + type + "-error");

  inputInnerContainer.append(inputInputBox).append(inputLabel);

  inputOuterContainer.append(inputInnerContainer).append(inputErrorMessage);

  inputInputBox.on("focus", handleFocus).on("blur", handleBlur);
  inputAndButtonWrap.append(inputOuterContainer);
  return inputAndButtonWrap;
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

function setMobileUIWhenUTubSelectedOrURLNavSelected() {
  $(".panel#leftPanel").addClass("hidden");
  $(".panel#centerPanel").addClass("visible-flex");
  $(".home#toUTubs").removeClass("hidden");
  $(".home#toMembers").removeClass("hidden");
  $(".home#toTags").removeClass("hidden");

  $(".deck#MemberDeck").removeClass("visible-flex");
  $(".deck#TagDeck").removeClass("visible-flex");

  NAVBAR_TOGGLER.toggler.hide();
}

function setMobileUIWhenUTubNotSelectedOrUTubDeleted() {
  $(".home#toUTubs").addClass("hidden");
  $(".home#toMembers").addClass("hidden");
  $(".home#toTags").addClass("hidden");
  $(".home#toURLs").addClass("hidden");

  $(".panel#centerPanel").removeClass("visible-flex");
  $(".deck#MemberDeck").removeClass("visible-flex");
  $(".deck#TagDeck").removeClass("visible-flex");

  $(".deck#UTubDeck").removeClass("hidden");

  NAVBAR_TOGGLER.toggler.hide();
}

function setMobileUIWhenUTubDeckSelected() {
  $(".home#toUTubs").addClass("hidden");
  $(".home#toMembers").removeClass("hidden");
  $(".home#toTags").removeClass("hidden");
  $(".home#toURLs").removeClass("hidden");

  $(".panel#leftPanel").removeClass("hidden");

  $(".panel#centerPanel").removeClass("visible-flex");
  $(".deck#MemberDeck").removeClass("visible-flex");
  $(".deck#TagDeck").removeClass("visible-flex");

  $(".deck#UTubDeck").removeClass("hidden");

  NAVBAR_TOGGLER.toggler.hide();
}

function setMobileUIWhenMemberDeckSelected() {
  $(".home#toMembers").addClass("hidden");
  $(".deck#MemberDeck").addClass("visible-flex").removeClass("hidden");

  $(".panel#leftPanel").removeClass("hidden");
  $(".panel#centerPanel").removeClass("visible-flex");
  $(".deck#UTubDeck").addClass("hidden");
  $(".deck#TagDeck").addClass("hidden");

  $(".home#toUTubs").removeClass("hidden");
  $(".home#toTags").removeClass("hidden");
  $(".home#toURLs").removeClass("hidden");

  NAVBAR_TOGGLER.toggler.hide();
}

function setMobileUIWhenTagDeckSelected() {
  $(".home#toTags").addClass("hidden");
  $(".deck#TagDeck").addClass("visible-flex").removeClass("hidden");

  $(".panel#leftPanel").removeClass("hidden");
  $(".panel#centerPanel").removeClass("visible-flex");
  $(".deck#UTubDeck").addClass("hidden");
  $(".deck#MemberDeck").addClass("hidden");

  $(".home#toUTubs").removeClass("hidden");
  $(".home#toTags").removeClass("hidden");
  $(".home#toURLs").removeClass("hidden");
  $(".home#toMembers").removeClass("hidden");

  NAVBAR_TOGGLER.toggler.hide();
}

function revertMobileUIToFullScreenUI() {
  NAVBAR_TOGGLER.toggler.hide();

  $(".home#toUTubs").addClass("hidden");
  $(".home#toMembers").addClass("hidden");
  $(".home#toTags").addClass("hidden");
  $(".home#toURLs").addClass("hidden");

  $(".panel#centerPanel").removeClass("hidden");
  $(".panel#leftPanel").removeClass("hidden");

  $(".deck#UTubDeck").removeClass("hidden");
  $(".deck#MemberDeck").removeClass("hidden");
  $(".deck#TagDeck").removeClass("hidden");
}

function setUIWhenNoUTubSelected() {
  hideInputs();
  setTagDeckSubheaderWhenNoUTubSelected();
  resetTagDeck();
  setURLDeckWhenNoUTubSelected();
  resetURLDeck();
  setMemberDeckWhenNoUTubSelected();
  resetMemberDeck();
}

// jQuery plugins
(function ($) {
  $.fn.enableTab = function () {
    this.attr({ tabindex: 0 });
    return this;
  };

  $.fn.disableTab = function () {
    this.attr({ tabindex: -1 });
    return this;
  };

  $.fn.offAndOn = function (eventName, callback) {
    this.off(eventName).on(eventName, callback);
    return this;
  };
})(jQuery);
