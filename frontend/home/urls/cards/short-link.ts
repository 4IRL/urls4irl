/**
 * The share short-link flows of a URL card: "Copy short link" (mint or reuse the
 * link, put it on the clipboard, report in the deck banner), "Revoke" (shared by
 * the copy banner and the card's status row) and the status row itself ("Short
 * link active · expires <date>" plus Revoke), which these flows keep in sync with
 * the app store.
 */

import type { SuccessResponse } from "../../../types/api-helpers.d.ts";
import type { UtubUrlItem } from "../../../types/url.js";

import { $ } from "../../../lib/globals.js";
import { getState, setState } from "../../../store/app-store.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { debug } from "../../../lib/debug.js";
import { fillTemplate } from "../../../lib/string-template.js";
import { emit } from "../../../lib/metrics-client.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";
import { SHORT_LINK_COPY_RESULT } from "../../../types/metrics-dim-values.js";
import { hideConfirmModal, showConfirmModal } from "../../confirm-modal.js";
import { isUtubLockedHandled } from "../../utub-locked.js";
import { showURLDeckBannerError } from "../deck.js";
import {
  URL_DECK_BANNER_MOUNT,
  clearURLOutcomeBanner,
  currentBannerToken,
  rearmBannerAction,
  returnFocusIn,
  showURLOutcomeBanner,
} from "../outcome-banner.js";
import { deleteURLOnStale } from "./get.js";
import {
  clearTimeoutIDAndHideLoadingIcon,
  setTimeoutAndShowURLCardLoadingIcon,
} from "./loading.js";
import { createShortLinkIcon } from "./options/short-link-icon.js";
import {
  SHORT_LINK_STATUS_ROW_SELECTOR,
  announceInDeck,
  formatShortLinkExpiry,
  isShortLinkHiddenForEdit,
  removeShortLinkStatusRow,
  setShortLinkBtnTooltip,
} from "./short-link-state.js";

const log = debug("urls:short-link");

type MintShortLinkResponse = SuccessResponse<"mintShortLink">;

type ShortLinkErrorBody = { message?: string; errorCode?: number | null };

const REQUEST_TIMEOUT_MS = 10_000;
const SELECTED_CARD_SELECTOR = '.urlRow[urlSelected="true"]';
const SHORT_LINK_BTN_SELECTOR = ".urlBtnShortLink";
const SUBMIT_BTN_SELECTOR = "#modalSubmit";
const CONFIRM_MODAL_SELECTOR = "#confirmModal";
const FOCUS_NAMESPACE = "hidden.bs.modal.shortLinkRevokeFocus";
// Mirrors `ShortLinkErrorCodes.SHORT_LINK_NOT_FOUND` (backend/short_links/constants.py).
const SHORT_LINK_NOT_FOUND_ERROR_CODE = 1;

function selectedCardElement(): HTMLElement | null {
  return ($(SELECTED_CARD_SELECTOR)[0] as HTMLElement | undefined) ?? null;
}

function shortLinkBtnOf(utubUrlID: number): JQuery {
  return $(`.urlRow[utuburlid=${utubUrlID}]`).find(SHORT_LINK_BTN_SELECTOR);
}

function errorMessageOf({
  xhr,
  fallback,
}: {
  xhr: JQuery.jqXHR;
  fallback: string;
}): string {
  const body = xhr.responseJSON as ShortLinkErrorBody | undefined;
  return body?.message ?? fallback;
}

/**
 * Makes (or reuses) the card's short link and copies it to the clipboard.
 *
 * The mint request and the clipboard write are deliberately independent: Safari
 * only allows a clipboard write inside the click's user gesture, so with
 * `ClipboardItem` the write starts synchronously with a promise that resolves to
 * the link once the mint returns. Everything after branches on the MINT outcome,
 * never on the clipboard promise alone, so a failed mint can never look like a
 * clipboard fallback.
 */
