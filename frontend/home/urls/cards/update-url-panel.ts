import { $ } from "../../../lib/globals.js";
import { KEYS } from "../../../lib/constants.js";
import { clearOpenForm, getOpenForm } from "../../../lib/modal-tracking.js";
import { HOME_FORM } from "../../../types/metrics-dim-values.js";
import {
  showUpdateURLTitleForm,
  hideAndResetUpdateURLTitleForm,
  clearTitleSubmitInFlight,
} from "./update-title.js";
import {
  showUpdateURLStringForm,
  hideAndResetUpdateURLStringForm,
  clearStringSubmitInFlight,
} from "./update-string.js";
import { clearFieldSavedTick } from "../field-saved-tick.js";
import { enableClickOnSelectedURLCardToHide } from "./selection.js";

// Opens the consolidated URL edit panel on mobile: the URL title and URL string
// forms open together. Mirrors the UTub-level orchestrator (update-utub-panel.ts)
// by calling both existing show functions with `suppressSiblingDisable: true`, so
// neither field hides the other's edit affordance (the mutual-exclusion path
// inline in the update-title.ts/update-string.ts show functions is skipped while
// the panel manages both fields).
export function openURLEditPanel(urlCard: JQuery): void {
  const urlTitleAndShowUpdateIconWrap = urlCard.find(
    ".urlTitleAndUpdateIconWrap",
  );
  const urlStringBtnUpdate = urlCard.find(".urlStringBtnUpdate");

  showUpdateURLTitleForm({
    urlTitleAndShowUpdateIconWrap,
    urlCard,
    suppressSiblingDisable: true,
  });
  showUpdateURLStringForm({
    urlCard,
    urlStringBtnUpdate,
    suppressSiblingDisable: true,
  });

  // Panel-level Escape: closes both fields and returns focus. Bound on document
  // (mirroring setupUTubEditPanelToggle's document-level Escape bind) so it fires
  // regardless of which field has focus; the per-field Escape cases early-return
  // on coarse pointers so the two mechanisms never double-close.
  $(document).offAndOn(
    "keydown.urlEditPanelEscape",
    function (event: JQuery.TriggeredEvent) {
      if (event.key === KEYS.ESCAPE) {
        closeURLEditPanel(urlCard);
        event.stopPropagation();
      }
    },
  );
}

// Low-level teardown: hides/resets both forms with NO focus return, and unbinds
// the panel-level Escape handler. Idempotent — safe to call even if the panel was
// never opened, which is required because deselectURL()'s routine teardown (Step
// 4) calls this on every deselection.
export function resetURLEditPanelState(urlCard: JQuery): void {
  // Clear any pending Saved✓ fade timers first, so a stale timer never toggles
  // opacity back on a torn-down card field after this reset runs.
  clearFieldSavedTick(urlCard.find(".updateUrlTitleWrap .field-saved-tick"));
  clearFieldSavedTick(urlCard.find(".updateUrlStringWrap .field-saved-tick"));

  // Clear the per-field in-flight submit guards (+ their aria-disabled
  // reflection) for this card. The module-level flags are not otherwise reset
  // on a routine card deselect, so without this a submit in flight when the card
  // is deselected would leave the flag stuck true and block the next submit
  // (DD-1). Pass the card's own submit buttons so aria-disabled is removed too.
  clearTitleSubmitInFlight(urlCard.find(".urlTitleSubmitBtnUpdate"));
  clearStringSubmitInFlight(urlCard.find(".urlStringSubmitBtnUpdate"));

  hideAndResetUpdateURLTitleForm({ urlCard, suppressSiblingDisable: true });
  hideAndResetUpdateURLStringForm({ urlCard, suppressSiblingDisable: true });
  $(document).off("keydown.urlEditPanelEscape");

  // Ownership-guarded open-form clear: resetURLEditPanelState is called directly
  // (not via closeURLEditPanel) by the routine, non-user-initiated deselect
  // teardown, so only clear the tracked open form when the registry currently
  // holds THIS card's own field — an unconditional clear would wipe an unrelated
  // open form (e.g. the UTub header panel, or a different card's field) whenever
  // a routine deselect fires while that unrelated form is open. closeURLEditPanel
  // keeps its own unconditional clear for the user-initiated-close case.
  const openForm = getOpenForm();
  if (
    openForm === HOME_FORM.URL_TITLE_EDIT ||
    openForm === HOME_FORM.URL_STRING_EDIT
  ) {
    clearOpenForm();
  }
}

// Higher-level wrapper: routine teardown + focus return to the repurposed trigger
// button (`.urlStringBtnUpdate`) that opened the panel. Called by the panel's own
// Cancel buttons and Escape handler — never by routine, non-user-initiated resets.
// Clears the open-form registry (idempotent) so a mobile close via the panel
// Escape/morphed-Cancel path — which bypasses the per-field handlers' own
// clearOpenForm() — does not leave a stale form that fires a spurious
// UI_FORM_CANCEL{navigation} on the next pagehide (see metrics-client.ts pagehide).
export function closeURLEditPanel(urlCard: JQuery): void {
  resetURLEditPanelState(urlCard);
  // resetURLEditPanelState() tears down both fields with
  // `suppressSiblingDisable: true`, which (post round-2 fix) skips re-arming the
  // card's click.deselectURL handler. On a user-initiated close (Cancel/Escape)
  // the card stays selected, so re-arm tap-to-deselect explicitly here — mirroring
  // the pre-round-2 behavior — while leaving the routine deselectURL() teardown
  // path (urlSelected already "false") untouched.
  if (urlCard.attr("urlSelected")?.toLowerCase() === "true") {
    enableClickOnSelectedURLCardToHide(urlCard);
  }
  clearOpenForm();
  urlCard.find(".urlStringBtnUpdate").trigger("focus");
}
