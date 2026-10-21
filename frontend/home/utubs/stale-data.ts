import { emit, AppEvents } from "../../lib/event-bus.js";
import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";

import type { UtubDetail } from "../../types/utub.js";
import { resolveUtubSettings } from "../../types/settings.js";
import { getState, setState } from "../../store/app-store.js";
import type { AppState } from "../../store/app-store.js";
import { fitUTubHeaderAndSubheader } from "./header-fit.js";
import {
  fetchUTubForRefresh,
  buildSelectedUTub,
  makeUTubRoleIcon,
  applyUTubDescriptionVisibility,
} from "./selectors.js";
import { removeUTubLocally } from "./remove-local.js";
import { setBackgroundRefreshActive } from "./background-refresh-flag.js";
import { showURLDeckBannerError } from "../urls/deck.js";
import {
  isMobile,
  getCurrentMobilePanel,
  setCurrentMobilePanel,
  setMobileUIWhenUTubDeckSelected,
  setMobileUIWhenMemberDeckSelected,
  setMobileUIWhenUTubSelectedOrURLNavSelected,
} from "../mobile.js";
import { syncUTubEditPanelDirtyState } from "../urls/utub-edit-panel-dirty.js";
import { debug } from "../../lib/debug.js";

const log = debug("utubs");

// Handles updating a UTub if found to include stale data
// For example, a user decides to update a URL string to a new URL, but it returns
// saying the URL already exists in the UTub -> yet the user does not see the URL in the UTub?
// This means another user has updated a URL or added a URL with the new URL string, in which
// we should reload the user's UTub to show them the latest data.
//
// Also the apply path of refresh-on-focus: with `isBackgroundRefresh` it is safe
// to run unattended (read-only fetch, stale/busy/mid-flight guards, no-op
// short-circuit). `shouldApply` is the post-response busy re-check; when omitted
// the response always applies (conflict-handler callers are never gated).
export async function updateUTubOnFindingStaleData({
  utubID,
  isBackgroundRefresh = false,
  shouldApply,
}: {
  utubID: number;
  isBackgroundRefresh?: boolean;
  shouldApply?: () => boolean;
}): Promise<void> {
  log(
    "updateUTubOnFindingStaleData — refetching UTub due to detected stale data",
    { utubID, isBackgroundRefresh },
  );

  // Captured before the await: a local mutation or a desktop rename/description
  // edit landing mid-flight changes one of these, and the response is dropped.
  const capturedState = getState();
  const capturedUrls = capturedState.urls;
  const capturedTags = capturedState.tags;
  const capturedMembers = capturedState.members;
  const capturedName = capturedState.activeUTubName;
  const capturedDescription = capturedState.activeUTubDescription;
  const capturedLocked = capturedState.isCurrentUTubLocked;
  const capturedSettingsVersion = capturedState.settingsVersion;

  const result = await fetchUTubForRefresh({ utubID });

  // Stale guard (fail closed, every outcome): the user moved to another UTub.
  if (getState().activeUTubID !== utubID) {
    log(
      "updateUTubOnFindingStaleData — discarding response for inactive UTub",
      {
        utubID,
      },
    );
    return;
  }

  // Busy re-check: the user opened a form while the request was in flight.
  if (shouldApply && !shouldApply()) return;

  if (result.kind === "error") return;

  if (result.kind === "gone") {
    removeUTubLocally({ utubID });
    showURLDeckBannerError(APP_CONFIG.strings.UTUB_NO_LONGER_AVAILABLE);
    announceOnNextTick({
      selector: "#MobilePanelAnnouncement",
      message: APP_CONFIG.strings.UTUB_NO_LONGER_AVAILABLE,
    });
    return;
  }

  const utub = result.data;
  const currentState = getState();
  if (
    currentState.urls !== capturedUrls ||
    currentState.tags !== capturedTags ||
    currentState.members !== capturedMembers ||
    currentState.activeUTubName !== capturedName ||
    currentState.activeUTubDescription !== capturedDescription ||
    currentState.isCurrentUTubLocked !== capturedLocked
  ) {
    log(
      "updateUTubOnFindingStaleData — local mutation mid-flight, discarding",
      {
        utubID,
      },
    );
    return;
  }

  // Settings apply before the no-op short-circuit (a settings-only difference
  // must still land), unless a local save landed while the request was in
  // flight: that response predates the save and must not overwrite it.
  if (currentState.settingsVersion === capturedSettingsVersion) {
    const incomingSettings = resolveUtubSettings(utub.settings);
    if (
      JSON.stringify(incomingSettings) !== JSON.stringify(currentState.settings)
    ) {
      setState({ settings: incomingSettings });
    }
  } else {
    log("updateUTubOnFindingStaleData — settings saved mid-flight, keeping", {
      utubID,
    });
  }

  if (isSameUTubData({ store: currentState, data: utub })) {
    log("updateUTubOnFindingStaleData — payload matches store, no-op", {
      utubID,
    });
    return;
  }

  if (hasPermissionChange({ store: currentState, data: utub })) {
    applyPermissionFallback({ data: utub });
    return;
  }

  const lockChanged = utub.isLocked !== currentState.isCurrentUTubLocked;
  if (lockChanged) {
    applyLockChange({ data: utub });
  }

  const utubURLs = utub.urls;
  const utubTags = utub.tags;
  const utubMembers = utub.members;
  const urlCountChanged = utubURLs.length !== currentState.urls.length;
  const memberCountChanged = utubMembers.length !== currentState.members.length;
  const tagCountChanged = utubTags.length !== currentState.tags.length;

  updateUTubNameAndDescription({
    utubID: utub.id,
    utubName: utub.name,
    utubDescription: utub.description,
    isCurrentUserOwner: utub.isCreator,
  });

  // Emit before setState so deck-update functions can diff against the current (pre-update) store
  log(
    "STALE_DATA_DETECTED — emitting before setState so deck-diff sees old store",
    {
      utubID: utub.id,
      newUrlCount: utubURLs.length,
      newTagCount: utubTags.length,
      newMemberCount: utubMembers.length,
    },
  );
  setBackgroundRefreshActive({ active: isBackgroundRefresh });
  try {
    emit(AppEvents.STALE_DATA_DETECTED, {
      utubID: utub.id,
      urls: utubURLs,
      tags: utubTags,
      members: utubMembers,
    });
  } finally {
    setBackgroundRefreshActive({ active: false });
  }

  // Sync store; selectedTagIDs filtering is handled by filtering.js's STALE_DATA_DETECTED listener
  setState({
    urls: utubURLs,
    tags: utubTags,
    members: utubMembers,
    activeUTubName: utub.name,
    activeUTubDescription: utub.description,
  });
  syncSidebarUTubName({ utubID: utub.id, utubName: utub.name });

  // Re-evaluate onboarding tips against the new store. There is no lock event,
  // so a lock change rides on URL_DECK_CHANGED (its listener re-runs the tips).
  if (urlCountChanged || lockChanged) emit(AppEvents.URL_DECK_CHANGED);
  if (memberCountChanged) emit(AppEvents.MEMBER_DECK_CHANGED);
  if (tagCountChanged) emit(AppEvents.TAG_DECK_CHANGED);
}

