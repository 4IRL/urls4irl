import type { Schema } from "../../../types/api-helpers.d.ts";

import { isURLCurrentlyVisibleInURLDeck } from "./filtering.js";
import { updateUTubOnFindingStaleData } from "../../utubs/stale-data.js";

// Shared 409 conflict handler for URL create/update.
// When the backend reports a duplicate URL with the offending urlString, and that URL is
// not currently rendered in the URL deck, our local store is stale — trigger a refresh.
export function checkForStaleDataOn409(
  responseJSON: Schema<"ErrorResponse">,
  utubID: number,
): void {
  if (
    responseJSON.urlString != null &&
    !isURLCurrentlyVisibleInURLDeck(responseJSON.urlString)
  ) {
    updateUTubOnFindingStaleData(utubID);
  }
}
