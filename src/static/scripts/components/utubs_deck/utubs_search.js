// Takes a user input into the UTub search field and returns an array of UTub ids that have names that contain the user's input as a substring
function filterUTubs(searchTerm) {
  const UTubSelectors = $(".UTubSelector");

  if (searchTerm === "")
    return Object.values(
      UTubSelectors.map((i) => $(UTubSelectors[i]).attr("utubid")),
    );

  const filteredSelectors = UTubSelectors.filter((i) => {
    const UTubName = $(UTubSelectors[i]).children(".UTubName")[0].innerText;
    if (UTubName === "") {
      // In case UTubName returns empty string for some reason...
      return false;
    }
    return UTubName.toLowerCase().includes(searchTerm);
  });

  return Object.values(
    filteredSelectors.map((i) => $(filteredSelectors[i]).attr("utubid")),
  );
}

// Updates displayed UTub selectors based on the provided array
function updatedUTubSelectorDisplay(filteredUTubIDs) {
  const UTubSelectors = $(".UTubSelector");
  UTubSelectors.each(function (_, UTubSelector) {
    const UTubID = $(UTubSelector).attr("utubid");
    if (!filteredUTubIDs.includes(UTubID)) $(this).hide();
    else $(this).show();
  });
}

function setUTubSelectorSearchEventListener() {
  const wrapper = $("#UTubSearchFilterWrapper");
  const searchIcon = $("#UTubSearchFilterIcon");
  const searchInput = $("#UTubSearchFilterInput");

  searchIcon.offAndOn("click.searchInputExpand", function (e) {
    e.stopPropagation();

    if (!wrapper.hasClass("expanded")) {
      wrapper.addClass("expanded"); // Add class to wrapper
      // Use setTimeout to ensure element is visible before focusing
      setTimeout(() => {
        searchInput.focus();
      }, 50); // Small delay might be needed
    }
  });

  searchInput
    // Use namespacing like in the example (.searchInputEsc)
    .offAndOn("focus.searchInputEsc", function () {
      // When the input gains focus, attach a keyup listener to the document
      $(document).offAndOn("keyup.searchInputEsc", function (e) {
        if (e.which === 27) {
          wrapper.removeClass("expanded");
          searchInput.blur();
        }
      });
    })
    .offAndOn("blur.searchInputEsc", function () {
      $(document).off("keyup.searchInputEsc");

      // Optional: Collapse the input if it's empty when blurred
      // Use a small timeout to allow clicking the icon again without immediate collapse
      setTimeout(function () {
        // Check if input lost focus AND is empty AND is currently expanded
        if (
          !searchInput.is(":focus") &&
          searchInput.val() === "" &&
          wrapper.hasClass("expanded")
        ) {
          wrapper.removeClass("expanded");
        }
      }, 150); // 150ms delay
    })
    .offAndOn("input", function () {
      const searchTerm = $("#UTubSearchFilterInput")[0].value.toLowerCase();
      console.log(searchTerm);
      const filteredUTubIDs = filterUTubs(searchTerm);
      updatedUTubSelectorDisplay(filteredUTubIDs);
    });
}