// Clear, then set on the next tick, so a repeated identical message is
// re-announced by the polite live region.
function announceOnNextTick({
  selector,
  message,
}: {
  selector: string;
  message: string;
}): void {
  $(selector).text("");
  setTimeout(() => $(selector).text(message), 0);
}

function sortedByID<Item extends { id: number } | { utubUrlID: number }>({
  items,
}: {
  items: Item[];
}): Item[] {
  const idOf = (item: Item): number =>
    "id" in item ? item.id : item.utubUrlID;
  return [...items].sort((first, second) => idOf(first) - idOf(second));
}

// Explicit, fixed-key-order projection so store items built client-side with a
// different key order or array order still compare equal to the payload.
function projectUTubContent({
  urls,
  tags,
  members,
  name,
  description,
  isLocked,
  isCreator,
  isCoCreator,
  createdByUserID,
}: {
  urls: UtubDetail["urls"];
  tags: UtubDetail["tags"];
  members: UtubDetail["members"];
  name: string | null;
  description: string | null;
  isLocked: boolean;
  isCreator: boolean;
  isCoCreator: boolean;
  createdByUserID: number | null;
}): string {
  return JSON.stringify({
    urls: sortedByID({ items: urls }).map((url) => ({
      utubUrlID: url.utubUrlID,
      urlString: url.urlString,
      urlTitle: url.urlTitle,
      canDelete: url.canDelete,
      utubUrlTagIDs: [...url.utubUrlTagIDs].sort(
        (first, second) => first - second,
      ),
    })),
    tags: sortedByID({ items: tags }).map((tag) => ({
      id: tag.id,
      tagString: tag.tagString,
      tagApplied: tag.tagApplied,
    })),
    members: sortedByID({ items: members }).map((member) => ({
      id: member.id,
      username: member.username,
      memberRole: member.memberRole,
    })),
    name: name ?? "",
    description: description ?? "",
    isLocked,
    isCreator,
    isCoCreator,
    createdByUserID,
  });
}

function isSameUTubData({
  store,
  data,
}: {
  store: AppState;
  data: UtubDetail;
}): boolean {
  return (
    projectUTubContent({
      urls: store.urls,
      tags: store.tags,
      members: store.members,
      name: store.activeUTubName,
      description: store.activeUTubDescription,
      isLocked: store.isCurrentUTubLocked,
      isCreator: store.isCurrentUserOwner,
      isCoCreator: store.isCoCreator,
      createdByUserID: store.utubOwnerID,
    }) ===
    projectUTubContent({
      urls: data.urls,
      tags: data.tags,
      members: data.members,
      name: data.name,
      description: data.description,
      isLocked: data.isLocked,
      isCreator: data.isCreator,
      isCoCreator: data.isCoCreator,
      createdByUserID: data.createdByUserID,
    })
  );
}

