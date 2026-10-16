import { $ } from "../../lib/globals.js";
import { clearOpenForm } from "../../lib/modal-tracking.js";
import { hideInputs } from "../btns-forms.js";
import {
  isMobile,
  setCurrentMobilePanel,
  setMobileUIWhenUTubNotSelectedOrUTubDeleted,
} from "../mobile.js";
import { setUIWhenNoUTubSelected } from "../init.js";
import { closeTagSheet, isTagSheetOpen } from "../tags/sheet.js";
import { hideInputsAndUpdateUTubDeck, resetUTubDeckIfNoUTubs } from "./deck.js";
import { emit, AppEvents } from "../../lib/event-bus.js";
import { TAG_SHEET_TOGGLE_TRIGGER } from "../../types/metrics-dim-values.js";
import { getNumOfUTubs, updateUTubDeckCount } from "./utils.js";
import { getState, setState } from "../../store/app-store.js";
import { applyAlternatingUTubSelectorBackground } from "./search.js";
import { refreshTrashCount } from "../trash/count.js";

// Purges a UTub from the store and UI without any server call: used after a
// successful delete and when a refresh finds the UTub is gone. Showing a banner
// is the caller's job. `pushHistoryEntry` keeps delete's push-then-replace pair;
// the default only replaces the entry with /home.
export function removeUTubLocally({
  utubID,
  pushHistoryEntry = false,
}: {
  utubID: number;
  pushHistoryEntry?: boolean;
}): void {
  hideInputs();

  // Close modal
  $("#confirmModal").modal("hide");
  clearOpenForm();

  const utubSelector = $(".UTubSelector[utubid=" + utubID + "]");

  // Consume the tag sheet's own history entry (via history.back()) while it is
  // still on top of the stack, BEFORE the history write below — otherwise the
  // sheet's entry is orphaned under the freshly-written /home entry.
  if (isTagSheetOpen())
    closeTagSheet({
      returnFocus: false,
      trigger: TAG_SHEET_TOGGLE_TRIGGER.TAP,
    });

  setTimeout(function () {
    if (pushHistoryEntry) window.history.pushState(null, "", "/home");
    window.history.replaceState(null, "", "/home");
  }, 0);

  const finishRemoval = (): void => {
    utubSelector.remove();
    updateUTubDeckCount();
    applyAlternatingUTubSelectorBackground();

    setState({
      utubs: getState().utubs.filter((utub) => utub.id !== utubID),
      activeUTubID: null,
      activeUTubName: null,
      activeUTubDescription: null,
      isCurrentUserOwner: false,
      isCoCreator: false,
      isCurrentUTubLocked: false,
      utubOwnerID: null,
      urls: [],
      tags: [],
      members: [],
      selectedTagIDs: [],
      selectedURLCardID: null,
      // Defense-in-depth: the UTUB_DELETED subscriber in bulk-actions/index.ts
      // already exits multi-select mode; clear the store here too so a future
      // call site mutating activeUTubID/urls off this path can't strand a
      // stale selection.
      multiSelectMode: false,
      selectedURLCardIDs: [],
    });

    // Inverse of buildSelectedUTub's lock affordance.
    $("body").removeClass("utub-locked");
    $("#URLDeckLockIcon").addClass("hidden");

    // Reset all panels
    setUIWhenNoUTubSelected();

    if (getNumOfUTubs() === 0) {
      resetUTubDeckIfNoUTubs();
      $("#utubTagBtnCreate").hideClass();
    } else {
      hideInputsAndUpdateUTubDeck();
    }
    emit(AppEvents.UTUB_DELETED, { utubID });
    void refreshTrashCount();

    if (isMobile()) {
      setMobileUIWhenUTubNotSelectedOrUTubDeleted();
      setCurrentMobilePanel({ mobilePanel: "utubs" });
    }
  };

  // jQuery never fires a fadeOut callback on an empty set, so a UTub whose
  // selector is already gone from the deck must still be purged from the store.
  if (utubSelector.length === 0) {
    finishRemoval();
    return;
  }
  utubSelector.fadeOut("slow", finishRemoval);
}
