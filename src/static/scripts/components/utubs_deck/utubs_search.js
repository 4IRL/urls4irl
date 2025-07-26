"use strict";

// Takes a user input into the UTub search field and returns an array of UTub ids that have names that contain the user's input as a substring
function filterUTubs(searchTerm) {
  const utubSelectors = $(".UTubSelector");
  const utubsToHide = [];

  let utubName;
  let utubID;
  let utubSelector;
  for (let i = 0; i < utubSelectors.length; i++) {
    utubSelector = $(utubSelectors[i]);
    utubID = parseInt(utubSelector.attr("utubid"));
    utubName = utubSelector.find(".UTubName").text().toLowerCase();

    if (!utubName.includes(searchTerm)) utubsToHide.push(utubID);
  }
  return utubsToHide;
}

// Updates displayed UTub selectors based on the provided array
function updatedUTubSelectorDisplay(filteredUTubIDsToHide) {
  if (filteredUTubIDsToHide.length === 0) {
    $(".UTubSelector").removeClass("hidden");
    return;
  }
  const hideSet = new Set(filteredUTubIDsToHide);
  const utubSelectors = $(".UTubSelector");

  let utubName;
  let utubID;
  for (let i = 0; i < utubSelectors.length; i++) {
    utubID = parseInt($(utubSelectors[i]).attr("utubid"));
    hideSet.has(utubID)
      ? $(utubSelectors[i]).addClass("hidden")
      : $(utubSelectors[i]).removeClass("hidden");
  }
}

function setUTubSelectorSearchEventListener() {
  const wrapper = $("#SearchUTubWrap");
  const searchIcon = $("#UTubSearchFilterIcon");
  const searchIconClose = $("#UTubSearchFilterIconClose");
  const searchInput = $("#UTubNameSearch");

  searchIcon.offAndOn("click.searchInputShow", function (e) {
    e.stopPropagation();
    wrapper.addClass("visible").removeClass("hidden");
    $("#UTubDeckSubheader").addClass("hidden");
    searchIcon.addClass("hidden");
    searchIconClose.removeClass("hidden");

    setTimeout(() => {
      searchInput.addClass("utub-search-expanded");
    }, 0);

    searchInput.focus();
  });

  searchIconClose.offAndOn("click.searchInputClose", function (e) {
    e.stopPropagation();
    closeUTubSearchAndEraseInput();
    searchInput.removeClass("utub-search-expanded");
  });

  searchInput
    .offAndOn("focus.searchInputEsc", function () {
      $(document).offAndOn("keyup.searchInputEsc", function (e) {
        if (e.which === 27) {
          searchInput.blur();
        }
      });
    })
    .offAndOn("blur.searchInputEsc", function () {
      $(document).off("keyup.searchInputEsc");
    })
    .offAndOn("input", function () {
      const searchTerm = searchInput.val().toLowerCase();
      if (searchTerm.length < CONSTANTS.UTUBS_MIN_NAME_LENGTH) {
        updatedUTubSelectorDisplay([]);
        return;
      }
      const filteredUTubIDsToHide = filterUTubs(searchTerm);
      updatedUTubSelectorDisplay(filteredUTubIDsToHide);
    });
}

function closeUTubSearchAndEraseInput() {
  $("#UTubSearchFilterIconClose").addClass("hidden");
  $("#UTubSearchFilterIcon").removeClass("hidden");
  $("#SearchUTubWrap").addClass("hidden").removeClass("visible");
  $("#UTubDeckSubheader").removeClass("hidden");
  $("#UTubNameSearch").val("");
  $(".UTubSelector").removeClass("hidden");
}
