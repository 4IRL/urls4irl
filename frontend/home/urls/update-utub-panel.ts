import { $ } from "../../lib/globals.js";
import { KEYS } from "../../lib/constants.js";
import { getState } from "../../store/app-store.js";
import { on, AppEvents } from "../../lib/event-bus.js";
import { clearOpenForm } from "../../lib/modal-tracking.js";
import { isCoarsePointer } from "../mobile.js";
import {
  updateUTubNameShowInput,
  updateUTubNameHideInput,
  clearNameSubmitInFlight,
} from "./update-name.js";
import {
  updateUTubDescriptionShowInput,
  updateUTubDescriptionHideInput,
  clearDescriptionSubmitInFlight,
} from "./update-description.js";
import { clearFieldSavedTick } from "./field-saved-tick.js";
import { deselectAllURLs } from "./cards/selection.js";
import { isMultiSelectActive } from "./bulk-actions/bulk-mode.js";

/**
 * Mobile-only orchestrator for the consolidated UTub edit panel. Opens/closes
 * the existing UTub name and description forms together via the single
 * `#utubEditPanelToggle` button, without touching the desktop-only pencil-driven
 * open paths. Acts as a third orchestrator that calls into `update-name.ts` and
 * `update-description.ts` rather than extending their existing mutual-import
 * cycle.
 */

// Selecting a URL card while the panel is open closes it. Registered exactly
// once at module load (not per UTub switch) — the event bus keys handlers by
// function reference with no dedupe, so re-subscribing on every switch would
// leak listeners. The closure reads the currently-selected UTub id from app
// state (no `utubID` is in lexical scope here), so closing threads the correct
// id into `closeUTubEditPanel` and preserves the empty-description re-arm. The
// open-panel guard guarantees a UTub is selected, so `activeUTubID` is non-null
// whenever this fires.
on(AppEvents.URL_CARD_SELECTED, () => {
  if ($("#utubEditPanelClose").hasClass("hidden")) return;
  closeUTubEditPanel(getState().activeUTubID);
});

// Binds the toggle/close/Escape handlers for the consolidated panel. Only binds
// on coarse-pointer (touch) devices — the pencil-driven path remains the sole
// desktop entry point. Called once per UTub switch, so the button bindings use
// `offAndOnExact` and the document-level keydown uses `offAndOn` (the
// established convention for document handlers) for idempotent rebinds.
export function setupUTubEditPanelToggle(utubID: number): void {
  if (!isCoarsePointer()) return;

  $("#utubEditPanelToggle").offAndOnExact("click.utubEditPanel", () =>
    openUTubEditPanel(utubID),
  );

  $("#utubEditPanelClose").offAndOnExact("click.utubEditPanel", () =>
    closeUTubEditPanel(utubID),
  );

  // Panel-level Escape: close the whole panel while it is open, then stop
  // propagation so the keypress does not also reach a per-field Escape case
  // still listening underneath. Bound at document level (mirroring the
  // name-field pattern) but scoped to the whole panel.
  $(document).offAndOn("keydown.utubEditPanel", function (keyEvent): void {
    if (keyEvent.key !== KEYS.ESCAPE) return;
    if ($("#utubEditPanelClose").hasClass("hidden")) return;
    closeUTubEditPanel(utubID);
    keyEvent.stopPropagation();
  });
}

