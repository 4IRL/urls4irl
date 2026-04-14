import { $ } from "../../lib/globals.js";
import { KEYS } from "../../lib/constants.js";
import { getSelectedURLCard, selectURLCard } from "./cards/selection.js";

// Function to count number of URLs in current UTub
export function getNumOfURLs(): number {
  return $(".urlRow").length;
}

// Function to count number of visible URLs in current UTub, after filtering
export function getNumOfVisibleURLs(): number {
  return $(".urlRow[filterable=true]").length;
}

// Keyboard navigation between selected UTubs or URLs
export function bindSwitchURLKeyboardEventListeners(): void {
  $(document).offAndOn(
    "keyup.switchurls",
    function (event: JQuery.TriggeredEvent) {
      const prev = event.key === KEYS.ARROW_UP;
      const next = event.key === KEYS.ARROW_DOWN;

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
    },
  );
}
