import { getInputValue } from "../../../lib/globals.js";
import { isCoarsePointer } from "../../mobile.js";
import {
  clearConfirmButtonState,
  setConfirmButtonUnchanged,
} from "../confirm-btn-state.js";
import {
  TRIM_RENDERED_EVENT,
  TRIM_SUBMISSION_KEY,
  type TrimSubmission,
} from "../trim/param-trim-block.js";

// Mobile consolidated edit panel: the Title ✓, URL ✓ and "Save URL" buttons stay
// disabled (aria-disabled + `unchanged`) until their field would actually change
// the stored value. Coarse-pointer only; desktop never binds or syncs.

const DIRTY_NAMESPACE = "editPanelDirty";
const INPUT_EVENT = `input.${DIRTY_NAMESPACE}`;
const TRIM_EVENT = `${TRIM_RENDERED_EVENT}.${DIRTY_NAMESPACE}`;
const BOUND_KEY = "editPanelDirtyBound";

const TITLE_INPUT_SELECTOR = ".urlTitleUpdate";
const STRING_INPUT_SELECTOR = ".urlStringUpdate";
const TRIM_WRAP_SELECTOR = ".urlParamTrimWrap";
const TITLE_SUBMIT_SELECTOR = ".urlTitleSubmitBtnUpdate";
const STRING_SUBMIT_SELECTOR = ".urlStringSubmitBtnUpdate";
const STRING_SAVE_SELECTOR = ".urlStringSaveBigBtnUpdate";

/** Title is dirty when its trimmed input differs from the stored title text. */
export function isTitleDirty(urlCard: JQuery): boolean {
  return (
    getInputValue(urlCard.find(TITLE_INPUT_SELECTOR)).trim() !==
    urlCard.find(".urlTitle").text()
  );
}

/**
 * URL is dirty when what would be SUBMITTED differs from the stored href: either
 * the trim block has chips dropped (the submitted string changes even when the
 * text does not) or the trimmed input differs. Reads the drop summary without
 * flushing the trim block's debounce, so it is safe on every keystroke.
 */
export function isURLStringDirty(urlCard: JQuery): boolean {
  const getSubmission = urlCard
    .find(TRIM_WRAP_SELECTOR)
    .data(TRIM_SUBMISSION_KEY) as (() => TrimSubmission) | undefined;
  if (getSubmission && getSubmission().droppedCount > 0) return true;
  return (
    getInputValue(urlCard.find(STRING_INPUT_SELECTOR)).trim() !==
    urlCard.find(".urlString").attr("href")
  );
}

/** Syncs the three confirm buttons of `urlCard`. No-op unless the panel is bound. */
export function syncEditPanelDirtyState(urlCard: JQuery): void {
  if (!urlCard.data(BOUND_KEY)) return;
  setConfirmButtonUnchanged({
    button: urlCard.find(TITLE_SUBMIT_SELECTOR),
    isUnchanged: !isTitleDirty(urlCard),
  });
  const stringUnchanged = !isURLStringDirty(urlCard);
  setConfirmButtonUnchanged({
    button: urlCard.find(STRING_SUBMIT_SELECTOR),
    isUnchanged: stringUnchanged,
  });
  setConfirmButtonUnchanged({
    button: urlCard.find(STRING_SAVE_SELECTOR),
    isUnchanged: stringUnchanged,
  });
}

/** Panel open: binds the recompute triggers and sets the initial state. */
export function bindEditPanelDirtyState(urlCard: JQuery): void {
  if (!isCoarsePointer()) return;
  urlCard.data(BOUND_KEY, true);
  const resync = (): void => syncEditPanelDirtyState(urlCard);
  urlCard.find(TITLE_INPUT_SELECTOR).off(INPUT_EVENT).on(INPUT_EVENT, resync);
  urlCard.find(STRING_INPUT_SELECTOR).off(INPUT_EVENT).on(INPUT_EVENT, resync);
  urlCard.find(TRIM_WRAP_SELECTOR).off(TRIM_EVENT).on(TRIM_EVENT, resync);
  syncEditPanelDirtyState(urlCard);
}

/** Panel close: unbinds the triggers and removes the disabled state. Idempotent. */
export function unbindEditPanelDirtyState(urlCard: JQuery): void {
  urlCard.removeData(BOUND_KEY);
  urlCard.find(TITLE_INPUT_SELECTOR).off(INPUT_EVENT);
  urlCard.find(STRING_INPUT_SELECTOR).off(INPUT_EVENT);
  urlCard.find(TRIM_WRAP_SELECTOR).off(TRIM_EVENT);
  clearConfirmButtonState(
    urlCard.find(
      `${TITLE_SUBMIT_SELECTOR}, ${STRING_SUBMIT_SELECTOR}, ${STRING_SAVE_SELECTOR}`,
    ),
  );
}
