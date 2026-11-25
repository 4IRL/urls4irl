/**
 * One banner per tag-policy refusal.
 *
 * Every refusal handler (and later the policy-flip observers) goes through
 * `showPolicyBanner`, so a refusal is explained exactly once, never moves focus,
 * and uses the right surface for the context: the URL deck banner on desktop and
 * with the Tag sheet closed, the blocked control's own note while the sheet is open.
 *
 * `runAsRefusal` lets a handler mark the message it owns while it learns the
 * policy, so a store observer reacting to that learn step can tell whether the
 * handler already explains the change.
 */

import { $ } from "../../lib/globals.js";
import { showDisabledReasonNote } from "../../lib/disabled-reason.js";
import { showURLDeckBannerError } from "../urls/deck.js";
import { isMobile } from "../mobile.js";
import { learnPolicyOff } from "../utubs/policy.js";
import { isTagSheetOpen } from "./sheet.js";

const BANNER_SELECTOR = "#URLDeckErrorIndicator";
const BANNER_SHOWING_CLASS = "URLDeckErrorIndicatorShow";

/**
 * Whether a programmatic focus on a tag-deck control would land. The deck controls
 * are inert behind a closed mobile sheet, so focus would silently fall to <body>.
 */
export function canFocusTagDeckControl(): boolean {
  return !(isMobile() && !isTagSheetOpen());
}

/** The errorCode of a 403 response body, or null for anything else. */
export function getForbiddenErrorCode(xhr: JQuery.jqXHR): number | null {
  if (xhr.status !== 403) return null;
  const code = (xhr.responseJSON as { errorCode?: unknown } | undefined)
    ?.errorCode;
  return typeof code === "number" ? code : null;
}

let ownedMessage: string | null = null;

/**
 * Shows the reason for a refused tag write once and without taking focus.
 *
 * @param message - The reason text.
 * @param control - The control that was refused. Read only while the Tag sheet is
 *   open: the reason then goes in that control's note instead of the deck banner.
 *   Without it, an open sheet falls back to the deck banner (never a silent no-op).
 */
export function showPolicyBanner({
  message,
  control,
}: {
  message: string;
  control?: HTMLElement;
}): void {
  if (isTagSheetOpen() && control !== undefined) {
    showDisabledReasonNote({ element: control, reason: message });
    return;
  }
  const banner = $(BANNER_SELECTOR);
  const alreadyShowingSameText =
    banner.hasClass(BANNER_SHOWING_CLASS) && banner.text() === message;
  if (alreadyShowingSameText) return;
  showURLDeckBannerError(message, { takeFocus: false });
}

/**
 * Runs `callback` with `message` marked as the refusal message in flight, then
 * clears the mark (also when the callback throws).
 */
export function runAsRefusal({
  message,
  callback,
}: {
  message: string;
  callback: () => void;
}): void {
  ownedMessage = message;
  try {
    callback();
  } finally {
    ownedMessage = null;
  }
}

/**
 * Shared tail of every URL-side tagging refusal (the caller has already closed its
 * form, picker or modal): restore focus to the triggering control, learn
 * `tags.members_can_tag` as off inside `runAsRefusal`, then explain once through
 * the banner.
 *
 * @param message - The reason text this refusal shows.
 * @param utubID - The UTub the request was made for (a switched UTub learns nothing).
 * @param focusTarget - The control to return focus to; omit to leave focus alone.
 * @param control - The refused control, forwarded to `showPolicyBanner`.
 */
export function handleTaggingRefusal({
  message,
  utubID,
  focusTarget,
  control,
}: {
  message: string;
  utubID: number | null;
  focusTarget?: HTMLElement | null;
  control?: HTMLElement;
}): void {
  // Focus first: learning the policy can make URL controls react (disable or inert
  // them), and focus() on a disabled control silently does nothing.
  focusTarget?.focus();
  runAsRefusal({
    message,
    callback: () => {
      if (utubID !== null) {
        learnPolicyOff({ utubID, key: "tags.members_can_tag" });
      }
    },
  });
  showPolicyBanner({ message, control });
}

/** The refusal message currently owned by a handler, or null. */
export function getRefusalOwnedMessage(): string | null {
  return ownedMessage;
}