export async function copyShortLink({
  button,
  urlCard,
  utubID,
  utubUrlID,
}: {
  button: JQuery;
  urlCard: JQuery;
  utubID: number;
  utubUrlID: number;
}): Promise<void> {
  // One request at a time (aria-disabled, not disabled, keeps focus on the button).
  if (button.attr("aria-disabled") === "true") return;
  button.attr("aria-disabled", "true");

  const clickToken = currentBannerToken({ mount: URL_DECK_BANNER_MOUNT });
  const clickCard = selectedCardElement();
  // A newer banner or a different selected card means the user has moved on:
  // this response must neither show a banner nor overwrite their clipboard.
  // Latched: once stale, always stale (reselecting the card must not undo it,
  // since the ClipboardItem write was already abandoned).
  let staleSeen = false;
  const isStale = (): boolean => {
    if (!staleSeen) {
      staleSeen =
        currentBannerToken({ mount: URL_DECK_BANNER_MOUNT }) !== clickToken ||
        selectedCardElement() !== clickCard;
    }
    return staleSeen;
  };

  const loadingTimeoutID = setTimeoutAndShowURLCardLoadingIcon(urlCard);
  let uiSettled = false;
  const settleUI = (): void => {
    if (uiSettled) return;
    uiSettled = true;
    clearTimeoutIDAndHideLoadingIcon(loadingTimeoutID, urlCard);
    button.removeAttr("aria-disabled");
  };

  try {
    const mintPromise = new Promise<MintShortLinkResponse>(
      (resolve, reject) => {
        ajaxCall(
          "post",
          APP_CONFIG.routes.mintShortLink(utubID, utubUrlID),
          [],
          REQUEST_TIMEOUT_MS,
        )
          .done((response: MintShortLinkResponse) => resolve(response))
          .fail((xhr: JQuery.jqXHR) => reject(xhr));
      },
    );

    // Started synchronously in the click handler (see the doc comment).
    const clipboardItemWrite = startClipboardItemWrite({
      mintPromise,
      isStale,
    });

    let response: MintShortLinkResponse;
    try {
      response = await mintPromise;
    } catch (error) {
      // The ClipboardItem promise rejects with the mint; nothing to wait for.
      settleUI();
      handleMintFailure({
        xhr: error as JQuery.jqXHR,
        urlCard,
        bannerUnchanged:
          currentBannerToken({ mount: URL_DECK_BANNER_MOUNT }) === clickToken,
      });
      return;
    }
    // The mint is done, so a second click can no longer send a second request.
    // Don't keep the button disabled behind a clipboard permission prompt.
    settleUI();
    // The link exists now, whatever the user did meanwhile: only the banner and
    // the clipboard are skipped for a stale response, never the card's state.
    applyShortLinkState({
      utubID,
      utubUrlID,
      expiresAt: response.expiresAt,
      canRevoke: response.canRevoke,
    });

    let copied: boolean;
    if (clipboardItemWrite !== null) {
      copied = await clipboardItemWrite;
    } else if (isStale()) {
      // Never overwrite the clipboard on behalf of a stale response.
      return;
    } else {
      copied = await writeTextToClipboard(response.shortUrl);
    }

    if (isStale()) return;

    if (copied) {
      emit({
        event: UI_EVENTS.UI_SHORT_LINK_COPY,
        result: SHORT_LINK_COPY_RESULT.SUCCESS,
      });
      showCopiedBanner({ response, button, urlCard, utubID, utubUrlID });
      return;
    }

    log("copyShortLink — clipboard rejected, showing the manual-copy fallback");
    emit({
      event: UI_EVENTS.UI_SHORT_LINK_COPY,
      result: SHORT_LINK_COPY_RESULT.FALLBACK,
    });
    showURLOutcomeBanner({
      variant: "partial",
      message: APP_CONFIG.strings.SHORT_LINK_CLIPBOARD_FALLBACK,
      detail: response.shortUrl,
      returnFocusTo: button,
      autoHide: false,
      detailSelectable: true,
    });
  } catch (error) {
    // Never let a throw after the awaits escape as an unhandled rejection.
    log("copyShortLink — unexpected error", error);
  } finally {
    settleUI();
  }
}

/**
 * With `ClipboardItem`, starts the write now (inside the user gesture) with a
 * blob promise derived from the mint. Resolves true when the write succeeded,
 * false when the clipboard rejected or the response went stale, and never
 * rejects. Returns null when the browser lacks `ClipboardItem` or the write
 * could not even start (the caller then falls back to `writeText`).
 */
function startClipboardItemWrite({
  mintPromise,
  isStale,
}: {
  mintPromise: Promise<MintShortLinkResponse>;
  isStale: () => boolean;
}): Promise<boolean> | null {
  if (
    typeof ClipboardItem === "undefined" ||
    typeof navigator.clipboard?.write !== "function"
  ) {
    return null;
  }
  const blobPromise = mintPromise.then((response) => {
    // Rejecting abandons the browser's pending write, leaving the clipboard alone.
    if (isStale()) throw new Error("short link response is stale");
    return new Blob([response.shortUrl], { type: "text/plain" });
  });
  // The mint's own rejection is handled by the caller; keep this chain quiet.
  blobPromise.catch(() => undefined);
  try {
    return navigator.clipboard
      .write([new ClipboardItem({ "text/plain": blobPromise })])
      .then(
        () => true,
        () => false,
      );
  } catch {
    // A synchronous throw means no write started: let the caller try writeText.
    return null;
  }
}

