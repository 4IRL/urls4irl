import { $ } from "../../lib/globals.js";
import { createMemberRemoveBtn, removeMemberShowModal } from "./delete.js";
import { hideInputs } from "../btns-forms.js";
import { deselectAllURLs } from "../urls/cards/selection.js";

// Creates member list item
export function createOwnerBadge(
  utubOwnerUserID: number,
  utubMemberUsername: string,
): HTMLSpanElement {
  const memberSpan = document.createElement("span");

  $(memberSpan)
    .attr({ memberid: utubOwnerUserID })
    .addClass("member full-width flex-row flex-start align-center")
    .html("<b>" + utubMemberUsername + "</b>");

  return memberSpan;
}

export function createMemberBadge(
  utubMemberUserID: number,
  utubMemberUsername: string,
  isCurrentUserOwner: boolean,
  utubID: number,
): JQuery<HTMLSpanElement> {
  const memberSpan = $(document.createElement("span"));

  $(memberSpan)
    .attr({ memberid: utubMemberUserID })
    .addClass("member full-width flex-row jc-sb align-center flex-start")
    .html("<b>" + utubMemberUsername + "</b>");

  if (isCurrentUserOwner) {
    const removeIcon = createMemberRemoveBtn();
    removeIcon.offAndOnExact("click.removeMember", function () {
      removeMemberShowModal(utubMemberUserID, isCurrentUserOwner, utubID);
    });
    $(memberSpan).append(removeIcon);
  } else {
    // Leave UTub if member
    $("#memberSelfBtnDelete").offAndOnExact("click.removeMember", function () {
      hideInputs();
      deselectAllURLs();
      removeMemberShowModal(utubMemberUserID, isCurrentUserOwner, utubID);
    });
  }

  return memberSpan;
}
