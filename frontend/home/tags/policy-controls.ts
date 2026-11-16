import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { setDisabledReason } from "../../lib/disabled-reason.js";
import { getState, subscribe } from "../../store/app-store.js";
import {
  dismissAddTagTipIfActive,
  maybeShowNextTip,
} from "../onboarding/nudges.js";
import { POLICY_STATE_KEYS, canDeleteTags, canTag } from "../utubs/policy.js";
import { canFocusTagDeckControl } from "./policy-banner.js";
import {
  closeUTubTagBtnMenuOnUTubTags,
  setTagDeckBtnsOnUpdateAllUTubTagsClosed,
} from "./update-all.js";

const CREATE_BUTTON_SELECTOR = "#utubTagBtnCreate";
const PENCIL_SELECTOR = "#utubTagBtnUpdateAllOpen";
const MENU_OPEN_SELECTOR = "#listTags .tagMenuWrap:not(.hidden)";
function firstElement(selector: string): HTMLElement | null {
  return ($(selector)[0] as HTMLElement | undefined) ?? null;
}

/**
 * Blocks the Tags deck's create button and pencil for a viewer who may not use
 * them. Fail closed on the reason (a blocked control always has one); with no
 * active UTub nothing is blocked because the deck controls are hidden.
 */
export function applyTagDeckControlReasons(): void {
  const state = getState();
  const active = state.activeUTubID !== null;
  const create = firstElement(CREATE_BUTTON_SELECTOR);
  if (create !== null) {
    setDisabledReason({
      element: create,
      reason:
        active && !canTag(state)
          ? APP_CONFIG.strings.TAG_CREATE_NOT_ALLOWED
          : null,
    });
  }
  const pencil = firstElement(PENCIL_SELECTOR);
  if (pencil !== null) {
    setDisabledReason({
      element: pencil,
      reason:
        active && !canDeleteTags(state)
          ? APP_CONFIG.strings.TAG_DELETE_NOT_ALLOWED
          : null,
    });
  }
}

/** Closes an open pencil menu and returns focus to the pencil when it can land. */
function closePencilMenuAfterFlip(): void {
  if ($(MENU_OPEN_SELECTOR).length === 0) return;
  closeUTubTagBtnMenuOnUTubTags();
  setTagDeckBtnsOnUpdateAllUTubTagsClosed();
  if (canFocusTagDeckControl()) firstElement(PENCIL_SELECTOR)?.focus();
}

/**
 * Applies the control reasons now and on every relevant store change, closes the
 * pencil menu when delete turns off while it is open, and tears the add-tag
 * onboarding tip down when tagging turns off.
 */
export function initTagDeckPolicyControls(): () => void {
  let previouslyCanDelete = canDeleteTags(getState());
  let previouslyCanTag = canTag(getState());
  applyTagDeckControlReasons();
  return subscribe((changedKeys) => {
    if (!POLICY_STATE_KEYS.some((key) => changedKeys.includes(key))) return;
    const state = getState();
    const nowCanDelete = canDeleteTags(state);
    const nowCanTag = canTag(state);
    applyTagDeckControlReasons();
    if (previouslyCanDelete && !nowCanDelete) closePencilMenuAfterFlip();
    if (!nowCanTag) dismissAddTagTipIfActive();
    else if (!previouslyCanTag) maybeShowNextTip();
    previouslyCanDelete = nowCanDelete;
    previouslyCanTag = nowCanTag;
  });
}
