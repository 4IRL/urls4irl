import { $ } from "../../lib/globals.js";
import { createMemberRemoveBtn, removeMemberShowModal } from "./delete.js";
import { hideInputs } from "../btns-forms.js";
import { deselectAllURLs } from "../urls/cards/selection.js";

// Diamond marker on the owner row — mirrors the UTub creator role icon.
const OWNER_ICON_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-diamond-fill memberRole" viewBox="0 0 16 16">' +
  '<path fill-rule="evenodd" d="M6.95.435c.58-.58 1.52-.58 2.1 0l6.515 6.516c.58.58.58 1.519 0 2.098L9.05 15.565c-.58.58-1.519.58-2.098 0L.435 9.05a1.48 1.48 0 0 1 0-2.098z"/>' +
  "</svg>";

// Creates member list item
export function createOwnerBadge(
  utubOwnerUserID: number,
  utubMemberUsername: string,
): HTMLSpanElement {
  const memberSpan = document.createElement("span");

  $(memberSpan)
    .attr({ memberid: utubOwnerUserID })
    .addClass("member full-width flex-row jc-sb align-center")
    .html("<b>" + utubMemberUsername + "</b>" + OWNER_ICON_SVG);

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
