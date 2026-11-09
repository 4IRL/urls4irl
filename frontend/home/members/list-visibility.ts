import { $ } from "../../lib/globals.js";
import { getState, setState } from "../../store/app-store.js";
import { setRowCountsFromStore } from "../utubs/row-counts.js";
import { refreshDateAddedBadges } from "../urls/cards/adder-badge.js";
import {
  cancelCoMemberCandidatesFetch,
  loadCoMemberCandidates,
} from "./co-member-fetch.js";
import { setMemberDeckForUTub } from "./deck.js";
import { RENDER_KEY } from "./member-combobox.js";

const OPEN_COMBOBOX_SELECTOR = "#createMemberWrap .memberAddComboboxWrap";

// Reconciles every surface that derives from the member list's visibility after
// a refresh wrote the new settings, urls and members to the store. The deck
// total, the UTub row's member segment and the stacked adder badges re-resolve on
// every call (the refresh path never rewrote them before); the co-member
// suggestions only react to an actual flip, `wasHidden !== isHidden`.
export function applyMemberListVisibility({
  wasHidden,
  isHidden,
}: {
  wasHidden: boolean;
  isHidden: boolean;
}): void {
  const { activeUTubID } = getState();
  setMemberDeckForUTub();
  if (activeUTubID !== null) setRowCountsFromStore({ utubID: activeUTubID });
  refreshDateAddedBadges();

  if (wasHidden === isHidden) return;

  const wrap = $(OPEN_COMBOBOX_SELECTOR);
  const render = wrap.data(RENDER_KEY) as (() => void) | undefined;
  if (isHidden) {
    // Cancel first so an in-flight fetch cannot repopulate the suggestions. An
    // aborted fetch never settles, so mark the slice loaded or an open combobox
    // would stay on "Loading matches".
    cancelCoMemberCandidatesFetch();
    setState({ coMemberCandidates: [], coMemberCandidatesLoaded: true });
    if (render) render();
    return;
  }
  if (wrap.length === 0 || activeUTubID === null) return;
  setState({ coMemberCandidatesLoaded: false });
  if (render) render();
  loadCoMemberCandidates(activeUTubID, () => {
    if (render && wrap.parent().length > 0) render();
  });
}
