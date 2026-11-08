import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { debug } from "../../lib/debug.js";
import { getState, subscribe, type AppState } from "../../store/app-store.js";
import { canAddMembers, canCoOwnerRemoveMembers } from "../utubs/policy.js";
import { closeAllMemberRowMenus } from "./row-menu.js";
import { dismissAddMemberTipIfActive } from "../onboarding/nudges.js";
import { setupShowCreateMemberFormEventListeners } from "./create.js";
import { hideAndResetMemberCombobox } from "./member-combobox.js";
import { withMemberControlFocusFallback } from "./focus-fallback.js";
import { announceMemberRowAction, showMemberDeckNotice } from "./notice.js";

const log = debug("members");

const MEMBERS_CAN_ADD_KEY = "members.members_can_add";
const CO_OWNERS_CAN_REMOVE_KEY = "members.co_owners_can_remove";
const RELEVANT_KEYS: ReadonlyArray<keyof AppState> = [
  "settings",
  "activeUTubID",
  "isCurrentUserOwner",
  "isCoCreator",
];

// What the subscription last saw. `utubID` is the UTub it describes;
// `learnedAddVersion` is the counter value the add policy was learned off at (a
// 403), so a revoke caused by the viewer's own refusal can be told apart from one
// that arrived by refresh or by the owner's save.
interface PolicySnapshot {
  utubID: number | null;
  canAdd: boolean;
  // A co-owner viewer's effective remove ability, and whether the viewer is a
  // co-owner at all (a demotion is a role change, not a policy flip).
  canRemove: boolean;
  viewerIsCoOwner: boolean;
  learnedAddVersion: number | null;
  learnedRemoveVersion: number | null;
}

let _snapshot: PolicySnapshot = {
  utubID: null,
  canAdd: false,
  canRemove: false,
  viewerIsCoOwner: false,
  learnedAddVersion: null,
  learnedRemoveVersion: null,
};

// The learned-policy counter value when the add ability was last granted. A
// learned-off entry at or below it predates that grant, so it is stale and must
// not suppress the notice for a later revoke.
let _addGrantedAtVersion = -1;

function readSnapshot(): PolicySnapshot {
  const state = getState();
  return {
    utubID: state.activeUTubID,
    canAdd: canAddMembers(state),
    canRemove: canCoOwnerRemoveMembers(state),
    viewerIsCoOwner: !state.isCurrentUserOwner && state.isCoCreator,
    learnedAddVersion: state.learnedOffPolicies[MEMBERS_CAN_ADD_KEY] ?? null,
    learnedRemoveVersion:
      state.learnedOffPolicies[CO_OWNERS_CAN_REMOVE_KEY] ?? null,
  };
}

// Re-seeds the baseline from the store. Called on every members-deck
// UTUB_SELECTED so a UTub change is never read as a flip.
export function seedMemberDeckPolicySnapshot(): void {
  _snapshot = readSnapshot();
  _addGrantedAtVersion = -1;
}

function isComboboxOpen(): boolean {
  return $("#createMemberWrap").find(".memberAddComboboxWrap").length > 0;
}

// Fail closed: CSS shows the co-owner kebabs only for exactly "true".
function applyMemberDeckAttrs(): void {
  $("#MemberDeck").attr(
    "data-co-owners-can-remove",
    String(getState().settings?.members.co_owners_can_remove === true),
  );
}

function syncAddButtonVisibility({
  snapshot,
}: {
  snapshot: PolicySnapshot;
}): void {
  const button = $("#memberBtnCreate");
  if (snapshot.utubID !== null && snapshot.canAdd) {
    button.showClassNormal();
  } else {
    button.hideClass();
  }
}

function handleAddGranted({ utubID }: { utubID: number }): void {
  _addGrantedAtVersion = getState().policyLearnedVersion;
  $("#memberBtnCreate").showClassNormal();
  // Never rebind while a combobox holds the wrap: that would clobber Cancel.
  if (!isComboboxOpen()) setupShowCreateMemberFormEventListeners(utubID);
  announceMemberRowAction({
    message: APP_CONFIG.strings.MEMBER_ADD_NOW_ALLOWED_ANNOUNCEMENT,
    politeness: "polite",
  });
}

