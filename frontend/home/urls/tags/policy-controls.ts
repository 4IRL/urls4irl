import { $, bootstrap } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { setDisabledReason } from "../../../lib/disabled-reason.js";
import { getState, subscribe } from "../../../store/app-store.js";
import { POLICY_STATE_KEYS, canTag } from "../../utubs/policy.js";

const DECK_SELECTOR = "#URLDeck";
const ADD_TAG_SELECTOR = ".urlTagBtnCreate";
const REMOVE_TAG_SELECTOR = ".urlTagBtnDelete";
const BLOCKABLE_SELECTOR = `${ADD_TAG_SELECTOR}, ${REMOVE_TAG_SELECTOR}`;
// The add button turns into Cancel while its combobox is open; it is never
// blocked in that state (the picker only opens while tagging is allowed).
const CANCEL_MODE_CLASS = "cancel";

// Buttons whose Bootstrap tooltip this module disabled, so unblocking re-enables
// only those (never one a combobox disabled on its own).
const tooltipDisabledByPolicy = new WeakSet<HTMLElement>();

function reasonFor(element: HTMLElement): string {
  return element.matches(ADD_TAG_SELECTOR)
    ? APP_CONFIG.strings.TAG_URLS_NOT_ALLOWED
    : APP_CONFIG.strings.TAG_REMOVE_NOT_ALLOWED;
}

function setBootstrapTooltipBlocked({
  element,
  isBlocked,
}: {
  element: HTMLElement;
  isBlocked: boolean;
}): void {
  const tooltip = bootstrap.Tooltip.getInstance(element);
  if (isBlocked) {
    if (tooltip === null) return;
    tooltip.hide();
    tooltip.disable();
    tooltipDisabledByPolicy.add(element);
  } else if (tooltipDisabledByPolicy.has(element)) {
    tooltipDisabledByPolicy.delete(element);
    tooltip?.enable();
  }
}

function applyToElement({
  element,
  isBlocked,
}: {
  element: HTMLElement;
  isBlocked: boolean;
}): void {
  const blockedNow =
    isBlocked && !element.classList.contains(CANCEL_MODE_CLASS);
  // The reason tooltip must be the only one: turn the Bootstrap tooltip off first.
  setBootstrapTooltipBlocked({ element, isBlocked: blockedNow });
  setDisabledReason({
    element,
    reason: blockedNow ? reasonFor(element) : null,
  });
}

/**
 * Blocks (or restores) every URL card's "Add tag" button and tag-badge remove
 * button under `root` according to the viewer's tagging permission. Idempotent.
 *
 * @param root - Where to look; defaults to the whole URL deck. May itself be one
 *   of the controls.
 */
export function applyURLTagControlReasons(
  root: ParentNode | Element | null = document.querySelector(DECK_SELECTOR),
): void {
  if (root === null) return;
  const isBlocked = !canTag(getState());
  const targets: HTMLElement[] = [];
  if (root instanceof HTMLElement && root.matches(BLOCKABLE_SELECTOR)) {
    targets.push(root);
  }
  root
    .querySelectorAll<HTMLElement>(BLOCKABLE_SELECTOR)
    .forEach((element) => targets.push(element));
  for (const element of targets) applyToElement({ element, isBlocked });
}

/**
 * Releases the blocked-control listeners of controls inside a removed subtree
 * (they live on `document`, so a removed card would otherwise leak them).
 */
function releaseDetachedControls(removed: HTMLElement): void {
  const controls: HTMLElement[] = [];
  if (removed.matches(BLOCKABLE_SELECTOR)) controls.push(removed);
  removed
    .querySelectorAll<HTMLElement>(BLOCKABLE_SELECTOR)
    .forEach((element) => controls.push(element));
  for (const element of controls) {
    if (!element.isConnected) setDisabledReason({ element, reason: null });
  }
}

/**
 * Keeps the URL-side tag controls in step with the tagging permission: reapplies
 * on every relevant store change, and blocks controls on cards and badges built
 * while tagging is off (they are created from many places, after the last store
 * change, so a deck-wide DOM observer is the one place that sees all of them).
 */
export function initURLTagPolicyControls(): () => void {
  applyURLTagControlReasons();
  const unsubscribe = subscribe((changedKeys) => {
    if (!POLICY_STATE_KEYS.some((key) => changedKeys.includes(key))) return;
    applyURLTagControlReasons();
  });

  const deck = $(DECK_SELECTOR)[0];
  const observer =
    deck === undefined
      ? null
      : new MutationObserver((records) => {
          const tagAllowed = canTag(getState());
          for (const record of records) {
            record.removedNodes.forEach((node) => {
              if (node instanceof HTMLElement) releaseDetachedControls(node);
            });
            if (tagAllowed) continue;
            record.addedNodes.forEach((node) => {
              if (node instanceof HTMLElement) applyURLTagControlReasons(node);
            });
          }
        });
  observer?.observe(deck, { childList: true, subtree: true });

  return () => {
    unsubscribe();
    observer?.disconnect();
  };
}
