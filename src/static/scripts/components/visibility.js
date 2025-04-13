"use strict";

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
    const activeElement = $(document.activeElement);

    const urlCard = activeElement.closest(".urlRow");
    if (urlCard.length == 0) {
      activeElement.addClass("focus");
      return;
    }

    urlCard.attr({ urlselected: true });
    enableTabbableChildElements(urlCard);
  }
});
