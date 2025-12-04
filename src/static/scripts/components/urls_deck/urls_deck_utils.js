"use strict";

// Function to count number of URLs in current UTub
function getNumOfURLs() {
  return $(".urlRow").length;
}

// Function to count number of visible URLs in current UTub, after filtering
function getNumOfVisibleURLs() {
  return $(".urlRow[filterable=true]").length;
}

// Keyboard navigation between selected UTubs or URLs
function bindSwitchURLKeyboardEventListeners() {
  $(document).offAndOn("keyup.switchurls", function (e) {
    const prev = e.key === KEYS.ARROW_UP;
    const next = e.key === KEYS.ARROW_DOWN;

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
