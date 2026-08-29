import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { getState } from "../../store/app-store.js";
import { removeMemberShowModal } from "./delete.js";
import { modifyMemberRoleShowModal } from "./role.js";
import {
  bindMemberRowMenu,
  bindMemberRowModalFocusRestore,
  closeAllMemberRowMenus,
} from "./row-menu.js";
import { makeUTubRoleIcon } from "../utubs/selectors.js";
import { hideInputs } from "../btns-forms.js";
import { deselectAllURLs } from "../urls/cards/selection.js";

// Inline SVG icons (bootstrap-icons font is NOT loaded in this app — `<i class="bi
// …">` renders nothing — so every glyph must be inline <svg> with explicit path
// data). Kebab (overflow) trigger + the "Remove member" menu-item glyph.
const KEBAB_ICON_SVG =
  `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-three-dots-vertical" viewBox="0 0 16 16" aria-hidden="true">` +
  `<path d="M9.5 13a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0m0-5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0m0-5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0"/>` +
  `</svg>`;
const REMOVE_MEMBER_ICON_SVG =
  `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-person-x-fill" viewBox="0 0 16 16" aria-hidden="true">` +
  `<path fill-rule="evenodd" d="M1 14s-1 0-1-1 1-4 6-4 6 3 6 4-1 1-1 1zm5-6a3 3 0 1 0 0-6 3 3 0 0 0 0 6m6.146-2.854a.5.5 0 0 1 .708 0L14 6.293l1.146-1.147a.5.5 0 0 1 .708.708L14.707 7l1.147 1.146a.5.5 0 0 1-.708.708L14 7.707l-1.146 1.147a.5.5 0 0 1-.708-.708L13.293 7l-1.147-1.146a.5.5 0 0 1 0-.708"/>` +
  `</svg>`;
// Role-toggle menu item glyph (neutral person — the label swaps Make/Revoke, so
// the icon must not carry a make-or-revoke meaning that would need swapping too).
const ROLE_MEMBER_ICON_SVG =
  `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-person-fill" viewBox="0 0 16 16" aria-hidden="true">` +
  `<path d="M3 14s-1 0-1-1 1-4 6-4 6 3 6 4-1 1-1 1zm5-6a3 3 0 1 0 0-6 3 3 0 0 0 0 6"/>` +
  `</svg>`;

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

// DD-7/DD-8/DD-18: the single per-row role-swap helper, shared by role.ts's
// grant/revoke success handler AND deck.ts's updateMemberDeck diff. Swaps ONLY
// the row's inner pieces in place (icon, visually-hidden label, role menu-item
// text) — never rebuilds or replaces the `.member` row node itself.
export function swapMemberRoleInRow({
  memberID,
  targetRole,
}: {
  memberID: number;
  targetRole: string;
}): void {
  const row = $(`.member[memberid=${memberID}]`);
  // Swap the decorative role icon (aria-hidden) via replaceWith — never the row.
  row
    .find(".memberRole")
    .replaceWith(makeUTubRoleIcon({ memberRole: targetRole, isLocked: false }));
  // DD-18: keep the visually-hidden role label in sync (a stale "Member"/
  // "Co-owner" would otherwise be announced after the swap). Located via the
  // .member-role-wrap ancestor, not .visually-hidden (which is shared/generic).
  row.find(".member-role-wrap .visually-hidden").text(roleLabelFor(targetRole));
  // Flip the role menu-item's label + aria-label (Make ↔ Revoke). Located by its
  // dedicated class, not text — the text is exactly what is being swapped (DD-8).
  const label =
    targetRole === APP_CONFIG.constants.MEMBER_ROLES.CO_CREATOR
      ? APP_CONFIG.strings.REVOKE_CO_OWNER_ACTION
      : APP_CONFIG.strings.MAKE_CO_OWNER_ACTION;
  const roleItem = row.find(".memberRowMenuItemRole");
  // Swap only the label <span> so the item's leading icon is preserved.
  roleItem.find("span").text(label);
  roleItem.attr("aria-label", label);
}

