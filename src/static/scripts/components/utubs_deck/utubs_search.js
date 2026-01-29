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

  searchIcon.offAndOnExact("click.searchInputShow", function (e) {
    wrapper.addClass("visible").removeClass("hidden");
    $("#UTubDeckSubheader").addClass("hidden");
    searchIcon.addClass("hidden");
    searchIconClose.removeClass("hidden");

    setTimeout(() => {
      searchInput.addClass("utub-search-expanded");
    }, 0);

    searchInput.focus();
  });

  searchIconClose.offAndOnExact("click.searchInputClose", function (e) {
    closeUTubSearchAndEraseInput();
    searchInput.removeClass("utub-search-expanded");
  });

  searchInput
    .offAndOn("focus.searchInputEsc", function (e) {
      searchInput.offAndOn("keydown.searchInputEsc", function (e) {
        if (e.key === KEYS.ESCAPE) {
          searchInput.blur();
          closeUTubSearchAndEraseInput();
          searchInput.removeClass("utub-search-expanded");
        }
      });
    })
    .offAndOn("blur.searchInputEsc", function () {
      searchInput.off("keydown.searchInputEsc");
    })
    .offAndOn("input", function () {
      const searchTerm = searchInput.val().toLowerCase();
      if (searchTerm.length < APP_CONFIG.constants.UTUBS_MIN_NAME_LENGTH) {
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
