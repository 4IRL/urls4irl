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

function titleInput(urlCard: JQuery): JQuery {
  return urlCard.find(".urlTitleUpdate");
}

function stringInput(urlCard: JQuery): JQuery {
  return urlCard.find(".urlStringUpdate");
}

function trimWrap(urlCard: JQuery): JQuery {
  return urlCard.find(".urlParamTrimWrap");
}

/** Title is dirty when its trimmed input differs from the stored title text. */
export function isTitleDirty(urlCard: JQuery): boolean {
  return (
    getInputValue(titleInput(urlCard)).trim() !==
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
  const getSubmission = trimWrap(urlCard).data(TRIM_SUBMISSION_KEY) as
    | (() => TrimSubmission)
    | undefined;
  if (getSubmission && getSubmission().droppedCount > 0) return true;
  return (
    getInputValue(stringInput(urlCard)).trim() !==
    urlCard.find(".urlString").attr("href")
  );
}

/** Syncs the three confirm buttons of `urlCard`. No-op unless the panel is bound. */
export function syncEditPanelDirtyState(urlCard: JQuery): void {
  if (!urlCard.data(BOUND_KEY)) return;
  setConfirmButtonUnchanged({
    button: urlCard.find(".urlTitleSubmitBtnUpdate"),
    isUnchanged: !isTitleDirty(urlCard),
  });
  const stringUnchanged = !isURLStringDirty(urlCard);
  setConfirmButtonUnchanged({
    button: urlCard.find(".urlStringSubmitBtnUpdate"),
    isUnchanged: stringUnchanged,
  });
  setConfirmButtonUnchanged({
    button: urlCard.find(".urlStringSaveBigBtnUpdate"),
    isUnchanged: stringUnchanged,
  });
}

/** Panel open: binds the recompute triggers and sets the initial state. */
export function bindEditPanelDirtyState(urlCard: JQuery): void {
  if (!isCoarsePointer()) return;
  urlCard.data(BOUND_KEY, true);
  const resync = (): void => syncEditPanelDirtyState(urlCard);
  titleInput(urlCard).off(INPUT_EVENT).on(INPUT_EVENT, resync);
  stringInput(urlCard).off(INPUT_EVENT).on(INPUT_EVENT, resync);
  trimWrap(urlCard).off(TRIM_EVENT).on(TRIM_EVENT, resync);
  syncEditPanelDirtyState(urlCard);
}

/** Panel close: unbinds the triggers and removes the disabled state. Idempotent. */
export function unbindEditPanelDirtyState(urlCard: JQuery): void {
  urlCard.removeData(BOUND_KEY);
  titleInput(urlCard).off(INPUT_EVENT);
  stringInput(urlCard).off(INPUT_EVENT);
  trimWrap(urlCard).off(TRIM_EVENT);
  clearConfirmButtonState(
    urlCard.find(
      ".urlTitleSubmitBtnUpdate, .urlStringSubmitBtnUpdate, .urlStringSaveBigBtnUpdate",
    ),
  );
}
