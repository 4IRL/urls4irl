import type { MemberItem } from "../../types/member.js";

import { $ } from "../../lib/globals.js";
import { applyDeckDiff } from "../../logic/apply-deck-diff.js";
import { getState } from "../../store/app-store.js";
import { on, AppEvents } from "../../lib/event-bus.js";
import { createMemberBadge, createOwnerBadge } from "./members.js";
import { setupShowCreateMemberFormEventListeners } from "./create.js";
import { createLeaveUTubAsMemberIcon } from "./delete.js";

// Clear the Member Deck
export function resetMemberDeck(): void {
  $("#UTubOwner").empty();
  $("#listMembers").empty();
}

// Update member deck on asynchronous update, either due to stale data or refresh
export function updateMemberDeck(
  newMembers: MemberItem[],
  isCurrentUserOwner: boolean,
  utubID: number,
): void {
  applyDeckDiff<MemberItem>({
    oldItems: getState().members,
    newItems: newMembers,
    getID: (member) => member.id,
    removeElement: (memberID) =>
      $(".member[memberid=" + memberID + "]").remove(),
    addElement: (member) => {
      $("#listMembers").append(
        createMemberBadge(
          member.id,
          member.username,
          isCurrentUserOwner,
          utubID,
        ),
      );
    },
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

  if (isCurrentUserOwner) setupShowCreateMemberFormEventListeners(utubID);

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
        createMemberBadge(
          utubMemberUserID,
          utubMemberUsername,
          isCurrentUserOwner,
          utubID,
        ),
      );
    }
  }

  // TODO: Move leaving of UTub badge creation here so that createMemberBadge does one thing
  // VERIFY where it is being used first
  if (!isCurrentUserOwner) {
    createLeaveUTubAsMemberIcon(isCurrentUserOwner, currentUserID, utubID);
  }

  // Subheader prompt
  setMemberDeckForUTub(isCurrentUserOwner);
}

export function setMemberDeckWhenNoUTubSelected(): void {
  resetMemberDeck();

  $("#memberBtnCreate").hideClass();
  $("#memberSelfBtnDelete").hideClass();

  // Hide the member list until a UTub is selected
  $("#displayMemberWrap").hideClass();

  // Clear the inline member count next to the deck title
  $("#MemberDeckCount").text("");
}

export function setMemberDeckForUTub(isCurrentUserOwner: boolean = true): void {
  const numOfMembers = $("#listMembers").find("span.member").length + 1; // plus 1 for owner

  // Ability to add members is restricted to UTub owner
  if (isCurrentUserOwner) {
    $("#memberSelfBtnDelete").hideClass();
    $("#memberBtnCreate").showClassNormal();
  } else {
    $("#memberBtnCreate").hideClass();
    $("#memberSelfBtnDelete").showClassNormal();
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
