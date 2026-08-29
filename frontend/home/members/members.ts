import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { createMemberRemoveBtn, removeMemberShowModal } from "./delete.js";
import { makeUTubRoleIcon } from "../utubs/selectors.js";
import { hideInputs } from "../btns-forms.js";
import { deselectAllURLs } from "../urls/cards/selection.js";

// Human-readable role label for the visually-hidden text that accompanies the
// decorative role icon. Shares the same 3-way switch shape makeUTubRoleIcon uses
// so the icon and its screen-reader label can never drift apart. Reused by both
// createMemberBadge/createOwnerBadge here and Step 4's swapMemberRoleInRow.
export function roleLabelFor(memberRole: string): string {
  switch (memberRole) {
    case APP_CONFIG.constants.MEMBER_ROLES.CREATOR:
      return "Owner";
    case APP_CONFIG.constants.MEMBER_ROLES.CO_CREATOR:
      return "Co-owner";
    default:
      return "Member";
  }
}

// Wraps the decorative role SVG (marked aria-hidden) alongside a visually-hidden
// text label so the role is announced to screen readers without duplicating the
// icon. makeUTubRoleIcon's own output is untouched (DD-2).
function roleIconWithLabel(memberRole: string): string {
  return (
    // Leading space keeps the role annotation a distinct text token from the
    // username that precedes it in the row's concatenated `textContent`. Without
    // it the visually-hidden label runs straight onto the name (e.g.
    // "u4i_test2Member"), which both muddies screen-reader phrasing and — since
    // there is no separating whitespace — defeats username-anchored locators that
    // match on a word boundary (`\bu4i_test2\b`). The space is whitespace-only
    // between flex items, so it has no visual effect on the row.
    ` <span class="member-role-wrap">` +
    `<span aria-hidden="true">${makeUTubRoleIcon({ memberRole, isLocked: false })}</span>` +
    `<span class="visually-hidden">${roleLabelFor(memberRole)}</span>` +
    `</span>`
  );
}

// Creates member list item
export function createOwnerBadge(
  utubOwnerUserID: number,
  utubMemberUsername: string,
): HTMLSpanElement {
  const memberSpan = document.createElement("span");

  $(memberSpan)
    .attr({ memberid: utubOwnerUserID })
    .addClass("member full-width flex-row jc-sb align-center")
    .html(
      "<b>" +
        utubMemberUsername +
        "</b>" +
        roleIconWithLabel(APP_CONFIG.constants.MEMBER_ROLES.CREATOR),
    );

  return memberSpan;
}

export function createMemberBadge({
  memberID,
  username,
  memberRole,
  isCurrentUserOwner,
  utubID,
}: {
  memberID: number;
  username: string;
  memberRole: string;
  isCurrentUserOwner: boolean;
  utubID: number;
}): JQuery<HTMLSpanElement> {
  const memberSpan = $(document.createElement("span"));

  $(memberSpan)
    .attr({ memberid: memberID })
    .addClass("member full-width flex-row jc-sb align-center flex-start")
    .html("<b>" + username + "</b>");

  // Right-side affordance cluster: role icon first, then any action controls.
  // jc-sb on the row keeps the name separated from this cluster.
  const memberRight = $(
    `<span class="member-right flex-row align-center">${roleIconWithLabel(memberRole)}</span>`,
  );
  $(memberSpan).append(memberRight);

  if (isCurrentUserOwner) {
    const removeIcon = createMemberRemoveBtn();
    removeIcon.offAndOnExact("click.removeMember", function () {
      removeMemberShowModal(memberID, isCurrentUserOwner, utubID);
    });
    memberRight.append(removeIcon);
  } else {
    // Leave UTub if member
    $("#memberSelfBtnDelete").offAndOnExact("click.removeMember", function () {
      hideInputs();
      deselectAllURLs();
      removeMemberShowModal(memberID, isCurrentUserOwner, utubID);
    });
  }

  return memberSpan;
}
