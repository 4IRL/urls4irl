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
  $(".createDiv").each(function () { hideIfShown($(this)) });
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
  if (isHidden(jqueryObj[0])) {
    jqueryObj.show();
  }
}

// Checks jqueryObj display status, and hides it if shown
function hideIfShown(jqueryObj) {
  if (!isHidden(jqueryObj[0])) {
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
      console.log("1 key bound");
      f();
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
// $(document).on("keyup", function (e) {
//   if (e.keyCode === 13) {
//     e.preventDefault();
//     e.target.blur();
//   }
// });
