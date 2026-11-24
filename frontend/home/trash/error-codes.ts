import { URLErrorCodes, UTubErrorCodes } from "../../types/error-codes.js";

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
    errorCode ===
    (domain === "url"
      ? URLErrorCodes.NOT_IN_TRASH
      : UTubErrorCodes.NOT_IN_TRASH)
  );
}
