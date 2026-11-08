import type { MemberItem } from "../../types/member.js";
import type { MemberSortValue } from "../../types/preferences.js";

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
import { compareMembers } from "./sort.js";
import { closeMemberRowMenuInRow } from "./row-menu.js";
import { canAddMembers, viewerRoleFor } from "../utubs/policy.js";
import { withMemberControlFocusFallback } from "./focus-fallback.js";
import { clearMemberDeckNotice } from "./notice.js";
import { seedMemberDeckPolicySnapshot } from "./policy-attrs.js";
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

// Moves the existing `.member` rows of #listMembers into the order the given
// members and sort dictate, without rebuilding any row. Only rows whose index
// among the member rows differs from the target index count as moved; those ids
// are returned (a no-op order touches no DOM and returns []). The moved set is
// index-differs, so rows passively shifted by another row's move count as moved
// too. The owner stays in
// #UTubOwner, rows unknown to `members` keep their relative order after the
// known ones, and the store is never written.
//
// The inputs are explicit (not read from the store) because the stale-data path
// emits STALE_DATA_DETECTED before its setState, so the store may still hold the
// old members. A moved row's open menu closes (its kebab is refocused); a menu in
// an unmoved row stays open. Focus that was inside #listMembers survives the
// re-insert. Background reorders are silent: no scroll, no announcement.
export function reorderMemberDeck({
  members,
  memberSort,
}: {
  members: MemberItem[];
  memberSort: MemberSortValue;
}): number[] {
  const list = $("#listMembers")[0];
  if (list === undefined) return [];
  const memberRows = (): HTMLElement[] =>
    Array.from(list.children).filter(
      (child): child is HTMLElement =>
        child instanceof HTMLElement && child.classList.contains("member"),
    );
  const currentRows = memberRows();
  const rowByID = new Map(
    currentRows.map((row) => [Number(row.getAttribute("memberid")), row]),
  );
  const knownRows = [...members]
    .sort(compareMembers({ memberSort }))
    .map((member) => rowByID.get(member.id))
    .filter((row): row is HTMLElement => row !== undefined);
  const knownSet = new Set(knownRows);
  const targetRows = [
    ...knownRows,
    ...currentRows.filter((row) => !knownSet.has(row)),
  ];

  const movedRows = targetRows.filter(
    (row, index) => currentRows[index] !== row,
  );
  if (movedRows.length === 0) return [];

  const activeElement = document.activeElement;
  const focusWasInList =
    activeElement instanceof HTMLElement && list.contains(activeElement);

  // Per row whose open menu closed: the row and its kebab, so focus is refocused
  // to a kebab only when it was inside that same row.
  const closedMenus = movedRows.flatMap((row) => {
    const kebab = closeMemberRowMenuInRow({ row });
    return kebab === null ? [] : [{ row, kebab }];
  });

  targetRows.forEach((row, index) => {
    const rowsNow = memberRows();
    if (rowsNow[index] !== row) list.insertBefore(row, rowsNow[index] ?? null);
  });

  if (focusWasInList) {
    const owningMenu = closedMenus.find(({ row }) =>
      row.contains(activeElement),
    );
    if (owningMenu !== undefined) {
      owningMenu.kebab[0]?.focus({ preventScroll: true });
    } else if (
      activeElement instanceof HTMLElement &&
      activeElement.isConnected &&
      document.activeElement !== activeElement
    ) {
      activeElement.focus({ preventScroll: true });
    }
  }

  applyAlternatingMemberBackground();
  return movedRows.map((row) => Number(row.getAttribute("memberid")));
}

// The vertical bounds a row must sit inside: the nearest scrolling ancestor, or
// the window viewport when no ancestor scrolls.
function nearestMemberScrollBounds(row: HTMLElement): {
  top: number;
  bottom: number;
} {
  let current = row.parentElement;
  while (current !== null) {
    const overflowY = window.getComputedStyle(current).overflowY;
    if (overflowY === "auto" || overflowY === "scroll") {
      return current.getBoundingClientRect();
    }
    current = current.parentElement;
  }
  return { top: 0, bottom: window.innerHeight };
}

