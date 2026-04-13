import { emit, AppEvents } from "../../lib/event-bus.js";
import { $ } from "../../lib/globals.js";

import type { UtubDetail } from "../../types/utub.js";
import { setState } from "../../store/app-store.js";
import { getUTubInfo } from "./selectors.js";

// Handles updating a UTub if found to include stale data
// For example, a user decides to update a URL string to a new URL, but it returns
// saying the URL already exists in the UTub -> yet the user does not see the URL in the UTub?
// This means another user has updated a URL or added a URL with the new URL string, in which
// we should reload the user's UTub to show them the latest data
export async function updateUTubOnFindingStaleData(
  selectedUTubID: number,
): Promise<void> {
  const utub: UtubDetail | null = await getUTubInfo(selectedUTubID);
  if (!utub) return;
  const utubName = utub.name;
  const utubDescription = utub.description;
  updateUTubNameAndDescription(utub.id, utubName, utubDescription);

  const utubURLs = utub.urls;
  const utubTags = utub.tags;
  const utubMembers = utub.members;

  // Emit before setState so deck-update functions can diff against the current (pre-update) store
  emit(AppEvents.STALE_DATA_DETECTED, {
    utubID: utub.id,
    urls: utubURLs,
    tags: utubTags,
    members: utubMembers,
  });

  // Sync store; selectedTagIDs filtering is handled by filtering.js's STALE_DATA_DETECTED listener
  setState({ urls: utubURLs, tags: utubTags, members: utubMembers });
}

function updateUTubNameAndDescription(
  utubID: number,
  utubName: string,
  utubDescription: string,
): void {
  const utubNameElem = $("#URLDeckHeader");
  const utubNameInUTubDeckElem = $(
    "UTubSelector[utubid=" + utubID + "] > .UTubName",
  );
  const utubDescriptionElem = $("#URLDeckSubheader");

  if (utubNameElem.text() !== utubName) {
    utubNameElem.text(utubName);
    utubNameInUTubDeckElem.text(utubName);
  }

  if (utubDescriptionElem.text() !== utubDescription) {
    utubDescriptionElem.text(utubDescription);
  }
}
