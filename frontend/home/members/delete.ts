import type { MemberModifiedResponse } from "../../types/member.js";

import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { debug } from "../../lib/debug.js";
import { hideTooltip } from "../../lib/tooltips.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { emit as emitAppEvent, AppEvents } from "../../lib/event-bus.js";
import { isUtubLockedHandled } from "../utub-locked.js";
import { emit } from "../../lib/metrics-client.js";
import { TAG_SHEET_TOGGLE_TRIGGER } from "../../types/metrics-dim-values.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import { closeTagSheet, isTagSheetOpen } from "../tags/sheet.js";
import { setMemberDeckForUTub } from "./deck.js";
import {
  bindMemberRowModalFocusRestore,
  disarmMemberRowModalFocusRestore,
} from "./row-menu.js";
import { announceMemberRowAction, showMemberDeckNotice } from "./notice.js";
import { learnPolicyOff } from "../utubs/policy.js";
import { updateUTubOnFindingStaleData } from "../utubs/stale-data.js";
import { hideInputs } from "../btns-forms.js";
import { getState, setState } from "../../store/app-store.js";
import { deselectAllURLs } from "../urls/cards/selection.js";
import { refreshStackedAdderBadges } from "../urls/cards/adder-badge.js";
import { getNumOfUTubs } from "../utubs/utils.js";
import { applyRowCountDelta } from "../utubs/row-counts.js";
import {
  hideInputsAndUpdateUTubDeck,
  resetUTubDeckIfNoUTubs,
} from "../utubs/deck.js";
import { setUIWhenNoUTubSelected } from "../init.js";

// "remove": the viewer removes another member (owner, or co-owner while allowed).
// "leave": the viewer removes themselves.
export type RemoveIntent = "remove" | "leave";

// Mirrors UTubMembersErrorCodes.CO_OWNER_REMOVE_NOT_ALLOWED (backend/members/constants.py).
export const CO_OWNER_REMOVE_NOT_ALLOWED_ERROR_CODE = 8;

let _memberActionConfirmed: boolean = false;
let _removeMemberIntent: RemoveIntent = "leave";

const log = debug("members");

export function createLeaveUTubAsMemberIcon({
  currentUserID,
  utubID,
}: {
  currentUserID: number;
  utubID: number;
}): void {
  $("#memberSelfBtnDelete").offAndOnExact(
    "click.removeMember",
    function (this: HTMLElement) {
      // The confirmation modal covers this button while a hover tooltip may
      // still be open — hide it first so the bubble cannot linger detached.
      hideTooltip(this);
      hideInputs();
      deselectAllURLs();
      removeMemberShowModal({
        memberID: currentUserID,
        utubID,
        intent: "leave",
      });
    },
  );
}

// Hide confirmation modal for removal of the selected member
function removeMemberHideModal(): void {
  $("#confirmModal").modal("hide");
}

