import type { MemberItem } from "../../types/member.js";

import { $ } from "../../lib/globals.js";
import { debug } from "../../lib/debug.js";
import { applyDeckDiff } from "../../logic/apply-deck-diff.js";
import { getState } from "../../store/app-store.js";
import { on, AppEvents } from "../../lib/event-bus.js";
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
}

export function setMemberDeckWhenNoUTubSelected(): void {
  resetMemberDeck();

  $("#memberBtnCreate").hideClass();
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
