import type { MemberItem } from "../../types/member.js";

import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { debug } from "../../lib/debug.js";
import { applyDeckDiff } from "../../logic/apply-deck-diff.js";
import { getState } from "../../store/app-store.js";
import { emit, on, AppEvents } from "../../lib/event-bus.js";
import { cancelCoMemberCandidatesFetch } from "./co-member-fetch.js";
import { hideAndResetMemberCombobox } from "./member-combobox.js";
import {
  createMemberBadge,
  createOwnerBadge,
  swapMemberRoleInRow,
} from "./members.js";
import { setupShowCreateMemberFormEventListeners } from "./create.js";
import { createLeaveUTubAsMemberIcon } from "./delete.js";
import {
  setMemberSelectorSearchEventListener,
  setMemberNameFilterToggleListeners,
  showMemberFilterBar,
  hideMemberFilterBar,
  resetMemberFilter,
  reapplyMemberFilter,
  applyAlternatingMemberBackground,
} from "./search.js";

const log = debug("members");

// Clear the Member Deck
export function resetMemberDeck(): void {
  $("#UTubOwner").empty();
  $("#listMembers").empty();
  $("#MemberSearchNoResults").addClass("hidden").text("");
  $("#MemberSearchAnnouncement").text("");
  resetMemberFilter();
  hideMemberFilterBar();
  // Drop any co-member add candidates so they never leak across UTubs; the next
  // add-UI open re-hydrates them via loadCoMemberCandidates for the new UTub.
  // Abort any in-flight fetch first — otherwise a response for the prior UTub
  // could resolve after this clear and repopulate the slice for the new UTub.
  cancelCoMemberCandidatesFetch();
  // Tear down any open/staged add-member combobox so a UTub switch never strands
  // staged chips or in-flight combobox state; this also clears the co-member
  // slice + loaded flag, so no separate setState clear is needed here.
  hideAndResetMemberCombobox();
}

// Update member deck on asynchronous update, either due to stale data or refresh
export function updateMemberDeck(
  newMembers: MemberItem[],
  isCurrentUserOwner: boolean,
  utubID: number,
): void {
  log("updateMemberDeck — applying member deck diff", {
    utubID,
    oldCount: getState().members.length,
    newCount: newMembers.length,
    isCurrentUserOwner,
  });
  // DD-20: capture the pre-diff members once (nothing mutates state between this
  // read and applyDeckDiff, so one read is safe to reuse for oldItems + the
  // role map). Build an id→role map so the updateElement callback can skip rows
  // whose role did not actually change — applyDeckDiff's toUpdate set is
  // id-membership-based, not field-diffed, so every id present in both snapshots
  // would otherwise trigger a needless swap.
  const oldMembers = getState().members;
  const oldRoleByID = new Map(
    oldMembers.map((member) => [member.id, member.memberRole]),
  );

  applyDeckDiff<MemberItem>({
    oldItems: oldMembers,
    newItems: newMembers,
    getID: (member) => member.id,
    removeElement: (memberID) =>
      $(".member[memberid=" + memberID + "]").remove(),
    addElement: (member) => {
      $("#listMembers").append(
        createMemberBadge({
          memberID: member.id,
          username: member.username,
          memberRole: member.memberRole,
          isCurrentUserOwner,
          utubID,
        }),
      );
    },
    // DD-7: a role flip arriving via STALE_DATA_DETECTED/refresh (not just the
    // local grant/revoke success path) gets the same targeted swap. Uses the
    // exact helper the Step-4 success handler uses so the paths never drift.
    updateElement: (id, member) => {
      if (oldRoleByID.get(id) === member.memberRole) return;
      swapMemberRoleInRow({ memberID: id, targetRole: member.memberRole });
    },
  });

  reapplyMemberFilter();

  // Keep the owner-only transfer trigger's visibility in sync when a background
  // membership change (STALE_DATA_DETECTED/refresh) crosses the 0↔1 non-owner
  // threshold — e.g. the last non-owner member leaving must hide the button
  // without waiting for the next full UTUB_SELECTED. utubOwnerID comes from
  // state (not a param here); newMembers is always a real array.
  setMemberDeckTransferOwnerBtn({
    members: newMembers,
    utubOwnerUserID: getState().utubOwnerID,
    isCurrentUserOwner,
  });
}

