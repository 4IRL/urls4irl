/** U4I-related constants **/

const ICON_WIDTH = 30;
const ICON_HEIGHT = ICON_WIDTH;

/** U4I UI Interactions **/

$(document).ready(function () {
  // Dev tracking of click-triggered objects
  $(document).on("click", function (e) {
    console.log($(e.target)[0]);
  });

  $("svg").attr({
    width: ICON_WIDTH,
    height: ICON_HEIGHT,
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

  // Bind esc key (keycode 27) to hide any visible user input createDivs
  $(document).bind("keyup", function (e) {
    if (e.which == 27) {
      hideInputs();
    }
  });

  // Keyboard navigation between selected UTubs or URLs
  $(document).on("keyup", function (e) {
    let keycode = e.keyCode ? e.keyCode : e.which;
    let prev = keycode == 37 || keycode == 38; // UP and LEFT keys
    let next = keycode == 39 || keycode == 40; // DOWN and RIGHT keys

    if ($("#URLFocusRow").length > 0) {
      // Some URL is selected, switch URLs

      let UPRcards = $("#UPRRow").children(".cardCol").length;
      let LWRcards = $("#LWRRow").children(".cardCol").length;

      if (prev && UPRcards > 0) {
        // User wants to highlight previous URL
        let cardCol = $($("#UPRRow").children(".cardCol")[UPRcards - 1]);
        toggleSelectedURL($(cardCol[0].children).attr("urlid"));
      } else if (next && LWRcards > 0) {
        // User wants to highlight next URL
        let cardCol = $($("#LWRRow").children(".cardCol")[0]);
        toggleSelectedURL($(cardCol[0].children).attr("urlid"));
      }
    } else {
      // No URL selected, switch UTubs
    }
  });

  // Navbar animation
  $(".first-button").on("click", function () {
    $(".animated-icon1").toggleClass("open");
  });
  $(".second-button").on("click", function () {
    $(".animated-icon2").toggleClass("open");
  });
  $(".third-button").on("click", function () {
    $(".animated-icon3").toggleClass("open");
  });
});

// General Functions

// Request user text input by showing the appropriate text input element and await valid input
function showInput(handle) {
  let inputEl = $("#" + handle);
  let inputDiv = inputEl.closest(".createDiv");
  showIfHidden(inputDiv);
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
  $(".createDiv").each(function () {
    hideIfShown($(this));
  });
  // editURLHideInput();
  // editUTubNameHideInput();
  // editUTubDescriptionHideInput();
}

// Hide specified input field. Typically done if user successfully completes, or cancels an action
function hideInput(handle) {
  let inputEl = $("#" + handle);
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

// Where el is the DOM element you'd like to test for visibility
function isHidden(el) {
  return el.offsetParent === null;
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

// Bind key to function... doesn't work universally, just in modals, as of 12/29
function bindKeyToFunction(f, keyTarget) {
  $(document).on("keypress", function (e) {
    if (e.which == keyTarget) {
      f();
    }
  });
}

// Bind key to function... doesn't work universally, just in modals, as of 01/03. Optional parameter...may be a better way to define like in MATLAB f(f, ~, keyTarget) when unused
function bindKeyToFunction(f, input, keyTarget) {
  $(document).on("keypress", function (e) {
    if (e.which == keyTarget) {
      f(input);
    }
  });
}

// Unbind enter key
function unbindEnter() {
  $(document).unbind("keypress", function (e) {
    if (e.which == 13) {
      return;
    }
  });
}

// Creates edit button
function makeEditButton() {
  const editBtn = document.createElement("i");
  const svg = document.createElement("svg");
  const path1 = document.createElement("path");
  const path2 = document.createElement("path");

  
  
  $(svg).append(path1);
  $(svg).append(path2);
  $(editBtn).append(svg);

  return editBtn
}

// I'd like a universal function to bind enter key but it doesn't work...01/03/24
// $(document).on("keyup", function (e) {
//   if (e.keyCode === 13) {
//     e.preventDefault();
//     e.target.blur();
//   }
// });

function displayState0() {
  hideInputs();
  displayState0TagDeck();
  resetTagDeck();
  displayState0URLDeck();
  resetURLDeck();
  displayState0UTubDescriptionDeck();
  displayState0UserDeck();
  resetUserDeck();
}

function displayState1() {
  displayState1UTubDeck(null, null);
  displayState1TagDeck();
  displayState1URLDeck();
  displayState1UTubDescriptionDeck();
  displayState1UserDeck();
}
