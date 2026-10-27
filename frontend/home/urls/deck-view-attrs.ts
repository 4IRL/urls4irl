import { $ } from "../../lib/globals.js";
import { debug } from "../../lib/debug.js";
import { getState, subscribe } from "../../store/app-store.js";
import { armFocusReturnSuppression } from "./cards/focus-return.js";
import { refreshDateAddedBadges } from "./cards/adder-badge.js";
import {
  effectiveDensity,
  effectiveHideDateAdded,
  effectiveViewMode,
} from "./view-settings.js";

const log = debug("urls-deck-attrs");

const DECK_SELECTOR = "#URLDeck";
const URL_ROW_SELECTOR = ".urlRow";
const ALLOW_SHORT_LINKS_ATTR = "data-allow-short-links";

// Controls a deck attribute can hide (see the matching rules in urls.css). A
// focused element matching one of these after an attribute write has just been
// hidden.
const HIDE_COPY_ATTR = "data-hide-copy";
const HIDE_SHORT_LINK_ATTR = "data-hide-short-link";
const HIDE_DATE_ATTR = "data-hide-date";
const SWIPE_DELETE_ATTR = "data-swipe-delete";
const HIDE_ATTRS = [HIDE_COPY_ATTR, HIDE_SHORT_LINK_ATTR, HIDE_DATE_ATTR];

const HIDDEN_BY_ATTRIBUTE_SELECTORS: string[] = [
  `${DECK_SELECTOR}[${ALLOW_SHORT_LINKS_ATTR}="false"] .urlBtnShortLink`,
  `${DECK_SELECTOR}[${HIDE_COPY_ATTR}="true"] .urlBtnCopy`,
  `${DECK_SELECTOR}[${HIDE_SHORT_LINK_ATTR}="true"] .urlBtnShortLink`,
];

/**
 * Runs a deck-attribute write; if it hides the control that held focus, moves
 * focus to that card's `.urlRow` (never `body`) without marking the card selected.
 */
export function withHiddenControlFocusFallback(write: () => void): void {
  const focused = document.activeElement;
  write();
  if (!(focused instanceof Element)) return;
  const wasHidden = HIDDEN_BY_ATTRIBUTE_SELECTORS.some((selector) =>
    focused.matches(selector),
  );
  if (!wasHidden) return;
  const urlRow = focused.closest<HTMLElement>(URL_ROW_SELECTOR);
  if (urlRow === null) return;
  armFocusReturnSuppression($(urlRow));
  urlRow.focus();
  log("focus moved from hidden control to its card row");
}

/** Mirrors the shared URL-deck policy onto `#URLDeck` data attributes for CSS. */
export function applyUrlDeckPolicyAttrs(): void {
  const deck = document.querySelector<HTMLElement>(DECK_SELECTOR);
  if (deck === null) {
    log("applyUrlDeckPolicyAttrs — #URLDeck missing, skipping");
    return;
  }
  const allowShortLinks = getState().settings?.urls.allow_short_links ?? true;
  withHiddenControlFocusFallback(() => {
    deck.setAttribute(ALLOW_SHORT_LINKS_ATTR, String(allowShortLinks));
  });
}

/**
 * Mirrors the member's personal hides onto `#URLDeck` and applies the effective
 * view mode and density to `body`. With no UTub selected the deck attributes are
 * cleared and the Display preferences apply.
 */
export function applyUrlDeckViewSettings(): void {
  const deck = document.querySelector<HTMLElement>(DECK_SELECTOR);
  if (deck === null) {
    log("applyUrlDeckViewSettings — #URLDeck missing, skipping");
    return;
  }
  const { activeUTubID, memberSettings } = getState();
  withHiddenControlFocusFallback(() => {
    if (activeUTubID === null) {
      HIDE_ATTRS.forEach((attr) => deck.removeAttribute(attr));
      deck.removeAttribute(SWIPE_DELETE_ATTR);
    } else {
      const urlsSettings = memberSettings?.urls;
      deck.setAttribute(
        SWIPE_DELETE_ATTR,
        urlsSettings?.disable_swipe_delete === true ? "off" : "on",
      );
      deck.setAttribute(
        HIDE_COPY_ATTR,
        String(urlsSettings?.hide_copy_button ?? false),
      );
      deck.setAttribute(
        HIDE_SHORT_LINK_ATTR,
        String(urlsSettings?.hide_short_link_button ?? false),
      );
      deck.setAttribute(
        HIDE_DATE_ATTR,
        String(urlsSettings?.hide_date_added ?? false),
      );
    }
  });
  // Same plain dataset writes as applyDefaultViewMode/Density (filtering.ts),
  // written here to avoid an import cycle through the card modules.
  document.body.dataset.view = effectiveViewMode();
  document.body.dataset.density = effectiveDensity();
}

/**
 * True when the card's short-link button is hidden by a deck attribute (policy
 * off or a personal hide), so focus cannot rest on it. Matches on the selector,
 * not on computed layout.
 */
export function isShortLinkButtonHiddenByAttribute(
  button: Element | null,
): boolean {
  if (button === null) return true;
  return HIDDEN_BY_ATTRIBUTE_SELECTORS.some((selector) =>
    button.matches(selector),
  );
}

/**
 * Where focus should return for a card's short-link button: the button, or the
 * card's `.urlRow` when the button is hidden by a deck attribute.
 */
export function shortLinkFocusTarget(urlCard: JQuery): JQuery {
  const button = urlCard.find(".urlBtnShortLink");
  if (button.length > 0 && !isShortLinkButtonHiddenByAttribute(button[0])) {
    return button;
  }
  return urlCard.is(URL_ROW_SELECTOR)
    ? urlCard
    : urlCard.closest(URL_ROW_SELECTOR);
}

/** Applies the attributes now and on every settings / active-UTub change. */
export function initUrlDeckPolicyAttrs(): () => void {
  applyUrlDeckPolicyAttrs();
  applyUrlDeckViewSettings();
  let renderedHideDate = effectiveHideDateAdded();
  return subscribe((changedKeys) => {
    if (
      changedKeys.includes("settings") ||
      changedKeys.includes("activeUTubID")
    ) {
      applyUrlDeckPolicyAttrs();
    }
    if (
      changedKeys.includes("memberSettings") ||
      changedKeys.includes("preferences") ||
      changedKeys.includes("activeUTubID")
    ) {
      applyUrlDeckViewSettings();
      const hideDate = effectiveHideDateAdded();
      if (hideDate !== renderedHideDate) {
        renderedHideDate = hideDate;
        refreshDateAddedBadges();
      }
    }
  });
}
