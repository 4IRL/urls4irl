"use strict";

// Clear the Member Deck
function resetMemberDeck() {
  $("#UTubOwner").empty();
  $("#listMembers").empty();
}

// Update member deck on asynchronous update, either due to stale data or refresh
function updateMemberDeck(newMembers, isCurrentUserOwner, utubID) {
  const currentMembers = $(".member");
  const currentMemberIDs = $.map(currentMembers, (member) =>
    parseInt($(member).attr("memberid")),
  );
  const newMemberIDs = $.map(newMembers, (member) => member.id);

  // Find any old members that aren't in new and remove them
  let memberIDToRemove;
  for (let i = 0; i < currentMemberIDs.length; i++) {
    memberIDToRemove = currentMemberIDs[i];
    if (!newMemberIDs.includes(memberIDToRemove)) {
      $(".member[memberid=" + memberIDToRemove + "]").remove();
    }
  }

  // Find any new members that aren't in old and add them
  const memberDeck = $("#listMembers");
  for (let i = 0; i < newMembers.length; i++) {
    if (!currentMemberIDs.includes(newMembers[i].id)) {
      memberDeck.append(
        createMemberBadge(
          newMembers[i].id,
          newMembers[i].username,
          isCurrentUserOwner,
          utubID,
        ),
      );
    }
  }
}

// Build center panel URL list for selectedUTub
function setMemberDeckOnUTubSelected(
  dictMembers,
  utubOwnerUserID,
  isCurrentUserOwner,
  currentUserID,
  utubID,
) {
  resetMemberDeck();
  const parent = $("#listMembers");
  const numOfMembers = dictMembers.length;
  let utubMember;
  let utubMemberUsername;
  let utubMemberUserID;

  isCurrentUserOwner ? setupShowCreateMemberFormEventListeners(utubID) : null;

  // Instantiate deck with list of members with access to current UTub
  for (let i = 0; i < numOfMembers; i++) {
    utubMember = dictMembers[i];
    utubMemberUsername = utubMember.username;
    utubMemberUserID = utubMember.id;

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
  isCurrentUserOwner
    ? null
    : createLeaveUTubAsMemberIcon(isCurrentUserOwner, currentUserID, utubID);

  // Subheader prompt
  setMemberDeckForUTub(isCurrentUserOwner);
}

function setMemberDeckWhenNoUTubSelected() {
  resetMemberDeck();

  $("#memberBtnCreate").hideClass();
  $("#memberSelfBtnDelete").hideClass();

  // Subheader prompt hidden
  $("#MemberDeckSubheader").text(null);
}

function setMemberDeckForUTub(isCurrentUserOwner = true) {
  const numOfMembers = $("#listMembers").find("span.member").length + 1; // plus 1 for owner
  const memberDeckSubheader = $("#MemberDeckSubheader");
  memberDeckSubheader.parent().addClass("height-2rem");
  // Ability to add members is restricted to UTub owner
  if (isCurrentUserOwner) {
    $("#memberSelfBtnDelete").hideClass();
    $("#memberBtnCreate").showClassNormal();
    numOfMembers === 1
      ? memberDeckSubheader.text("Add a member")
      : memberDeckSubheader.text(numOfMembers + " members");
  } else {
    $("#memberBtnCreate").hideClass();
    $("#memberSelfBtnDelete").showClassNormal();
    memberDeckSubheader.text(numOfMembers + " members");
  }

  // Subheader prompt shown
  memberDeckSubheader.closest(".titleElement").show();
}
