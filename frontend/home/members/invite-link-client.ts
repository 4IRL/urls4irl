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

/** `InviteLinkErrorCodes` mirrored from the backend: link not found, live link exists. */
export const INVITE_LINK_NOT_FOUND_ERROR_CODE = 1;
export const INVITE_LINK_LIVE_EXISTS_ERROR_CODE = 4;
/** Dead-link update (PATCH on a link that stopped working) and use limit below the joined count. */
export const INVITE_LINK_DEAD_UPDATE_ERROR_CODE = 5;
export const INVITE_LINK_USES_BELOW_JOINED_ERROR_CODE = 6;

const MS_PER_DAY = 86_400_000;

/**
 * Why a create / replace / revoke failed. `rate_limited` is a 429 the global
 * handler already announced; `csrf` is a 403 whose body is the HTML error page;
 * `error` is everything else (with the status and the response's `errorCode`
 * when it carried one; status 0 covers a timeout or network failure).
 */
export type InviteLinkMutationFailure =
  | { kind: "rate_limited" }
  | { kind: "csrf"; html: string }
  | { kind: "error"; status: number; errorCode: number | null };

/**
 * The smallest of 1/7/30 days that is at least the time remaining on `link`.
 * Rounding up is intended (a new link may outlive the old one).
 */
export function replaceExpiryDays({
  expiresAt,
  now,
}: {
  expiresAt: string;
  now: number;
}): 1 | 7 | 30 {
  const remainingDays = (new Date(expiresAt).getTime() - now) / MS_PER_DAY;
  if (remainingDays <= 1) return 1;
  if (remainingDays <= 7) return 7;
  return 30;
}

function sendMutation<Result>({
  method,
  url,
  body,
  read,
}: {
  method: "post" | "patch" | "delete";
  url: string;
  body: Record<string, unknown> | null;
  read: (response: unknown) => Result | null;
}): Promise<Result> {
  return new Promise<Result>((resolve, reject) => {
    const request = ajaxCall(method, url, body, INVITE_LINK_TIMEOUT_MS);

    request.done((response: unknown) => {
      const result = read(response);
      if (result === null) {
        reject({
          kind: "error",
          status: 200,
          errorCode: null,
        } satisfies InviteLinkMutationFailure);
        return;
      }
      resolve(result);
    });

    request.fail((xhr: JQuery.jqXHR) => {
      if (is429Handled(xhr)) {
        reject({ kind: "rate_limited" } satisfies InviteLinkMutationFailure);
        return;
      }
      if (
        xhr.status === 403 &&
        xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
      ) {
        reject({
          kind: "csrf",
          html: xhr.responseText,
        } satisfies InviteLinkMutationFailure);
        return;
      }
      reject({
        kind: "error",
        status: xhr.status,
        errorCode: readErrorCode(xhr),
      } satisfies InviteLinkMutationFailure);
    });
  });
}

function readLink(response: unknown): InviteLink | null {
  const body = response as { inviteLink?: InviteLink | null } | undefined;
  if (typeof body !== "object" || body === null) return null;
  return body.inviteLink ?? null;
}

/** POSTs a new invite link with both settings (`maxUses: null` is unlimited). */
export function createInviteLink({
  utubID,
  expiresInDays,
  maxUses,
}: {
  utubID: number;
  expiresInDays: number;
  maxUses: number | null;
}): Promise<InviteLink> {
  return sendMutation({
    method: "post",
    url: APP_CONFIG.routes.createInviteLink(utubID),
    body: { expires_in_days: expiresInDays, max_uses: maxUses },
    read: readLink,
  });
}

/** POSTs a replacement for the live link, sending both settings. */
export function replaceInviteLink({
  utubID,
  expiresInDays,
  maxUses,
}: {
  utubID: number;
  expiresInDays: number;
  maxUses: number | null;
}): Promise<InviteLink> {
  return sendMutation({
    method: "post",
    url: APP_CONFIG.routes.replaceInviteLink(utubID),
    body: { expires_in_days: expiresInDays, max_uses: maxUses },
    read: readLink,
  });
}

/** Exactly one setting per save; `max_uses: null` is Unlimited. */
export type InviteLinkUpdateBody =
  | { expires_in_days: number }
  | { max_uses: number | null };

/** PATCHes one setting of the live link; the response is the saved link. */
export function updateInviteLink({
  utubID,
  body,
}: {
  utubID: number;
  body: InviteLinkUpdateBody;
}): Promise<InviteLink> {
  return sendMutation({
    method: "patch",
    url: APP_CONFIG.routes.updateInviteLink(utubID),
    body,
    read: readLink,
  });
}

/** DELETEs the UTub's invite link. */
export function revokeInviteLink({
  utubID,
}: {
  utubID: number;
}): Promise<true> {
  return sendMutation({
    method: "delete",
    url: APP_CONFIG.routes.revokeInviteLink(utubID),
    body: null,
    read: () => true as const,
  });
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