// Build center panel URL list for selectedUTub
export function setMemberDeckOnUTubSelected(
  dictMembers: MemberItem[],
  utubOwnerUserID: number,
  isCurrentUserOwner: boolean,
  currentUserID: number,
  utubID: number,
): void {
  resetMemberDeck();
  $("#displayMemberWrap").showClassFlex();
  const parent = $("#listMembers");

  // Co-owners can add members too (DD-1), so gate the add affordance on
  // owner-OR-co-creator rather than the literal owner flag alone.
  const canManageMembers = isCurrentUserOwner || getState().isCoCreator;

  if (canManageMembers) setupShowCreateMemberFormEventListeners(utubID);

  // Instantiate deck with list of members with access to current UTub
  for (const utubMember of dictMembers) {
    const utubMemberUsername = utubMember.username;
    const utubMemberUserID = utubMember.id;

    if (utubMemberUserID === utubOwnerUserID) {
      $("#UTubOwner").append(
        createOwnerBadge(utubOwnerUserID, utubMemberUsername),
      );
    } else {
      parent.append(
        createMemberBadge({
          memberID: utubMemberUserID,
          username: utubMemberUsername,
          memberRole: utubMember.memberRole,
          isCurrentUserOwner,
          utubID,
        }),
      );
    }
  }

  // TODO: Move leaving of UTub badge creation here so that createMemberBadge does one thing
  // VERIFY where it is being used first
  if (!isCurrentUserOwner) {
    createLeaveUTubAsMemberIcon(isCurrentUserOwner, currentUserID, utubID);
  }

  // Stripe the freshly-built rows, (re)bind the filter listeners for this UTub,
  // and reveal the funnel toggle (the box starts collapsed).
  applyAlternatingMemberBackground();
  setMemberSelectorSearchEventListener();
  setMemberNameFilterToggleListeners();
  showMemberFilterBar();

  // Subheader prompt
  setMemberDeckForUTub(canManageMembers);

  // Standalone "Transfer ownership" trigger (owner-only, DD-9). Shown only for
  // the literal owner AND when at least one non-owner member exists as a
  // transfer target. No client-side lock check — matching #utubBtnDelete
  // (utubs/deck.ts, gated only on isCurrentUserOwner) and #memberBtnCreate
  // (gated only on canManageMembers): the server's 403 UTUB_IS_LOCKED +
  // isUtubLockedHandled banner enforces the lock, not this trigger's
  // visibility (DD-11 governs the backend reject_if_utub_locked guard only).
  setMemberDeckTransferOwnerBtn({
    members: dictMembers,
    utubOwnerUserID,
    isCurrentUserOwner,
  });
}

// Reveal/hide + (re)bind the owner-only "Transfer ownership" header button for
// the currently selected UTub. Reads the just-built deck's members/owner/role
// (the same authoritative values buildSelectedUTub set into state before
// emitting UTUB_SELECTED). Idempotent off/on binding (mirrors
// setupShowCreateMemberFormEventListeners) so re-running on UTub reselection
// never double-binds the click handler.
function setMemberDeckTransferOwnerBtn({
  members,
  utubOwnerUserID,
  isCurrentUserOwner,
}: {
  members: MemberItem[];
  // number | null so the STALE_DATA path can forward getState().utubOwnerID
  // directly; a null owner never equals any member id (all count as non-owner),
  // and the isCurrentUserOwner gate below still governs visibility.
  utubOwnerUserID: number | null;
  isCurrentUserOwner: boolean;
}): void {
  const otherMembers = members.filter(
    (member) => member.id !== utubOwnerUserID,
  ).length;
  const transferOwnerBtn = $("#memberBtnTransferOwner");

  if (isCurrentUserOwner && otherMembers >= 1) {
    transferOwnerBtn.attr(
      "aria-label",
      APP_CONFIG.strings.TRANSFER_OWNER_ACTION,
    );
    // Reach the picker through the event bus (mirrors the delete-flow trigger's
    // TRANSFER_PICKER_REQUESTED emit) rather than a direct openTransferPicker
    // import — a static members/deck.ts → transfer-picker.ts import would close
    // a members/deck ↔ transfer-picker ↔ transfer/member-combobox module cycle.
    // transfer-picker.ts already subscribes to this event and opens for the
    // active UTub, threading `opener` through for focus return.
    transferOwnerBtn.off("click").on("click.transferOwner", () =>
      emit(AppEvents.TRANSFER_PICKER_REQUESTED, {
        opener: "#memberBtnTransferOwner",
      }),
    );
    transferOwnerBtn.showClassNormal();
  } else {
    transferOwnerBtn.hideClass();
  }
}

export function setMemberDeckWhenNoUTubSelected(): void {
  resetMemberDeck();

  $("#memberBtnCreate").hideClass();
  // Owner-only transfer trigger is hidden alongside the other owner
  // affordances whenever no UTub is selected.
  $("#memberBtnTransferOwner").hideClass();
  // The leave button lives in the UTub deck now; it is hidden via
  // setUTubDeckWhenNoUTubSelected() on the no-UTub path.

  // Hide the member list until a UTub is selected
  $("#displayMemberWrap").hideClass();

  // Clear the inline member count next to the deck title
  $("#MemberDeckCount").text("");
}

export function setMemberDeckForUTub(canManageMembers: boolean = true): void {
  const numOfMembers = $("#listMembers").find("span.member").length + 1; // plus 1 for owner

  log("setMemberDeckForUTub — permission-gated UI", {
    canManageMembers,
    numOfMembers,
    showingAddButton: canManageMembers,
  });

  // Ability to add members is limited to the UTub owner and co-owners (DD-1). The
  // leave/delete actions live in the UTub deck (setUTubDeckOnUTubSelected) and are
  // not managed here.
  if (canManageMembers) {
    $("#memberBtnCreate").showClassNormal();
  } else {
    $("#memberBtnCreate").hideClass();
  }

  // Inline member total next to the deck title (replaces the subheader band)
  $("#MemberDeckCount").text("(" + numOfMembers + ")");
}

on(
  AppEvents.UTUB_SELECTED,
  ({ members, utubOwnerID, isCurrentUserOwner, currentUserID, utubID }) =>
    setMemberDeckOnUTubSelected(
      members,
      utubOwnerID,
      isCurrentUserOwner,
      currentUserID,
      utubID,
    ),
);

on(AppEvents.STALE_DATA_DETECTED, ({ members, utubID }) =>
  updateMemberDeck(members, getState().isCurrentUserOwner, utubID),
);
