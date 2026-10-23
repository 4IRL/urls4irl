/**
 * Leaf helpers for a URL card's short-link state (the "link active" status row,
 * its Revoke button and the short-link button's tooltip). No card-flow imports,
 * so the address-edit helper (`apply-url-string.ts`) and every edit-panel hook
 * point can use them without an import cycle. Building and re-rendering the row
 * lives in `short-link.ts`, next to the revoke flow it triggers.
 */

import type { UtubUrlItem } from "../../../types/url.js";

import { $ } from "../../../lib/globals.js";
import { getState } from "../../../store/app-store.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { fillTemplate } from "../../../lib/string-template.js";
import {
  applyHoverTooltip,
  disposeTooltipsWithin,
} from "../../../lib/tooltips.js";
import { isURLEditFormOpen } from "./utils.js";

export const SHORT_LINK_STATUS_ROW_SELECTOR = ".shortLinkStatusRow";
export const SHORT_LINK_REVOKE_SELECTOR = ".shortLinkRevoke";
const SHORT_LINK_BTN_SELECTOR = ".urlBtnShortLink";
const SHORT_LINK_TOOLTIP_CLASS = "urlBtnShortLink-tooltip";

/** True when the store holds an active short link for this URL. */
export function hasActiveShortLink({
  utubUrlID,
}: {
  utubUrlID: number;
}): boolean {
  return getState().urls.some(
    (url: UtubUrlItem) =>
      url.utubUrlID === utubUrlID && typeof url.shortLinkExpiresAt === "string",
  );
}

/** Locale date for a short link's `expiresAt` (e.g. "Oct 27, 2026"). */
export function formatShortLinkExpiry(expiresAt: string): string {
  return new Date(expiresAt).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/** The short-link button's tooltip / aria-label for a link that expires at `expiresAt` (null = no link). */
export function shortLinkTooltipTitle({
  expiresAt,
}: {
  expiresAt: string | null;
}): string {
  if (expiresAt === null) return APP_CONFIG.strings.SHORT_LINK_TOOLTIP;
  return fillTemplate({
    template: APP_CONFIG.strings.SHORT_LINK_TOOLTIP_ACTIVE,
    values: { date: formatShortLinkExpiry(expiresAt) },
  });
}

/** Re-labels the card's short-link button (aria-label and the desktop hover tooltip). */
export function setShortLinkBtnTooltip({
  urlCard,
  expiresAt,
}: {
  urlCard: JQuery;
  expiresAt: string | null;
}): void {
  const button = urlCard.find(SHORT_LINK_BTN_SELECTOR);
  if (button.length === 0) return;
  // The Bootstrap instance caches its title, so rebuild it with the new one.
  disposeTooltipsWithin(button);
  applyHoverTooltip({
    btn: button,
    tooltip: {
      title: shortLinkTooltipTitle({ expiresAt }),
      customClass: SHORT_LINK_TOOLTIP_CLASS,
    },
  });
}

/** Removes the status row (and with it the Revoke button). */
export function removeShortLinkStatusRow(urlCard: JQuery): void {
  urlCard.find(SHORT_LINK_STATUS_ROW_SELECTOR).remove();
}

/** The link is gone from this card: no status row, no Revoke, plain tooltip. */
export function clearShortLinkFromCard(urlCard: JQuery): void {
  removeShortLinkStatusRow(urlCard);
  setShortLinkBtnTooltip({ urlCard, expiresAt: null });
}

/**
 * Hides the status row while a URL, title or tag edit panel is open on the card,
 * and takes Revoke out of the tab order. Mirrors how the short-link button hides.
 */
export function hideShortLinkStatus(urlCard: JQuery): void {
  urlCard.find(SHORT_LINK_STATUS_ROW_SELECTOR).addClass("hidden");
  urlCard.find(SHORT_LINK_REVOKE_SELECTOR).disableTab();
}

/**
 * Shows the status row again once the panel closes (a no-op while the URL or
 * title form is still open). A row the edit removed stays absent: this only
 * reveals what is still rendered.
 */
export function restoreShortLinkStatus(urlCard: JQuery): void {
  if (isURLEditFormOpen({ urlCard })) return;
  urlCard.find(SHORT_LINK_STATUS_ROW_SELECTOR).removeClass("hidden");
  if (urlCard.attr("urlSelected") === "true") {
    urlCard.find(SHORT_LINK_REVOKE_SELECTOR).enableTab();
  }
}

/** True while an edit panel hides the card's short-link button, or the URL or title form is open (so the status row stays hidden). */
export function isShortLinkHiddenForEdit(urlCard: JQuery): boolean {
  return (
    urlCard.find(SHORT_LINK_BTN_SELECTOR).hasClass("hidden") ||
    isURLEditFormOpen({ urlCard })
  );
}

/** Appends "Its short link was removed." to an address-edit banner message when the edit removed a link. */
export function withShortLinkRemovedSuffix({
  message,
  linkRemoved,
}: {
  message: string;
  linkRemoved: boolean;
}): string {
  return linkRemoved
    ? `${message} ${APP_CONFIG.strings.SHORT_LINK_REMOVED_SUFFIX}`
    : message;
}

/** Writes an outcome message to the deck's polite live region. */
export function announceInDeck(message: string): void {
  $("#URLDeckOutcomeAnnouncement").text(message);
}