// Show confirmation modal for removal of the selected member from current UTub
export function removeMemberShowModal({
  memberID,
  utubID,
  intent,
}: {
  memberID: number;
  utubID: number;
  intent: RemoveIntent;
}): void {
  const isRemovingAnother = intent === "remove";
  _memberActionConfirmed = false;
  _removeMemberIntent = intent;
  // Leave never inherits a focus restore a cancelled Remove left armed.
  if (!isRemovingAnother) disarmMemberRowModalFocusRestore();
  emit({
    event: isRemovingAnother
      ? UI_EVENTS.UI_MEMBER_REMOVE_OPEN
      : UI_EVENTS.UI_MEMBER_LEAVE_OPEN,
  });

  const modalTitle = isRemovingAnother
    ? "Are you sure you want to remove this member from the UTub?"
    : "Are you sure you want to leave this UTub?";
  const modalBody = isRemovingAnother
    ? `${APP_CONFIG.strings.MEMBER_DELETE_WARNING}`
    : `${APP_CONFIG.strings.MEMBER_LEAVE_WARNING}`;
  const buttonTextDismiss = isRemovingAnother ? "Keep member" : "Stay in UTub";
  const buttonTextSubmit = isRemovingAnother ? "Remove member" : "Leave UTub";

  $("#confirmModalTitle").text(modalTitle);

  $("#confirmModalBody").text(modalBody);

  $("#modalDismiss")
    .addClass("btn btn-secondary")
    .offAndOn("click", function (event: JQuery.TriggeredEvent) {
      event.preventDefault();
      removeMemberHideModal();
    })
    .text(buttonTextDismiss);

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-danger")
    .text(buttonTextSubmit)
    .offAndOn("click", function (event: JQuery.TriggeredEvent) {
      event.preventDefault();
      _memberActionConfirmed = true;
      emit({
        event: isRemovingAnother
          ? UI_EVENTS.UI_MEMBER_REMOVE_CONFIRM
          : UI_EVENTS.UI_MEMBER_LEAVE_CONFIRM,
      });
      removeMember({ memberID, intent, utubID });
    })
    .text(buttonTextSubmit);

  $("#confirmModal").offAndOnExact("hidden.bs.modal.memberAction", function () {
    if (!_memberActionConfirmed) {
      emit({
        event:
          _removeMemberIntent === "remove"
            ? UI_EVENTS.UI_MEMBER_REMOVE_CANCEL
            : UI_EVENTS.UI_MEMBER_LEAVE_CANCEL,
      });
    }
  });

  $("#modalSubmit").prop("disabled", false);
  $("#confirmModal").modal("show");
  $("#modalRedirect").hide();
}

// Handles post request and response for removing a member from current UTub, after confirmation
function removeMember({
  memberID,
  intent,
  utubID,
}: {
  memberID: number;
  intent: RemoveIntent;
  utubID: number;
}): void {
  $("#modalSubmit").prop("disabled", true);

  log("removeMember submitted", { memberID, intent, utubID });

  const postURL = APP_CONFIG.routes.removeMember(utubID, memberID);

  const request = ajaxCall("delete", postURL, []);

  // Handle response
  request.done(function (
    _response: MemberModifiedResponse,
    _textStatus: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    if (xhr.status === 200) {
      if (intent === "remove") {
        removeMemberSuccess(memberID);
      } else {
        leaveUTubSuccess(utubID);
      }
    }
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    removeMemberFail({ xhr, memberID, utubID });
  });
}

function removeMemberSuccess(memberID: number): void {
  // Close modal
  $("#confirmModal").modal("hide");

  setState({
    members: getState().members.filter((member) => member.id !== memberID),
  });
  emitAppEvent(AppEvents.MEMBER_DECK_CHANGED);
  const { activeUTubID } = getState();
  if (activeUTubID !== null) {
    applyRowCountDelta({
      utubID: activeUTubID,
      urlDelta: 0,
      memberDelta: -1,
    });
  }

  // The removed member's URLs are now orphans: switch the remover's rendered
  // attribution badges to "a former member" without rebuilding the deck.
  refreshStackedAdderBadges(memberID);

  const memberListItem = $("span[memberid=" + memberID + "]");
  memberListItem.fadeOut("slow", function () {
    memberListItem.remove();
  });

  setMemberDeckForUTub();

  if (getNumOfUTubs() === 0) {
    resetUTubDeckIfNoUTubs();
  }
}

