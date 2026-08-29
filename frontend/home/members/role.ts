import type { MemberModifiedResponse } from "../../types/member.js";

import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { debug } from "../../lib/debug.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { isUtubLockedHandled } from "../utub-locked.js";
import { emit } from "../../lib/metrics-client.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import { getState, setState } from "../../store/app-store.js";
import { swapMemberRoleInRow } from "./members.js";

const log = debug("members");

// Grant/revoke co-owner. Mirrors delete.ts's confirm-modal + AJAX shape, targeting
// the live PATCH /utubs/<id>/members/<id> endpoint with { member_role }. The 200
// body omits the new role, so the client sets it locally and does a targeted
// per-row swap (the id-keyed deck diff never catches a same-id role flip).

// Hide the shared confirmation modal.
function modifyMemberRoleHideModal(): void {
  $("#confirmModal").modal("hide");
}

// Resolve the role the member will hold after the action (the opposite of their
// current co-owner status).
function targetRoleFor(currentRole: string): string {
  return currentRole === APP_CONFIG.constants.MEMBER_ROLES.CO_CREATOR
    ? APP_CONFIG.constants.MEMBER_ROLES.MEMBER
    : APP_CONFIG.constants.MEMBER_ROLES.CO_CREATOR;
}

// Show the confirm modal for granting/revoking co-owner. Copy is static per-role
// (bridged strings, no {{ username }} templating — DD-22), so no username param is
// threaded here; the success announcement resolves the name from the store.
export function modifyMemberRoleShowModal({
  memberID,
  currentRole,
  utubID,
}: {
  memberID: number;
  currentRole: string;
  utubID: number;
}): void {
  const isRevoke = currentRole === APP_CONFIG.constants.MEMBER_ROLES.CO_CREATOR;

  emit({ event: UI_EVENTS.UI_MEMBER_ROLE_CHANGE_SHOWN });

  const modalTitle = isRevoke
    ? APP_CONFIG.strings.REVOKE_CO_OWNER_TITLE
    : APP_CONFIG.strings.MAKE_CO_OWNER_TITLE;
  const modalBody = isRevoke
    ? APP_CONFIG.strings.REVOKE_CO_OWNER_WARNING
    : APP_CONFIG.strings.MAKE_CO_OWNER_WARNING;
  const buttonTextSubmit = isRevoke
    ? APP_CONFIG.strings.REVOKE_CO_OWNER_ACTION
    : APP_CONFIG.strings.MAKE_CO_OWNER_ACTION;

  $("#confirmModalTitle").text(modalTitle);
  $("#confirmModalBody").text(modalBody);

  $("#modalDismiss")
    .addClass("btn btn-secondary")
    .offAndOn("click", function (event: JQuery.TriggeredEvent) {
      event.preventDefault();
      modifyMemberRoleHideModal();
    })
    .text("Cancel");

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-success")
    .text(buttonTextSubmit)
    .offAndOn("click", function (event: JQuery.TriggeredEvent) {
      event.preventDefault();
      emit({ event: UI_EVENTS.UI_MEMBER_ROLE_CHANGE_CONFIRMED });
      modifyMemberRole({ memberID, currentRole, utubID });
    });

  $("#modalSubmit").prop("disabled", false);
  $("#confirmModal").modal("show");
  $("#modalRedirect").hide();
}

// Handle the PATCH request/response for granting or revoking co-owner, after
// confirmation. CSRF is auto-attached to PATCH globally (no per-call code).
function modifyMemberRole({
  memberID,
  currentRole,
  utubID,
}: {
  memberID: number;
  currentRole: string;
  utubID: number;
}): void {
  // Double-submit guard (mirrors remove).
  $("#modalSubmit").prop("disabled", true);

  const targetRole = targetRoleFor(currentRole);

  log("modifyMemberRole submitted", {
    memberID,
    currentRole,
    targetRole,
    utubID,
  });

  const patchURL = APP_CONFIG.routes.modifyMemberRole(utubID, memberID);
  const request = ajaxCall("patch", patchURL, { member_role: targetRole });

  request.done(function (
    _response: MemberModifiedResponse,
    _textStatus: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    if (xhr.status === 200) {
      modifyMemberRoleSuccess({ memberID, targetRole });
    }
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    modifyMemberRoleFail(xhr);
  });
}

function modifyMemberRoleSuccess({
  memberID,
  targetRole,
}: {
  memberID: number;
  targetRole: string;
}): void {
  modifyMemberRoleHideModal();

  // The 200 body omits the new role — set it locally, then do a targeted per-row
  // re-render (never a full deck rebuild). The map only rewrites the matching
  // member's role in place; the entry is never removed.
  setState({
    members: getState().members.map((member) =>
      member.id === memberID ? { ...member, memberRole: targetRole } : member,
    ),
  });

  swapMemberRoleInRow({ memberID, targetRole });

  // DD-22: resolve the display name from the store (still present after the
  // in-place role update above), rather than threading it through the call chain.
  const memberUsername =
    getState().members.find((member) => member.id === memberID)?.username ?? "";
  // DD-9/DD-19: pick the grant vs revoke complete-sentence template (no hardcoded
  // 'co-owner'/'member' ternary on the copy). DD-21: polite on success.
  const template =
    targetRole === APP_CONFIG.constants.MEMBER_ROLES.CO_CREATOR
      ? APP_CONFIG.strings.MEMBER_ROLE_CHANGE_GRANT_SUCCESS
      : APP_CONFIG.strings.MEMBER_ROLE_CHANGE_REVOKE_SUCCESS;
  $("#MemberRowActionAnnouncement")
    .attr("aria-live", "polite")
    .text(template.replace("{{ username }}", memberUsername));
}

function modifyMemberRoleFail(xhr: JQuery.jqXHR): void {
  $("#modalSubmit").prop("disabled", false);
  if (is429Handled(xhr)) return;
  if (isUtubLockedHandled(xhr)) return;

  if (
    xhr.status === 403 &&
    xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
  ) {
    // Invalid CSRF token — swap in the server-rendered body (mirrors remove).
    $("body").html(xhr.responseText);
    return;
  }

  switch (xhr.status) {
    case 400:
    case 404:
      // These carry actionable server messages (CANNOT_MODIFY_OWNER_ROLE,
      // MEMBER_NOT_IN_UTUB, invalid form) — surface the text via the row-action
      // live region (DD-10/DD-21 assertive), do NOT blind-redirect.
      $("#MemberRowActionAnnouncement")
        .attr("aria-live", "assertive")
        .text(xhr.responseJSON?.message ?? "");
      break;
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}