function handleAddRevoked(): void {
  const comboboxOpen = isComboboxOpen();
  withMemberControlFocusFallback({
    write: () => {
      if (comboboxOpen) hideAndResetMemberCombobox();
      $("#memberBtnCreate").off("click").hideClass();
    },
  });
  dismissAddMemberTipIfActive();

  // The viewer's own 403 owns its notice and its single announcement. Read the
  // store, not a snapshot diff: a demoted co-owner's learn is not itself a revoke,
  // so the later role refresh must still be treated as learn-owned. An entry
  // from before the last grant is stale and owns nothing.
  const learnedVersion = getState().learnedOffPolicies[MEMBERS_CAN_ADD_KEY];
  if (learnedVersion !== undefined && learnedVersion > _addGrantedAtVersion)
    return;

  if (comboboxOpen) {
    showMemberDeckNotice({
      message: APP_CONFIG.strings.MEMBER_ADD_NOT_ALLOWED,
    });
    announceMemberRowAction({
      message: APP_CONFIG.strings.MEMBER_ADD_NOT_ALLOWED,
      politeness: "polite",
    });
  } else {
    announceMemberRowAction({
      message: APP_CONFIG.strings.MEMBER_ADD_NO_LONGER_ALLOWED_ANNOUNCEMENT,
      politeness: "polite",
    });
  }
}

// Announces a co-owner viewer's remove-ability flip. Silent when the viewer is
// not a co-owner on both sides (a role change is not a policy flip), when the
// ability did not change, or when the change is the viewer's own refused remove
// (the learn bumped the version, and removeMemberFail owns that announcement).
function handleRemoveFlip({
  previous,
  next,
}: {
  previous: PolicySnapshot;
  next: PolicySnapshot;
}): void {
  if (previous.canRemove === next.canRemove) return;
  if (!previous.viewerIsCoOwner || !next.viewerIsCoOwner) return;
  if (previous.learnedRemoveVersion !== next.learnedRemoveVersion) return;
  announceMemberRowAction({
    message: next.canRemove
      ? APP_CONFIG.strings.MEMBERS_PERMISSIONS_CO_OWNERS_REMOVE_ON_NOTICE
      : APP_CONFIG.strings.MEMBERS_PERMISSIONS_CO_OWNERS_REMOVE_OFF_NOTICE,
    politeness: "polite",
  });
}

/**
 * Shows or hides the add button and manages its click binding as the viewer's
 * add ability changes, and keeps `#MemberDeck[data-co-owners-can-remove]` in
 * step with the setting. Acts (bind, unbind, close the combobox, notice,
 * announce) only for a same-UTub ability change; across a UTub change it only
 * refreshes visibility and re-seeds the baseline.
 */
export function initMemberDeckPolicyAttrs(): () => void {
  seedMemberDeckPolicySnapshot();
  applyMemberDeckAttrs();
  return subscribe((changedKeys) => {
    if (!RELEVANT_KEYS.some((key) => changedKeys.includes(key))) return;
    const previous = _snapshot;
    const next = readSnapshot();
    _snapshot = next;

    const { utubID } = next;
    const sameUTub = utubID !== null && previous.utubID === utubID;
    // Hiding the co-owner kebabs closes any open row menu and keeps focus on a
    // control that still exists (the kebab's row), never <body>.
    if (sameUTub && previous.canRemove && !next.canRemove) {
      withMemberControlFocusFallback({
        write: () => {
          closeAllMemberRowMenus();
          applyMemberDeckAttrs();
        },
      });
    } else {
      applyMemberDeckAttrs();
    }

    if (utubID === null || !sameUTub) {
      syncAddButtonVisibility({ snapshot: next });
      return;
    }
    handleRemoveFlip({ previous, next });
    if (previous.canAdd === next.canAdd) return;

    log("member add ability changed", {
      utubID,
      canAdd: next.canAdd,
    });
    if (next.canAdd) {
      handleAddGranted({ utubID });
    } else {
      handleAddRevoked();
    }
  });
}
