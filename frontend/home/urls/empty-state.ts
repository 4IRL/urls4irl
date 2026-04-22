import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";

// Show the empty-state wrapper with subheader text and button label
export function showURLsEmptyState(): void {
  $("#noURLsSubheader").text(APP_CONFIG.strings.UTUB_NO_URLS);
  $("#urlBtnDeckCreate").text(APP_CONFIG.strings.ADD_URL_BUTTON);
  $("#noURLsEmptyState").removeClass("hidden");
}

// Hide the empty-state wrapper and clear subheader text
export function hideURLsEmptyState(): void {
  $("#noURLsSubheader").text("");
  $("#noURLsEmptyState").addClass("hidden");
}
