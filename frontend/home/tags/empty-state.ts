import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";

// Show the zero-tags empty-state wrapper with subheader text
export function showTagDeckEmptyState(): void {
  $("#noTagsSubheader").text(APP_CONFIG.strings.TAG_DECK_NO_TAGS);
  $("#noTagsEmptyState").removeClass("hidden");
}

// Hide the empty-state wrapper and clear subheader text
export function hideTagDeckEmptyState(): void {
  $("#noTagsSubheader").text("");
  $("#noTagsEmptyState").addClass("hidden");
}