async function writeTextToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

// A stale mint failure still reports its (real) error and drops a card the
// server says is gone; only the banner is left alone when a newer one replaced it.
function handleMintFailure({
  xhr,
  urlCard,
  bannerUnchanged,
}: {
  xhr: JQuery.jqXHR;
  urlCard: JQuery;
  bannerUnchanged: boolean;
}): void {
  emit({
    event: UI_EVENTS.UI_SHORT_LINK_COPY,
    result: SHORT_LINK_COPY_RESULT.FAILURE,
  });
  if (is429Handled(xhr)) return;
  if (isUtubLockedHandled(xhr)) return;

  const message = errorMessageOf({
    xhr,
    fallback: APP_CONFIG.strings.SHORT_LINK_COPY_FAILED,
  });
  if (xhr.status === 404) {
    // Route guard: the URL or UTub is trashed, or the caller left the UTub.
    // The card is going away: a leftover Revoke for it would be stale.
    if (bannerUnchanged) clearURLOutcomeBanner();
    showURLDeckBannerError(message);
    deleteURLOnStale(urlCard);
    return;
  }
  showURLDeckBannerError(APP_CONFIG.strings.SHORT_LINK_COPY_FAILED);
}

function showCopiedBanner({
  response,
  button,
  urlCard,
  utubID,
  utubUrlID,
}: {
  response: MintShortLinkResponse;
  button: JQuery;
  urlCard: JQuery;
  utubID: number;
  utubUrlID: number;
}): void {
  const message = fillTemplate({
    template: APP_CONFIG.strings.SHORT_LINK_COPIED,
    values: { date: formatShortLinkExpiry(response.expiresAt) },
  });
  showURLOutcomeBanner({
    variant: "success",
    message,
    detail: response.shortUrl,
    actionLabel: response.canRevoke
      ? APP_CONFIG.strings.SHORT_LINK_REVOKE_LABEL
      : undefined,
    actionAriaLabel: APP_CONFIG.strings.SHORT_LINK_REVOKE_ARIA,
    onAction: () =>
      confirmAndRevokeShortLink({
        utubID,
        utubUrlID,
        urlCard,
        expiresAt: response.expiresAt,
      }),
    returnFocusTo: button,
  });
  announceInDeck(message);
}

/**
 * Asks "Revoke short link?" in the shared confirm modal and, only on Confirm,
 * deletes the link. Shared by the copy banner's Revoke and the card's status row.
 *
 * Focus returns to the card's short-link button once the modal has closed
 * (`hidden.bs.modal`) for every outcome, or to the deck when the button is gone.
 * Cancel, Esc and close send no request and re-arm the banner's Revoke.
 */
