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

const VISIBLE_URL_SELECTOR = ".urlRow[filterable=true]:not([searchable=false])";

export function bindSwitchURLKeyboardEventListeners(): void {
  $(document).offAndOn(
    "keyup.switchurls",
    function (event: JQuery.TriggeredEvent) {
      const prev = event.key === KEYS.ARROW_UP;
      const next = event.key === KEYS.ARROW_DOWN;

      if (!prev && !next) return;

      const visibleURLs = $(VISIBLE_URL_SELECTOR);
      const visibleCount = visibleURLs.length;
      if (visibleCount === 0) return;

      const selectedURLCard = getSelectedURLCard();

      if (selectedURLCard === null) {
        selectURLCard($(visibleURLs[0]));
        return;
      }

      const currentIndex = visibleURLs.index(selectedURLCard);

      if (currentIndex === -1) {
        selectURLCard($(visibleURLs[0]));
        return;
      }

      if (visibleCount === 1) return;

      if (prev) {
        const prevIndex =
          currentIndex === 0 ? visibleCount - 1 : currentIndex - 1;
        selectURLCard($(visibleURLs[prevIndex]));
      }

      if (next) {
        const nextIndex =
          currentIndex === visibleCount - 1 ? 0 : currentIndex + 1;
        selectURLCard($(visibleURLs[nextIndex]));
      }
    },
  );
}
