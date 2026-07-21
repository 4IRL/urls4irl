import { $ } from "../../lib/globals.js";
import { KEYS } from "../../lib/constants.js";
import { getState } from "../../store/app-store.js";
import { on, AppEvents } from "../../lib/event-bus.js";
import { isCoarsePointer } from "../mobile.js";
import {
  updateUTubNameShowInput,
  updateUTubNameHideInput,
} from "./update-name.js";
import {
  updateUTubDescriptionShowInput,
  updateUTubDescriptionHideInput,
} from "./update-description.js";
import { deselectAllURLs } from "./cards/selection.js";

/**
 * Mobile-only orchestrator for the consolidated UTub edit panel. Opens/closes
 * the existing UTub name and description forms together via the single
 * `#utubEditPanelToggle` button, without touching the desktop-only pencil-driven
 * open paths. Acts as a third orchestrator that calls into `update-name.ts` and
 * `update-description.ts` rather than extending their existing mutual-import
 * cycle.
 */

// Binds the toggle/close/Escape/URL-selection handlers for the consolidated
// panel. Only binds on coarse-pointer (touch) devices — the pencil-driven path
// remains the sole desktop entry point. Called once per UTub switch, so the
// button bindings use `offAndOnExact` and the document-level keydown uses
// `offAndOn` (the established convention for document handlers) for idempotent
// rebinds.
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

  // Selecting a URL card while the panel is open closes it. NOTE: event-bus
  // `on()` keys handlers by function reference with no rebind-idempotency, so
  // this inline closure is a per-switch listener leak — harmless here since the
  // guard is idempotent and `closeUTubEditPanel()` is safe to call redundantly.
  on(AppEvents.URL_CARD_SELECTED, () => {
    if (!$("#utubEditPanelClose").hasClass("hidden"))
      closeUTubEditPanel(utubID);
  });
}

// Opens both the UTub name and description forms together (mobile only).
export function openUTubEditPanel(utubID: number): void {
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
  updateUTubNameHideInput();
  updateUTubDescriptionHideInput(utubID);

  // Always clean up the unified click-outside listener, whether the panel
  // closed via the wrapper or via a routine UTub switch.
  $(window).off("click.utubEditPanel");

  $("#utubEditPanelClose").addClass("hidden");
  $("#utubEditPanelToggle").removeClass("hidden");
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