export function confirmAndRevokeShortLink({
  utubID,
  utubUrlID,
  urlCard,
  expiresAt,
}: {
  utubID: number;
  utubUrlID: number;
  urlCard: JQuery;
  expiresAt: string;
}): void {
  const mount = URL_DECK_BANNER_MOUNT;
  let requestState: "idle" | "inFlight" | "done" = "idle";
  let modalOpen = true;
  // A guard-404 removes the card, so focus the deck instead of the fading button.
  let focusDeckInstead = false;
  // The banner (and so the deck context) that opened this modal. If it changed
  // meanwhile (a newer banner, a UTub switch), its Revoke is no longer ours to
  // re-arm and the outcome has no banner or error UI to show; focus still returns.
  const openedToken = currentBannerToken({ mount });
  const bannerChanged = (): boolean =>
    currentBannerToken({ mount }) !== openedToken;

  const returnFocus = (): void => {
    returnFocusIn({
      target: focusDeckInstead ? $() : shortLinkBtnOf(utubUrlID),
      mount,
    });
  };

  $(CONFIRM_MODAL_SELECTOR)
    .off(FOCUS_NAMESPACE)
    .on(FOCUS_NAMESPACE, () => {
      $(CONFIRM_MODAL_SELECTOR).off(FOCUS_NAMESPACE);
      modalOpen = false;
      if (requestState === "idle") {
        // Cancel, Esc or close: nothing was sent.
        if (!bannerChanged()) rearmBannerAction({ mount });
        returnFocus();
      } else if (requestState === "done") {
        returnFocus();
      }
      // "inFlight": the request's finish handler returns focus.
    });

  // Runs LAST in each outcome, after any banner/error UI (which can move focus),
  // so focus lands on the button (or the deck) whatever else happened.
  const finish = (): void => {
    requestState = "done";
    if (modalOpen) {
      hideConfirmModal();
    } else {
      returnFocus();
    }
  };

  const sendRevoke = (): void => {
    // The modal submit is disabled while in flight; this also blocks a re-entrant call.
    if (requestState !== "idle") return;
    requestState = "inFlight";
    $(SUBMIT_BTN_SELECTOR).prop("disabled", true);

    ajaxCall(
      "delete",
      APP_CONFIG.routes.revokeShortLink(utubID, utubUrlID),
      [],
      REQUEST_TIMEOUT_MS,
    )
      .done(() => {
        applyShortLinkState({
          utubID,
          utubUrlID,
          expiresAt: null,
          canRevoke: false,
        });
        if (!bannerChanged()) showRevokedBanner(utubUrlID);
        finish();
      })
      .fail((xhr: JQuery.jqXHR) => {
        const failure = classifyRevokeFailure(xhr);
        // Already revoked or expired elsewhere: the goal state is reached, so the
        // status row goes too, whatever banner is showing.
        if (failure === "alreadyRevoked") {
          applyShortLinkState({
            utubID,
            utubUrlID,
            expiresAt: null,
            canRevoke: false,
          });
        }
        // Decided before finish() so focus targets the deck, not the doomed button.
        if (failure === "guard404") focusDeckInstead = true;
        if (!bannerChanged()) {
          if (failure === "guard404") {
            clearURLOutcomeBanner(); // no stale Revoke for a removed card
          } else {
            rearmBannerAction({ mount });
          }
          showRevokeFailure({ xhr, failure, urlCard, utubUrlID });
        }
        finish();
      });
  };

  showConfirmModal({
    title: APP_CONFIG.strings.SHORT_LINK_REVOKE_CONFIRM_TITLE,
    body: fillTemplate({
      template: APP_CONFIG.strings.SHORT_LINK_REVOKE_CONFIRM_BODY,
      values: { date: formatShortLinkExpiry(expiresAt) },
    }),
    submitLabel: APP_CONFIG.strings.SHORT_LINK_REVOKE_LABEL,
    namespace: "shortLinkRevoke",
    onConfirm: sendRevoke,
  });
}

function cardOf(utubUrlID: number): JQuery {
  return $(`.urlRow[utuburlid=${utubUrlID}]`);
}

/**
 * Builds the card's "link active" row: the status line and, only when the viewer
 * may revoke (owner, co-owner, adder or minter), a Revoke button. Its own
 * in-flow row below `.urlOptions`; shown by CSS only while the card is selected.
 * Revoke is gated here at render time, never hidden by CSS.
 */
export function buildShortLinkStatusRow({
  urlCard,
  utubID,
  utubUrlID,
  expiresAt,
  canRevoke,
}: {
  urlCard: JQuery;
  utubID: number;
  utubUrlID: number;
  expiresAt: string;
  canRevoke: boolean;
}): JQuery {
  const row = $(document.createElement("div"))
    .addClass("shortLinkStatusRow")
    .attr({
      "data-expires-at": expiresAt,
      "data-can-revoke": String(canRevoke),
    });

  const status = $(document.createElement("span"))
    .addClass("shortLinkStatus")
    .append(
      createShortLinkIcon({ sizePx: 14 }),
      $(document.createElement("span"))
        .addClass("shortLinkStatusText")
        .text(
          fillTemplate({
            template: APP_CONFIG.strings.SHORT_LINK_EXPIRES,
            values: { date: formatShortLinkExpiry(expiresAt) },
          }),
        ),
    );
  row.append(status);

  if (canRevoke) {
    const revokeBtn = $(document.createElement("button"))
      .addClass("btn shortLinkRevoke tabbable")
      .attr({
        type: "button",
        "aria-label": APP_CONFIG.strings.SHORT_LINK_REVOKE_ARIA,
      })
      .text(APP_CONFIG.strings.SHORT_LINK_REVOKE_LABEL)
      .disableTab()
      .onExact("click", function () {
        // Read the expiry at click time: another member's refresh may have moved it.
        const current = getState().urls.find(
          (url: UtubUrlItem) => url.utubUrlID === utubUrlID,
        );
        confirmAndRevokeShortLink({
          utubID,
          utubUrlID,
          urlCard,
          expiresAt: current?.shortLinkExpiresAt ?? expiresAt,
        });
      });
    row.append(revokeBtn);
  }

  return row;
}

