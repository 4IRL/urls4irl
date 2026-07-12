import { APP_CONFIG } from "../lib/config.js";
import { $ } from "../lib/globals.js";
import { showURLDeckBannerError } from "./urls/deck.js";

interface LockedUTubErrorResponse {
  message?: string;
}

/**
 * Returns true if the jqXHR failure is a "UTub is locked" 403 whose
 * server-provided message has been surfaced to the user via the standard
 * URL-deck error banner. Lock-guarded fail handlers call this at the top
 * (mirroring `is429Handled`) and early-return on a truthy result so the action
 * failure is explained inline instead of falling through to the generic
 * error-page redirect.
 *
 * Detection keys on the message rather than an error code on purpose: each
 * backend domain assigns its own numeric `UTUB_IS_LOCKED` code (URLErrorCodes
 * uses 8, the UTub/tag/member enums use 3), so no single code identifies the
 * locked state across every operation. The rejected message is uniform —
 * `UTUB_FAILURE.UTUB_IS_LOCKED`, bridged to `APP_CONFIG.strings.UTUB_IS_LOCKED`
 * — so it is the reliable cross-domain signal.
 */
export function isUtubLockedHandled(xhr: JQuery.jqXHR): boolean {
  if (xhr.status !== 403) return false;

  const responseJSON = xhr.responseJSON as LockedUTubErrorResponse | undefined;
  const lockedMessage = APP_CONFIG.strings.UTUB_IS_LOCKED;
  if (!responseJSON || responseJSON.message !== lockedMessage) {
    return false;
  }

  // Dismiss any open confirmation modal so the inline banner is visible;
  // a no-op when no modal is showing (inline-edit ops).
  $("#confirmModal").modal("hide");
  showURLDeckBannerError(lockedMessage);
  return true;
}
