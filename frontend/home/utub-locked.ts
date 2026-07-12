import type { Schema } from "../types/api-helpers.d.ts";

import { $ } from "../lib/globals.js";
import { showURLDeckBannerError } from "./urls/deck.js";

/**
 * Mirrors backend `UTubErrorCodes.UTUB_IS_LOCKED` (backend/utubs/constants.py).
 * The generated OpenAPI types expose `UTubErrorCodes` only as a numeric-literal
 * type (`1 | 2 | 3`), not a runtime value, so there is nothing runtime to
 * import; typing this constant as `Schema<"UTubErrorCodes">` keeps it tethered
 * to the generated union — TypeScript rejects any value outside the spec.
 */
const UTUB_IS_LOCKED_ERROR_CODE: Schema<"UTubErrorCodes"> = 3;

interface LockedUTubErrorResponse {
  errorCode?: Schema<"UTubErrorCodes">;
  message?: string;
}

/**
 * Returns true if the jqXHR failure is a "UTub is locked" 403 whose
 * server-provided message has been surfaced to the user via the standard
 * URL-deck error banner. Lock-guarded fail handlers call this at the top
 * (mirroring `is429Handled`) and early-return on a truthy result so the action
 * failure is explained inline instead of falling through to the generic
 * error-page redirect.
 */
export function isUtubLockedHandled(xhr: JQuery.jqXHR): boolean {
  if (xhr.status !== 403) return false;

  const responseJSON = xhr.responseJSON as LockedUTubErrorResponse | undefined;
  if (!responseJSON || responseJSON.errorCode !== UTUB_IS_LOCKED_ERROR_CODE) {
    return false;
  }

  // Dismiss any open confirmation modal so the inline banner is visible;
  // a no-op when no modal is showing (inline-edit ops).
  $("#confirmModal").modal("hide");
  showURLDeckBannerError(responseJSON.message ?? "");
  return true;
}