/**
 * Brings the card's status row, Revoke button and short-link tooltip in line
 * with the link state, in place (no deck reload). A no-op when the card already
 * shows exactly this state, so unrelated refreshes never rebuild the row (and
 * never drop keyboard focus on Revoke).
 */
export function renderShortLinkStatus({
  urlCard,
  utubID,
  utubUrlID,
  expiresAt,
  canRevoke,
}: {
  urlCard: JQuery;
  utubID: number;
  utubUrlID: number;
  expiresAt: string | null;
  canRevoke: boolean;
}): void {
  if (urlCard.length === 0) return;

  const currentRow = urlCard.find(SHORT_LINK_STATUS_ROW_SELECTOR);
  const upToDate =
    expiresAt === null
      ? currentRow.length === 0
      : currentRow.attr("data-expires-at") === expiresAt &&
        currentRow.attr("data-can-revoke") === String(canRevoke);
  if (upToDate) return;

  const focusWasInRow =
    currentRow.length > 0 &&
    currentRow[0].contains(document.activeElement as Node | null);
  removeShortLinkStatusRow(urlCard);
  setShortLinkBtnTooltip({ urlCard, expiresAt });
  // Rebuilding drops focus to body; keep it on the card's short-link button.
  if (focusWasInRow) urlCard.find(SHORT_LINK_BTN_SELECTOR).trigger("focus");
  if (expiresAt === null) return;

  const row = buildShortLinkStatusRow({
    urlCard,
    utubID,
    utubUrlID,
    expiresAt,
    canRevoke,
  });
  if (isShortLinkHiddenForEdit(urlCard)) {
    // An edit panel is open: stay hidden until it closes.
    row.addClass("hidden");
  } else if (urlCard.attr("urlSelected") === "true") {
    row.find(".shortLinkRevoke").enableTab();
  }
  urlCard.find(".urlOptions").after(row);
}

/**
 * Writes a URL's link state to the app store and updates its card in place.
 * Looks the card up fresh, so a response that outlives a deselect still lands.
 */
export function applyShortLinkState({
  utubID,
  utubUrlID,
  expiresAt,
  canRevoke,
}: {
  utubID: number;
  utubUrlID: number;
  expiresAt: string | null;
  canRevoke: boolean;
}): void {
  setState({
    urls: getState().urls.map((url: UtubUrlItem) =>
      url.utubUrlID === utubUrlID
        ? {
            ...url,
            shortLinkExpiresAt: expiresAt,
            canRevokeShortLink: canRevoke,
          }
        : url,
    ),
  });
  renderShortLinkStatus({
    urlCard: cardOf(utubUrlID),
    utubID,
    utubUrlID,
    expiresAt,
    canRevoke,
  });
}

function showRevokedBanner(utubUrlID: number): void {
  const message = APP_CONFIG.strings.SHORT_LINK_REVOKED;
  showURLOutcomeBanner({
    variant: "success",
    message,
    returnFocusTo: shortLinkBtnOf(utubUrlID),
  });
  announceInDeck(message);
}

type RevokeFailure = "handled" | "alreadyRevoked" | "guard404" | "failed";

// Pure classification (the shared 429 / locked handlers own their responses).
function classifyRevokeFailure(xhr: JQuery.jqXHR): RevokeFailure {
  if (is429Handled(xhr)) return "handled";
  if (isUtubLockedHandled(xhr)) return "handled";
  if (xhr.status !== 404) return "failed";
  const body = xhr.responseJSON as ShortLinkErrorBody | undefined;
  // Already revoked or expired elsewhere: the goal state is reached. Any other
  // 404 is the route guard: the URL or UTub is trashed, or the caller left.
  return body?.errorCode === SHORT_LINK_NOT_FOUND_ERROR_CODE
    ? "alreadyRevoked"
    : "guard404";
}

function showRevokeFailure({
  xhr,
  failure,
  urlCard,
  utubUrlID,
}: {
  xhr: JQuery.jqXHR;
  failure: RevokeFailure;
  urlCard: JQuery;
  utubUrlID: number;
}): void {
  switch (failure) {
    case "handled":
      return;
    case "alreadyRevoked":
      showRevokedBanner(utubUrlID);
      return;
    case "guard404":
      showURLDeckBannerError(
        errorMessageOf({
          xhr,
          fallback: APP_CONFIG.strings.SHORT_LINK_REVOKE_FAILED,
        }),
      );
      deleteURLOnStale(urlCard);
      return;
    case "failed":
      showURLDeckBannerError(APP_CONFIG.strings.SHORT_LINK_REVOKE_FAILED);
      return;
  }
}
