import type { Schema } from "../../types/api-helpers.d.ts";
import type { SuccessResponse } from "../../types/api-helpers.d.ts";

import { APP_CONFIG } from "../../lib/config.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";

/** ajaxCall's 1000ms default is too short for a write; every call here uses 10s. */
export const INVITE_LINK_TIMEOUT_MS = 10000;

export type InviteLink = Schema<"InviteLinkSchema">;

type GetInviteLinkResponse = SuccessResponse<"getInviteLink">;

/** `InviteLinkErrorCodes.UTUB_IS_LOCKED`, mirrored from the backend constants. */
export const INVITE_LINK_LOCKED_ERROR_CODE = 3;

/**
 * Why a GET failed. `denied` is a 403/404 (the viewer can no longer manage the
 * link; `errorCode` is the response's code when it carried one), `rate_limited`
 * is a 429 the global handler already announced, `failed` is anything else
 * (500, timeout, network, a non-JSON 200).
 */
export type InviteLinkLoadFailure =
  | { kind: "denied"; errorCode: number | null }
  | { kind: "rate_limited" }
  | { kind: "failed" };

function readErrorCode(xhr: JQuery.jqXHR): number | null {
  const body = xhr.responseJSON as { errorCode?: unknown } | undefined;
  return typeof body?.errorCode === "number" ? body.errorCode : null;
}

/**
 * GETs the UTub's invite link. Resolves the link (null when the UTub has none)
 * and rejects with an `InviteLinkLoadFailure`. Writes no store and no DOM.
 */
export function getInviteLink({
  utubID,
}: {
  utubID: number;
}): Promise<InviteLink | null> {
  return new Promise<InviteLink | null>((resolve, reject) => {
    const request = ajaxCall(
      "get",
      APP_CONFIG.routes.getInviteLink(utubID),
      null,
      INVITE_LINK_TIMEOUT_MS,
    );

    request.done((response: GetInviteLinkResponse) => {
      // A 200 that is not the app's JSON (e.g. a followed login redirect) is a
      // failure, never "no link".
      const body = response as { inviteLink?: InviteLink | null } | undefined;
      if (
        typeof body !== "object" ||
        body === null ||
        body.inviteLink === undefined
      ) {
        reject({ kind: "failed" } satisfies InviteLinkLoadFailure);
        return;
      }
      resolve(body.inviteLink);
    });

    request.fail((xhr: JQuery.jqXHR) => {
      if (is429Handled(xhr)) {
        reject({ kind: "rate_limited" } satisfies InviteLinkLoadFailure);
        return;
      }
      if (xhr.status === 403 || xhr.status === 404) {
        reject({
          kind: "denied",
          errorCode: readErrorCode(xhr),
        } satisfies InviteLinkLoadFailure);
        return;
      }
      reject({ kind: "failed" } satisfies InviteLinkLoadFailure);
    });
  });
}