// Opens both the UTub name and description forms together (mobile only).
export function openUTubEditPanel(utubID: number): void {
  // Gate the consolidated mobile editor on multi-select mode: its toggle is
  // CSS-hidden in mode, but block the open too so the editors can never take
  // over the selection-context header (deselectAllURLs() below only clears the
  // single-select field, so the multi-select set would strand otherwise).
  if (isMultiSelectActive()) return;
  deselectAllURLs();

  // Call the internal Show functions directly, bypassing the pencil-click
  // wrapper closures — so the sibling-hide mutual exclusion never triggers and
  // both fields open together.
  updateUTubNameShowInput(utubID);
  updateUTubDescriptionShowInput(utubID);

  // Swap toggle -> close button visibility.
  $("#utubEditPanelToggle").addClass("hidden");
  $("#utubEditPanelClose").removeClass("hidden");

  // Each Show function bound its own per-field window click-outside listener,
  // whose ignore-list only covers its OWN field's wrap. Left un-neutralized,
  // clicking inside one field would fall through the other's listener and close
  // it. Unbind both and bind a single unified listener scoped to the whole
  // panel.
  $(window).off(".updateUTubname").off(".updateUTubDescription");

  $(window).offAndOn("click.utubEditPanel", function (windowClickEvent): void {
    const target = $(windowClickEvent.target);
    if (
      target.closest("#UTubNameOuterUpdateWrap").length ||
      target.closest("#UTubDescriptionSubheaderOuterWrap").length ||
      target.closest("#utubEditPanelToggle").length ||
      target.closest("#utubEditPanelClose").length
    )
      return;
    closeUTubEditPanel(utubID);
  });
}

// Low-level idempotent teardown: hides both fields and restores button
// visibility, with NO focus-return. Called by routine, non-user-initiated
// resets (UTub switch, UTub delete).
export function resetUTubEditPanelState(utubID: number | null = null): void {
  // Flip the panel-open signal to "closed" FIRST — before the Hide calls — so
  // the per-field Hide functions (guarded on `!#utubEditPanelClose.hidden`) take
  // their normal restore-chrome + collapse path here on a true panel close,
  // while a per-field submit (panel still open) takes the keep-open path. This
  // is the single source of truth for open vs. closed; no separate state field.
  $("#utubEditPanelClose").addClass("hidden");
  $("#utubEditPanelToggle").removeClass("hidden");

  // Any pending Saved✓ fade timer must be killed before the fields are torn
  // down, so a stale timer never mutates a collapsed/hidden field.
  clearFieldSavedTick($("#utubNameSavedTick"));
  clearFieldSavedTick($("#utubDescriptionSavedTick"));

  // Clear the per-field in-flight submit guards (+ their aria-disabled
  // reflection). These module-level flags are not otherwise reset on a routine
  // UTub switch, so without this a submit that was in flight on the old UTub
  // would leave the flag stuck true and silently block a legit submit on the
  // next UTub until the stale request settles (DD-1).
  clearNameSubmitInFlight();
  clearDescriptionSubmitInFlight();

  updateUTubNameHideInput();
  updateUTubDescriptionHideInput(utubID);

  // Always clean up the unified click-outside listener, whether the panel
  // closed via the wrapper or via a routine UTub switch.
  $(window).off("click.utubEditPanel");

  // The panel-open form is only ever tracked while the panel is genuinely open;
  // clear it on every close path routed through here (Close button, Escape,
  // click-outside, URL_CARD_SELECTED, routine UTub-switch teardown). Mirrors
  // closeURLEditPanel's clearOpenForm() precedent on the card side.
  clearOpenForm();
}

// Higher-level wrapper for user-initiated closes (close button, Escape,
// click-outside): tears down then returns focus to the toggle button.
export function closeUTubEditPanel(utubID: number | null = null): void {
  resetUTubEditPanelState(utubID);
  $("#utubEditPanelToggle")[0]?.focus();
}

// Owner-gated visibility for the toggle button, mirroring the desktop pencils'
// ownership gate. Separate from `setupUTubEditPanelToggle` (binding vs.
// visibility are distinct concerns).
export function setUTubEditPanelToggleVisibility(): void {
  if (
    isCoarsePointer() &&
    getState().isCurrentUserOwner &&
    !getState().isCurrentUTubLocked
  ) {
    $("#utubEditPanelToggle").removeClass("hidden");
  } else {
    $("#utubEditPanelToggle").addClass("hidden");
  }
}
