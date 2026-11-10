import type { ResolvedUtubSettings } from "../../types/settings.js";

import { getState, setState, type AppState } from "../../store/app-store.js";

// Settings keys a refused request can teach the client are off.
export const LEARNABLE_POLICY_KEYS = [
  "urls.allow_short_links",
  "members.members_can_add",
  "members.co_owners_can_remove",
] as const;

export type LearnablePolicyKey = (typeof LEARNABLE_POLICY_KEYS)[number];

// Records that a refused request proved `key` is off for the active UTub. Writes
// only that key, bumps `policyLearnedVersion` and records the key at the new
// version. A stale UTub or an undelivered (null) settings slice gets no write.
// Returns whether anything was written.
export function learnPolicyOff({
  utubID,
  key,
}: {
  utubID: number;
  key: LearnablePolicyKey;
}): boolean {
  const { activeUTubID, settings, policyLearnedVersion, learnedOffPolicies } =
    getState();
  if (activeUTubID !== utubID || settings === null) return false;
  const nextVersion = policyLearnedVersion + 1;
  const nextSettings: ResolvedUtubSettings = {
    ...settings,
    urls: { ...settings.urls },
    members: { ...settings.members },
  };
  switch (key) {
    case "urls.allow_short_links":
      nextSettings.urls.allow_short_links = false;
      break;
    case "members.members_can_add":
      nextSettings.members.members_can_add = false;
      break;
    case "members.co_owners_can_remove":
      nextSettings.members.co_owners_can_remove = false;
      break;
  }
  setState({
    settings: nextSettings,
    policyLearnedVersion: nextVersion,
    learnedOffPolicies: { ...learnedOffPolicies, [key]: nextVersion },
  });
  return true;
}

// Whether the viewer may add members: the owner and co-owners always, a plain
// member only while the owner allows it. Missing settings mean false.
export function canAddMembers(
  state: Pick<
    AppState,
    "isCurrentUserOwner" | "isCoCreator" | "settings"
  > = getState(),
): boolean {
  return (
    state.isCurrentUserOwner ||
    state.isCoCreator ||
    state.settings?.members.members_can_add === true
  );
}

// Whether the active UTub's member list (and total) is hidden from the viewer:
// false only for the owner, co-owners, or when the resolved setting is exactly
// false. Missing settings fail closed (hidden); the server is the authority.
export function isMemberListHiddenForViewer(
  state: Pick<
    AppState,
    "isCurrentUserOwner" | "isCoCreator" | "settings"
  > = getState(),
): boolean {
  if (state.isCurrentUserOwner || state.isCoCreator) return false;
  return state.settings?.members.hide_member_list !== false;
}

export const VIEWER_ROLE = {
  OWNER: "owner",
  CO_OWNER: "co_owner",
  MEMBER: "member",
} as const;
export type ViewerRole = (typeof VIEWER_ROLE)[keyof typeof VIEWER_ROLE];

// The viewer's role, derived the one way every member-row builder uses.
export function viewerRoleFor({
  isCurrentUserOwner,
  isCoCreator,
}: {
  isCurrentUserOwner: boolean;
  isCoCreator: boolean;
}): ViewerRole {
  if (isCurrentUserOwner) return VIEWER_ROLE.OWNER;
  if (isCoCreator) return VIEWER_ROLE.CO_OWNER;
  return VIEWER_ROLE.MEMBER;
}

// Whether the viewer is a co-owner (not the owner) who may remove plain members:
// only while the owner allows it. Missing settings mean false.
export function canCoOwnerRemoveMembers(
  state: Pick<
    AppState,
    "isCurrentUserOwner" | "isCoCreator" | "settings"
  > = getState(),
): boolean {
  return (
    !state.isCurrentUserOwner &&
    state.isCoCreator &&
    state.settings?.members.co_owners_can_remove === true
  );
}