// Permission-bearing fields that the in-place diff cannot re-render. Added or
// removed URLs never count: only a canDelete flip on a URL present in both.
function hasPermissionChange({
  store,
  data,
}: {
  store: AppState;
  data: UtubDetail;
}): boolean {
  if (
    data.isCreator !== store.isCurrentUserOwner ||
    data.isCoCreator !== store.isCoCreator ||
    data.createdByUserID !== store.utubOwnerID
  ) {
    return true;
  }
  const storeCanDelete = new Map(
    store.urls.map((url) => [url.utubUrlID, url.canDelete]),
  );
  return data.urls.some(
    (url) =>
      storeCanDelete.has(url.utubUrlID) &&
      storeCanDelete.get(url.utubUrlID) !== url.canDelete,
  );
}

// Patches the sidebar entry (store + role/lock icon) for the refreshed UTub.
function syncSidebarUTubEntry({ data }: { data: UtubDetail }): void {
  // Fail closed to the least-privileged icon if the current user is missing.
  const memberRole =
    data.members.find((member) => member.id === data.currentUser)?.memberRole ??
    APP_CONFIG.constants.MEMBER_ROLES.MEMBER;
  setState({
    utubs: getState().utubs.map((utubSummary) =>
      utubSummary.id === data.id
        ? { ...utubSummary, memberRole, isLocked: data.isLocked }
        : utubSummary,
    ),
  });
  $(`.UTubSelector[utubid=${data.id}] .memberRole`).replaceWith(
    makeUTubRoleIcon({ memberRole, isLocked: data.isLocked }),
  );
}

// Patches the matching utubs summary name in the store (no-op when unchanged).
function syncSidebarUTubName({
  utubID,
  utubName,
}: {
  utubID: number;
  utubName: string;
}): void {
  const { utubs } = getState();
  if (
    !utubs.some(
      (utubSummary) =>
        utubSummary.id === utubID && utubSummary.name !== utubName,
    )
  ) {
    return;
  }
  setState({
    utubs: utubs.map((utubSummary) =>
      utubSummary.id === utubID
        ? { ...utubSummary, name: utubName }
        : utubSummary,
    ),
  });
}

// Additive: the caller continues into the normal diff afterwards.
function applyLockChange({ data }: { data: UtubDetail }): void {
  setState({ isCurrentUTubLocked: data.isLocked });
  $("body").toggleClass("utub-locked", data.isLocked);
  $("#URLDeckLockIcon").toggleClass("hidden", !data.isLocked);
  syncSidebarUTubEntry({ data });
  announceOnNextTick({
    selector: "#URLDeckOutcomeAnnouncement",
    message: data.isLocked
      ? APP_CONFIG.strings.UTUB_IS_LOCKED
      : APP_CONFIG.strings.UTUB_UNLOCKED_ANNOUNCEMENT,
  });
}

// Rare: a role/permission change is reconciled by rebuilding the whole UTub, as
// the post-transfer reconciliation does. buildSelectedUTub emits UTUB_SELECTED,
// which re-runs the onboarding tips, so no deck-changed events are emitted here.
function applyPermissionFallback({ data }: { data: UtubDetail }): void {
  const mobile = isMobile();
  const panelBefore = getCurrentMobilePanel();

  buildSelectedUTub({ selectedUTub: data, keepSettings: true });
  syncSidebarUTubEntry({ data });

  if (!mobile) return;
  setCurrentMobilePanel({ mobilePanel: panelBefore });
  switch (panelBefore) {
    case "members":
      setMobileUIWhenMemberDeckSelected();
      break;
    case "urls":
      setMobileUIWhenUTubSelectedOrURLNavSelected();
      break;
    case "utubs":
      setMobileUIWhenUTubDeckSelected();
      break;
    case "trash":
      // Trash is not UTub-scoped: nothing to re-apply, and the panel must not be re-shown.
      break;
  }
}

function updateUTubNameAndDescription({
  utubID,
  utubName,
  utubDescription,
  isCurrentUserOwner,
}: {
  utubID: number;
  utubName: string;
  utubDescription: string;
  isCurrentUserOwner: boolean;
}): void {
  const utubNameElem = $("#URLDeckHeader");
  const utubNameInUTubDeckElem = $(`.UTubSelector[utubid=${utubID}] .UTubName`);

  if (utubNameElem.text() !== utubName) {
    utubNameElem.text(utubName);
  }
  // Independent of the header: the sidebar entry can drift on its own.
  if (utubNameInUTubDeckElem.text() !== utubName) {
    utubNameInUTubDeckElem.text(utubName);
  }

  // Read before the final setState writes the new description, so an unchanged
  // description re-runs none of the helper's side effects.
  if ((getState().activeUTubDescription ?? "") !== (utubDescription ?? "")) {
    applyUTubDescriptionVisibility({
      utubID,
      utubDescription,
      isCurrentUserOwner,
    });
  }

  fitUTubHeaderAndSubheader();
  // The open mobile edit panel compares against this stored text (no-op if unbound).
  syncUTubEditPanelDirtyState();
}