// Creates member list item
export function createOwnerBadge(
  utubOwnerUserID: number,
  utubMemberUsername: string,
): HTMLSpanElement {
  const memberSpan = document.createElement("span");

  $(memberSpan)
    .attr({ memberid: utubOwnerUserID })
    .addClass("member full-width flex-row jc-sb align-center");
  // Set the username via .text() (a text node) rather than interpolating it into
  // an HTML sink, so a `<`/`>`/`"` in the name can never reach HTML parsing. The
  // role icon+label markup is static/trusted, so it stays an HTML append.
  $(memberSpan)
    .append($(document.createElement("b")).text(utubMemberUsername))
    .append(roleIconWithLabel(APP_CONFIG.constants.MEMBER_ROLES.CREATOR));

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
    .addClass("member full-width flex-row jc-sb align-center flex-start");
  // Build the bold username node and set the name via .text() (a text node),
  // never string-interpolated into an HTML sink. This keeps a username containing
  // `<`/`>`/`"` from ever reaching HTML parsing regardless of backend filtering.
  $(memberSpan).append($(document.createElement("b")).text(username));

  // Right-side affordance cluster: role icon first, then any action controls.
  // jc-sb on the row keeps the name separated from this cluster.
  const memberRight = $(
    `<span class="member-right flex-row align-center">${roleIconWithLabel(memberRole)}</span>`,
  );
  $(memberSpan).append(memberRight);

  if (isCurrentUserOwner) {
    // Owner viewer: fold the row's actions into a kebab (overflow) menu. Step 3
    // ships it with only "Remove member" (reusing removeMemberShowModal); the
    // grant/revoke item is added in Step 4.
    const kebabBtn = $(
      `<button type="button" class="memberRowKebab flex-row align-center" aria-haspopup="menu" aria-expanded="false">${KEBAB_ICON_SVG}</button>`,
    ) as JQuery<HTMLButtonElement>;
    // Set the member-naming aria-label via the attr-setter (not interpolated into
    // the HTML string above) so a username containing a double-quote cannot break
    // out of the attribute and inject markup. Backend filtering is not a guarantee
    // at this sink: usernames are not HTML-escaped, the nh3 filter rejects
    // well-formed tags but a bare `"` still reaches the client, and the OAuth/CLI
    // registration paths bypass the Pydantic username schema entirely. So every
    // user-controlled value is set through .attr()/.text(), never an HTML string.
    kebabBtn.attr("aria-label", `Actions for ${username}`);
    kebabBtn.enableTab();

    // Role-toggle label reflects the row's CURRENT role (Revoke if already a
    // co-owner, otherwise Make). The dedicated .memberRowMenuItemRole class (not
    // .danger) lets swapMemberRoleInRow re-target this button after its own text
    // has changed (DD-8) — a text-based selector would break on the swap.
    const roleActionLabel =
      memberRole === APP_CONFIG.constants.MEMBER_ROLES.CO_CREATOR
        ? APP_CONFIG.strings.REVOKE_CO_OWNER_ACTION
        : APP_CONFIG.strings.MAKE_CO_OWNER_ACTION;

    const rowMenu = $(
      `<div class="memberRowMenu" role="menu" hidden>` +
        `<button type="button" role="menuitem" class="memberRowMenuItem memberRowMenuItemRole">` +
        `${ROLE_MEMBER_ICON_SVG}<span>${roleActionLabel}</span>` +
        `</button>` +
        `<hr class="memberRowMenuDivider" aria-hidden="true" />` +
        `<button type="button" role="menuitem" class="memberRowMenuItem danger">` +
        `${REMOVE_MEMBER_ICON_SVG}<span>Remove member</span>` +
        `</button>` +
        `</div>`,
    ) as JQuery<HTMLDivElement>;
    // Name the role button for screen readers (its text alone omits the member).
    rowMenu.find(".memberRowMenuItemRole").attr("aria-label", roleActionLabel);

    memberRight.append(kebabBtn).append(rowMenu);

    // DD-13: bind the shared open/close/keyboard wiring on the freshly-built pair.
    bindMemberRowMenu({ kebab: kebabBtn, menu: rowMenu, memberID });

    // Wire "Make/Revoke co-owner": DD-16 close the menu first, DD-25 arm the
    // focus restore, THEN open the modal — never show it while the menu is open.
    // DD-22: no username param; the confirm copy is static per-role.
    rowMenu
      .find(".memberRowMenuItemRole")
      .offAndOnExact("click.memberRowMenuRole", function () {
        closeAllMemberRowMenus();
        bindMemberRowModalFocusRestore(memberID);
        modifyMemberRoleShowModal({
          memberID,
          // Source the CURRENT role at click time, not the creation-time
          // `memberRole` closure: swapMemberRoleInRow re-renders the row in place
          // (no full deck rebuild, so this handler is never rebound), so a stale
          // closure would compute the wrong targetRole on a second toggle. Mirrors
          // the DD-22 store lookup role.ts's success handler already uses.
          currentRole:
            getState().members.find((member) => member.id === memberID)
              ?.memberRole ?? memberRole,
          utubID,
        });
      });

    // Wire "Remove member": DD-16 close the menu first, DD-25 arm the focus
    // restore, THEN open the modal — never show the modal while the menu is open.
    rowMenu
      .find(".memberRowMenuItem.danger")
      .offAndOnExact("click.memberRowMenuRemove", function () {
        closeAllMemberRowMenus();
        bindMemberRowModalFocusRestore(memberID);
        removeMemberShowModal(memberID, isCurrentUserOwner, utubID);
      });
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