// Scrolls a member's row into view only when it is outside its scroll parent.
// A filter-hidden (`.hidden`) row is never scrolled to. Mirrors
// scrollActiveUTubIntoViewIfHidden in utubs/sort.ts and never moves focus.
export function scrollMemberRowIntoViewIfHidden({
  memberID,
}: {
  memberID: number;
}): void {
  const row = $(`#listMembers > .member[memberid="${memberID}"]`)[0];
  if (row === undefined || row.classList.contains("hidden")) return;
  const rowRect = row.getBoundingClientRect();
  const viewport = nearestMemberScrollBounds(row);
  if (rowRect.top >= viewport.top && rowRect.bottom <= viewport.bottom) return;
  row.scrollIntoView({ block: "nearest", behavior: "instant" });
}

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
          viewerRole: viewerRoleFor({
            isCurrentUserOwner,
            isCoCreator: getState().isCoCreator,
          }),
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

  // Put added rows and role-flipped rows in sort order. newMembers is passed
  // explicitly (the store still holds the old members here); the sort is read from
  // the store, where the stale-data path already wrote the resolved value (a kept
  // local edit wins over the payload). Intentionally silent: a background reorder
  // neither scrolls nor announces.
  reorderMemberDeck({
    members: newMembers,
    memberSort: getState().preferences.memberSort,
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
  // The rebuild destroys every row: focus that sat on a row or kebab falls back
  // to the deck header, never <body>.
  withMemberControlFocusFallback({
    coverList: true,
    write: () =>
      buildMemberDeck({
        dictMembers,
        utubOwnerUserID,
        isCurrentUserOwner,
        currentUserID,
        utubID,
      }),
  });
  // Re-seed the policy baseline so a UTub change is never read as a flip.
  seedMemberDeckPolicySnapshot();
}

function buildMemberDeck({
  dictMembers,
  utubOwnerUserID,
  isCurrentUserOwner,
  currentUserID,
  utubID,
}: {
  dictMembers: MemberItem[];
  utubOwnerUserID: number;
  isCurrentUserOwner: boolean;
  currentUserID: number;
  utubID: number;
}): void {
  resetMemberDeck();
  $("#displayMemberWrap").showClassFlex();
  const parent = $("#listMembers");

  // The add affordance follows the shared rule: owner or co-owner, or a plain
  // member while the owner allows it.
  const { isCoCreator, settings } = getState();
  const viewerRole = viewerRoleFor({ isCurrentUserOwner, isCoCreator });
  if (canAddMembers({ isCurrentUserOwner, isCoCreator, settings })) {
    setupShowCreateMemberFormEventListeners(utubID);
  }

  // Paint in the resolved sort (written to the store before UTUB_SELECTED; a kept
  // local edit wins over the payload). This is also how an ownership transfer
  // ends in sort order: its success path re-emits UTUB_SELECTED.
  const sortedMembers = [...dictMembers].sort(
    compareMembers({ memberSort: getState().preferences.memberSort }),
  );

  // Instantiate deck with list of members with access to current UTub
  for (const utubMember of sortedMembers) {
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
          viewerRole,
          utubID,
        }),
      );
    }
  }

  // TODO: Move leaving of UTub badge creation here so that createMemberBadge does one thing
  // VERIFY where it is being used first
  if (!isCurrentUserOwner) {
    createLeaveUTubAsMemberIcon({ currentUserID, utubID });
  }

  // Stripe the freshly-built rows, (re)bind the filter listeners for this UTub,
  // and reveal the funnel toggle (the box starts collapsed).
  applyAlternatingMemberBackground();
  setMemberSelectorSearchEventListener();
  setMemberNameFilterToggleListeners();
  showMemberFilterBar();

  // Subheader prompt
  setMemberDeckForUTub();
}

export function setMemberDeckWhenNoUTubSelected(): void {
  resetMemberDeck();
  clearMemberDeckNotice();

  $("#memberBtnCreate").hideClass();
  // The leave button lives in the UTub deck now; it is hidden via
  // setUTubDeckWhenNoUTubSelected() on the no-UTub path.

  // Hide the member list until a UTub is selected
  $("#displayMemberWrap").hideClass();

  // Clear the inline member count next to the deck title
  $("#MemberDeckCount").text("");
}

export function setMemberDeckForUTub(): void {
  const numOfMembers = $("#listMembers").find("span.member").length + 1; // plus 1 for owner
  // The one shared add rule, read from the store: no caller can force it on.
  const canAdd = canAddMembers();

  log("setMemberDeckForUTub — permission-gated UI", {
    canAdd,
    numOfMembers,
  });

  // Owners and co-owners always add; a plain member only while the owner allows
  // it. The leave/delete actions live in the UTub deck (setUTubDeckOnUTubSelected)
  // and are not managed here.
  if (canAdd) {
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
