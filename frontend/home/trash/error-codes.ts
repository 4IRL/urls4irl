/**
 * Backend error codes the Trash UI branches on. Pinned to the backend by
 * `tests/unit/test_trash_error_codes.py`, so a renumbering fails CI.
 */

// backend/urls/constants.py URLErrorCodes.NOT_IN_TRASH
export const URL_NOT_IN_TRASH = 11;
// backend/utubs/constants.py UTubErrorCodes.NOT_IN_TRASH
export const UTUB_NOT_IN_TRASH = 4;
// backend/urls/constants.py URLErrorCodes.URL_ALREADY_IN_DESTINATION
export const URL_ALREADY_IN_DESTINATION = 14;
// backend/urls/constants.py URLErrorCodes.DESTINATION_REQUIRED
export const URL_DESTINATION_REQUIRED = 12;
// backend/urls/constants.py URLErrorCodes.INVALID_DESTINATION
export const URL_INVALID_DESTINATION = 13;

export type TrashDomain = "url" | "utub";

type ErrorCodeBody = { errorCode?: number };

/** True for the 404 the Trash endpoints return when the item already left Trash. */
export function isNotInTrash({
  xhr,
  domain,
}: {
  xhr: JQuery.jqXHR;
  domain: TrashDomain;
}): boolean {
  if (xhr.status !== 404) return false;
  const errorCode = (xhr.responseJSON as ErrorCodeBody | undefined)?.errorCode;
  return (
    errorCode === (domain === "url" ? URL_NOT_IN_TRASH : UTUB_NOT_IN_TRASH)
  );
}
