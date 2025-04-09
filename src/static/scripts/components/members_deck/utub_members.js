"use strict";

// Creates member list item
function createOwnerBadge(utubOwnerUserID, utubMemberUsername) {
  const memberSpan = document.createElement("span");

  $(memberSpan)
    .attr({ memberid: utubOwnerUserID })
    .addClass("member full-width flex-row")
    .html("<b>" + utubMemberUsername + "</b>");

  return memberSpan;
}

function createMemberBadge(
  utubMemberUserID,
  utubMemberUsername,
  isCurrentUserOwner,
) {
  const memberSpan = $(document.createElement("span"));

  $(memberSpan)
    .attr({ memberid: utubMemberUserID })
    .addClass("member full-width flex-row justify-space-between align-center")
    .html("<b>" + utubMemberUsername + "</b>");

  if (isCurrentUserOwner) {
    const removeIcon = createMemberRemoveIcon();
    removeIcon
      .offAndOn("click.removeMember", function (e) {
        e.stopPropagation();
        removeMemberShowModal(utubMemberUserID, isCurrentUserOwner);
      })
      .offAndOn("focus.removeMember", function () {
        $(document).on("keyup.removeMember", function (e) {
          if (e.which === 13)
            removeMemberShowModal(utubMemberUserID, isCurrentUserOwner);
        });
      })
      .offAndOn("blur.removeMember", function () {
        $(document).off("keyup.removeMember");
      });
    $(memberSpan).append(removeIcon);
  } else {
    // Leave UTub if member
    $("#memberSelfBtnDelete")
      .offAndOn("click.removeMember", function (e) {
        e.stopPropagation();
        hideInputs();
        deselectAllURLs();
        removeMemberShowModal(utubMemberUserID, isCurrentUserOwner);
      })
      .offAndOn("focus.removeSelf", function () {
        $(document).on("keyup.removeSelf", function (e) {
          if (e.which === 13) {
            hideInputs();
            deselectAllURLs();
            removeMemberShowModal(utubMemberUserID, isCurrentUserOwner);
          }
        });
      })
      .offAndOn("blur.removeSelf", function () {
        $(document).off("keyup.removeSelf");
      });
  }

  return memberSpan;
}
