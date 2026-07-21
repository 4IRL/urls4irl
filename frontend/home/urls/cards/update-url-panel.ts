import { $ } from "../../../lib/globals.js";
import { KEYS } from "../../../lib/constants.js";
import { clearOpenForm } from "../../../lib/modal-tracking.js";
import {
  showUpdateURLTitleForm,
  hideAndResetUpdateURLTitleForm,
} from "./update-title.js";
import {
  showUpdateURLStringForm,
  hideAndResetUpdateURLStringForm,
} from "./update-string.js";
import { enableClickOnSelectedURLCardToHide } from "./selection.js";

// Opens the consolidated URL edit panel on mobile: the URL title and URL string
// forms open together. Mirrors the UTub-level orchestrator (update-utub-panel.ts)
// by calling both existing show functions with `suppressSiblingDisable: true`, so
// neither field hides the other's edit affordance (the mutual-exclusion path in
// cards/utils.ts is skipped while the panel manages both fields).
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
  hideAndResetUpdateURLTitleForm({ urlCard, suppressSiblingDisable: true });
  hideAndResetUpdateURLStringForm({ urlCard, suppressSiblingDisable: true });
  $(document).off("keydown.urlEditPanelEscape");
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
