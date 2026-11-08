import { APP_CONFIG } from "../../lib/config.js";
import { getState } from "../../store/app-store.js";
import { learnPolicyOff } from "../utubs/policy.js";
import { updateUTubOnFindingStaleData } from "../utubs/stale-data.js";
import { announceMemberRowAction, showMemberDeckNotice } from "./notice.js";

// Mirrors UTubMembersErrorCodes.MEMBER_ADD_NOT_ALLOWED (backend/members/constants.py).
export const MEMBER_ADD_NOT_ALLOWED_ERROR_CODE = 7;

type RefusalBody = { errorCode?: number } | undefined;

/** True for the 403 the server sends when the owner turned off member adds. */
export function isMemberAddNotAllowedResponse(xhr: JQuery.jqXHR): boolean {
  const body = xhr.responseJSON as RefusalBody;
  return (
    xhr.status === 403 && body?.errorCode === MEMBER_ADD_NOT_ALLOWED_ERROR_CODE
  );
}

/**
 * Learns from a refused add: writes `members_can_add: false` into the store (the
 * revoke subscription then closes any open combobox), shows the notice, optionally
 * announces the refusal, and reconciles with the server so a stale viewer role is
 * corrected. A batch passes `announce: false` because it writes one combined
 * announcement itself. Nothing is learned for a UTub the viewer already left.
 */
export function learnMemberAddRefused({
  utubID,
  announce,
}: {
  utubID: number;
  announce: boolean;
}): void {
  if (getState().activeUTubID !== utubID) return;
  const message = APP_CONFIG.strings.MEMBER_ADD_NOT_ALLOWED;
  // Deliberately ignores the return value: with no settings loaded nothing can be
  // written, but the 403 is real, so the notice and announcement still apply.
  learnPolicyOff({ utubID, key: "members.members_can_add" });
  showMemberDeckNotice({ message });
  if (announce) announceMemberRowAction({ message, politeness: "assertive" });
  void updateUTubOnFindingStaleData({ utubID });
}
