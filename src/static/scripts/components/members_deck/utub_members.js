"use strict";

// Creates member list item
function createOwnerBadge(utubOwnerUserID, utubMemberUsername) {
  const memberSpan = document.createElement("span");

  $(memberSpan)
    .attr({ memberid: utubOwnerUserID })
    .addClass("member full-width flex-row flex-start align-center")
    .html("<b>" + utubMemberUsername + "</b>");

  return memberSpan;
}

function createMemberBadge(
  utubMemberUserID,
  utubMemberUsername,
  isCurrentUserOwner,
  utubID,
) {
  const memberSpan = $(document.createElement("span"));

  $(memberSpan)
    .attr({ memberid: utubMemberUserID })
    .addClass("member full-width flex-row jc-sb align-center flex-start")
    .html("<b>" + utubMemberUsername + "</b>");

  if (isCurrentUserOwner) {
    const removeIcon = createMemberRemoveBtn();
    removeIcon.offAndOnExact("click.removeMember", function (e) {
      removeMemberShowModal(utubMemberUserID, isCurrentUserOwner, utubID);
    });
    $(memberSpan).append(removeIcon);
  } else {
    // Leave UTub if member
    $("#memberSelfBtnDelete").offAndOnExact("click.removeMember", function (e) {
      hideInputs();
      deselectAllURLs();
      removeMemberShowModal(utubMemberUserID, isCurrentUserOwner, utubID);
    });
  }

  return memberSpan;
}
