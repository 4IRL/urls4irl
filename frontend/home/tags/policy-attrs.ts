import { $ } from "../../lib/globals.js";
import { getState, subscribe } from "../../store/app-store.js";
import { POLICY_STATE_KEYS, canDeleteTags, canTag } from "../utubs/policy.js";

const DECK_SELECTORS = ["#TagDeck", "#URLDeck"] as const;
/**
 * Mirrors the viewer's effective tag permissions onto `#TagDeck` and `#URLDeck`
 * as `data-can-tag` / `data-can-delete-tags` ("true" or "false"). Fail closed:
 * a plain member with no settings loaded reads "false".
 */
export function applyTagPolicyAttrs(): void {
  const state = getState();
  const attrs = {
    "data-can-tag": String(canTag(state)),
    "data-can-delete-tags": String(canDeleteTags(state)),
  };
  for (const selector of DECK_SELECTORS) $(selector).attr(attrs);
}

/** Applies the attributes now and on every relevant store change. */
export function initTagPolicyAttrs(): () => void {
  applyTagPolicyAttrs();
  return subscribe((changedKeys) => {
    if (!POLICY_STATE_KEYS.some((key) => changedKeys.includes(key))) return;
    applyTagPolicyAttrs();
  });
}
