import { $, getInputValue } from "../../lib/globals.js";
import { isCoarsePointer } from "../mobile.js";
import {
  clearConfirmButtonState,
  setConfirmButtonUnchanged,
} from "./confirm-btn-state.js";

// Mobile consolidated UTub edit panel: the name ✓ and description ✓ stay disabled
// (aria-disabled + `unchanged`) until their field differs from the stored value.
// Coarse-pointer only; desktop never binds or syncs.

const INPUT_EVENT = "input.utubEditPanelDirty";
const NAME_INPUT = "#utubNameUpdate";
const DESCRIPTION_INPUT = "#utubDescriptionUpdate";
const NAME_SUBMIT = "#utubNameSubmitBtnUpdate";
const DESCRIPTION_SUBMIT = "#utubDescriptionSubmitBtnUpdate";

let isBound = false;

/** Name is dirty when its trimmed input differs from the displayed UTub name. */
export function isUTubNameDirty(): boolean {
  return getInputValue(NAME_INPUT).trim() !== $("#URLDeckHeader").text();
}

/**
 * Description is dirty when its trimmed input differs from the displayed
 * description; a UTub without one stores "" so empty vs empty is unchanged.
 */
export function isUTubDescriptionDirty(): boolean {
  return (
    getInputValue(DESCRIPTION_INPUT).trim() !== $("#URLDeckSubheader").text()
  );
}

/** Syncs both ✓ buttons. No-op unless the panel is open (bound). */
export function syncUTubEditPanelDirtyState(): void {
  if (!isBound) return;
  setConfirmButtonUnchanged({
    button: $(NAME_SUBMIT),
    isUnchanged: !isUTubNameDirty(),
  });
  setConfirmButtonUnchanged({
    button: $(DESCRIPTION_SUBMIT),
    isUnchanged: !isUTubDescriptionDirty(),
  });
}

/** Panel open: binds the recompute triggers and sets the initial state. */
export function bindUTubEditPanelDirtyState(): void {
  if (!isCoarsePointer()) return;
  isBound = true;
  $(NAME_INPUT).off(INPUT_EVENT).on(INPUT_EVENT, syncUTubEditPanelDirtyState);
  $(DESCRIPTION_INPUT)
    .off(INPUT_EVENT)
    .on(INPUT_EVENT, syncUTubEditPanelDirtyState);
  syncUTubEditPanelDirtyState();
}

/** Panel close: unbinds the triggers and removes the disabled state. Idempotent. */
export function unbindUTubEditPanelDirtyState(): void {
  isBound = false;
  $(NAME_INPUT).off(INPUT_EVENT);
  $(DESCRIPTION_INPUT).off(INPUT_EVENT);
  clearConfirmButtonState($(`${NAME_SUBMIT}, ${DESCRIPTION_SUBMIT}`));
}