export function leaveUTubSuccess(utubID: number): void {
  // Close modal
  $("#confirmModal").modal("hide");

  log("leaveUTubSuccess — purging UTub from UTub deck and resetting URL deck", {
    utubID,
    remainingUtubCount: getNumOfUTubs() - 1,
  });

  // No UTub is selected after leaving — clear the active selection so deck
  // resets (and the member-button cleanup) treat it as the no-UTub state.
  setState({ activeUTubID: null });

  // No UTub selected -> UTub deck hides the leave button (and delete) here.
  setUIWhenNoUTubSelected();

  // UTub Deck display updates
  const utubSelector = $(".UTubSelector[utubid=" + utubID + "]");
  utubSelector.fadeOut("slow", function () {
    utubSelector.remove();
    if (getNumOfUTubs() === 0) {
      resetUTubDeckIfNoUTubs();
    } else {
      hideInputsAndUpdateUTubDeck();
    }
  });

  // Consume the tag sheet's own history entry (via history.back()) while it is
  // still on top of the stack, BEFORE the pushState/replaceState pair below —
  // otherwise the sheet's entry is orphaned under the freshly-pushed /home entry.
  if (isTagSheetOpen())
    closeTagSheet({
      returnFocus: false,
      trigger: TAG_SHEET_TOGGLE_TRIGGER.TAP,
    });

  setTimeout(function () {
    window.history.pushState(null, "", "/home");
    window.history.replaceState(null, "", "/home");
  }, 0);
}

type RemoveRefusalBody = { errorCode?: number; message?: string } | undefined;

// The three 403s a stale or refused co-owner Remove can get. Matched by errorCode
// (setting off) or by message (no errorCode). Every other 403 keeps the redirect.
function removeRefusalFor(xhr: JQuery.jqXHR): {
  message: string;
  learnOff: boolean;
} | null {
  if (xhr.status !== 403) return null;
  const body = xhr.responseJSON as RemoveRefusalBody;
  if (body?.errorCode === CO_OWNER_REMOVE_NOT_ALLOWED_ERROR_CODE) {
    return {
      message: APP_CONFIG.strings.CO_OWNER_REMOVE_NOT_ALLOWED,
      learnOff: true,
    };
  }
  if (body?.message === APP_CONFIG.strings.CO_OWNER_CANNOT_REMOVE_CO_OWNER) {
    return {
      message: APP_CONFIG.strings.CO_OWNER_CANNOT_REMOVE_CO_OWNER,
      learnOff: false,
    };
  }
  if (body?.message === APP_CONFIG.strings.INVALID_PERMISSION_TO_REMOVE) {
    return {
      message: APP_CONFIG.strings.INVALID_PERMISSION_TO_REMOVE,
      learnOff: false,
    };
  }
  return null;
}

// Closes the modal and shows the refusal: one notice, one assertive announcement,
// a focus landing on the row (else the deck header), and a reconcile with the
// server so a stale viewer role or target row converges. Never redirects.
function handleRemoveRefusal({
  message,
  learnOff,
  memberID,
  utubID,
}: {
  message: string;
  learnOff: boolean;
  memberID: number;
  utubID: number;
}): void {
  // The kebab may be hidden by the learn below; arm the one-shot restore so focus
  // lands on the row (else the header) when the modal finishes closing.
  bindMemberRowModalFocusRestore(memberID);
  $("#confirmModal").modal("hide");
  if (getState().activeUTubID !== utubID) return;
  if (learnOff) learnPolicyOff({ utubID, key: "members.co_owners_can_remove" });
  showMemberDeckNotice({ message });
  announceMemberRowAction({ message, politeness: "assertive" });
  void updateUTubOnFindingStaleData({ utubID });
}

function removeMemberFail({
  xhr,
  memberID,
  utubID,
}: {
  xhr: JQuery.jqXHR;
  memberID: number;
  utubID: number;
}): void {
  $("#modalSubmit").prop("disabled", false);
  if (is429Handled(xhr)) return;
  if (isUtubLockedHandled(xhr)) return;

  if (
    xhr.status === 403 &&
    xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
  ) {
    // Handle invalid CSRF token error response
    $("body").html(xhr.responseText);
    return;
  }

  const refusal = removeRefusalFor(xhr);
  if (refusal !== null) {
    handleRemoveRefusal({ ...refusal, memberID, utubID });
    return;
  }

  switch (xhr.status) {
    case 400:
    case 403:
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}
