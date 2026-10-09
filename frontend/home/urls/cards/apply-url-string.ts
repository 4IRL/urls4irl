import type { SuccessResponse } from "../../../types/api-helpers.d.ts";
import type { UtubUrlItem } from "../../../types/url.js";

import { emit } from "../../../lib/metrics-client.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";
import {
  SEARCH_ACTIVE,
  URL_ACCESS_TRIGGER,
} from "../../../types/metrics-dim-values.js";
import { getState, setState } from "../../../store/app-store.js";
import { isURLSearchActive, getActiveTagCount } from "../url-context.js";
import { accessLink } from "./access.js";
import { copyURLString } from "./copy.js";

type UpdateUrlStringResponse = SuccessResponse<"updateUrl">;

// Leaf module (no card-flow imports) so both the edit save and the trim Undo can
// share it without an import cycle.
// Writes a saved URL string into the store and the card (href, text and the
// access/go-to/copy bindings).
export function applyUpdatedURLString({
  response,
  urlCard,
}: {
  response: UpdateUrlStringResponse;
  urlCard: JQuery;
}): void {
  const updatedURLString = response.URL.urlString;

  setState({
    urls: getState().urls.map((existingUrl: UtubUrlItem) =>
      existingUrl.utubUrlID === response.URL.utubUrlID
        ? {
            ...existingUrl,
            urlString: response.URL.urlString,
            urlTitle: response.URL.urlTitle,
            utubUrlTagIDs: response.URL.urlTags.map(
              (urlTag) => urlTag.utubTagID,
            ),
          }
        : existingUrl,
    ),
  });

  // Update URL body with latest published data
  urlCard
    .find(".urlString")
    .attr({ href: updatedURLString })
    .text(updatedURLString);

  // Update URL options. Dimensions (search_active, active_tag_count) are read
  // at click time so values reflect the deck state at the moment the user
  // activates the rebound button, not at save time.
  urlCard.find(".urlBtnAccess").offAndOnExact("click", function () {
    emit({
      event: UI_EVENTS.UI_URL_ACCESS,
      trigger: URL_ACCESS_TRIGGER.MAIN_BUTTON,
      search_active: isURLSearchActive()
        ? SEARCH_ACTIVE.TRUE
        : SEARCH_ACTIVE.FALSE,
      active_tag_count: getActiveTagCount(),
    });
    accessLink(updatedURLString);
  });

  urlCard.find(".goToUrlIcon").offAndOnExact("click", function () {
    emit({
      event: UI_EVENTS.UI_URL_ACCESS,
      trigger: URL_ACCESS_TRIGGER.CORNER_BUTTON,
      search_active: isURLSearchActive()
        ? SEARCH_ACTIVE.TRUE
        : SEARCH_ACTIVE.FALSE,
      active_tag_count: getActiveTagCount(),
    });
    accessLink(updatedURLString);
  });

  urlCard
    .find(".urlBtnCopy")
    .offAndOnExact("click", function (this: HTMLElement) {
      copyURLString(updatedURLString, this);
    });
}
