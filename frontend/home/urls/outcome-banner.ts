import type { Schema, SuccessResponse } from "../../types/api-helpers.d.ts";

import { $, getInputValue } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { isUtubLockedHandled } from "../utub-locked.js";
import { showURLDeckBannerError } from "./deck.js";
import { deleteURLOnStale } from "./cards/get.js";
import { applyUpdatedURLString } from "./cards/apply-url-string.js";
import { syncEditPanelDirtyState } from "./cards/edit-panel-dirty.js";
import {
  type TrimSubmission,
  type UrlParamsTrimmedForm,
} from "./trim/param-trim-block.js";
import { composeURL } from "./scheme/scheme-utils.js";
import {
  currentUpdateScheme,
  resyncUpdateInputAfterUndo,
} from "./scheme/update-input-scheme.js";
import { fillTemplate } from "../../lib/string-template.js";
import { debug } from "../../lib/debug.js";
import { emit } from "../../lib/metrics-client.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import { URL_PARAMS_TRIMMED_ACTION } from "../../types/metrics-dim-values.js";

const log = debug("urls:outcome-banner");

/**
 * Where an outcome banner lives: the banner element and the `tabindex="-1"`
 * root that receives focus when a dismissed banner's focus target is gone.
 */
export type OutcomeBannerMount = {
  bannerSelector: string;
  rootSelector: string;
};

export const URL_DECK_BANNER_MOUNT: OutcomeBannerMount = {
  bannerSelector: "#URLDeckOutcomeBanner",
  rootSelector: "#URLDeck",
};

const BANNER_SELECTOR = URL_DECK_BANNER_MOUNT.bannerSelector;
const DECK_SELECTOR = URL_DECK_BANNER_MOUNT.rootSelector;
const REQUEST_TIMEOUT_MS = 35000;

type UpdateUrlStringResponse = SuccessResponse<"updateUrl">;
type UpdateUrlStringError = Schema<"ErrorResponse_URLErrorCodes">;

export type OutcomeBannerVariant = "success" | "partial";

/**
 * Moves focus to `target`, or to the URL deck itself (a `tabindex="-1"`
 * programmatic-focus root) when the target is absent or not rendered — the card
 * may be gone, filtered out, or deselected so its buttons are hidden.
 */
function returnFocusIn({
  target,
  mount,
}: {
  target: JQuery;
  mount: OutcomeBannerMount;
}): void {
  const destination =
    target.length > 0 && target.is(":visible") ? target : $(mount.rootSelector);
  destination.trigger("focus");
}

function returnFocus(target: JQuery): void {
  returnFocusIn({ target, mount: URL_DECK_BANNER_MOUNT });
}

// How long the banner stays up before hiding itself. Long enough to read the
// message and reach Undo on a phone; partial (error / no-change) banners get
// longer since they are messages the user may need to read.
const AUTO_HIDE_MS = 10000;
const AUTO_HIDE_PARTIAL_MS = 20000;
const PAUSE_EVENTS =
  "pointerenter.outcomeBannerPause pointerdown.outcomeBannerPause focusin.outcomeBannerPause";
const RESUME_EVENTS =
  "pointerleave.outcomeBannerPause pointerup.outcomeBannerPause pointercancel.outcomeBannerPause focusout.outcomeBannerPause";
// Window after a touch pointer event in which mouse-type pointer events are
// compatibility events from that touch (they would re-pause with no leave).
const TOUCH_COMPAT_MOUSE_MS = 1000;

type MountTimers = {
  autoHideTimer: ReturnType<typeof setTimeout> | null;
  lastTouchAt: number;
};

// Per-mount timer state, keyed by `bannerSelector`, so banners never share a countdown.
const timersByBanner = new Map<string, MountTimers>();

function timersFor(mount: OutcomeBannerMount): MountTimers {
  let timers = timersByBanner.get(mount.bannerSelector);
  if (timers === undefined) {
    timers = { autoHideTimer: null, lastTouchAt: Number.NEGATIVE_INFINITY };
    timersByBanner.set(mount.bannerSelector, timers);
  }
  return timers;
}

function stopAutoHide(mount: OutcomeBannerMount): void {
  const timers = timersByBanner.get(mount.bannerSelector);
  if (timers === undefined) return;
  if (timers.autoHideTimer !== null) {
    clearTimeout(timers.autoHideTimer);
    timers.autoHideTimer = null;
  }
}

function bannerVariant(): OutcomeBannerVariant {
  return $(BANNER_SELECTOR).hasClass("partial") ? "partial" : "success";
}

// (Re)starts the full countdown; hides without moving focus (focus can only be
// inside the banner while the timer is paused, so nothing is lost). If an Undo
// request is still in flight when it fires, the hide is deferred: the request's
// 429 branch restarts the countdown, and every other outcome replaces or clears
// the banner itself.
function startAutoHide({
  mount,
  variant,
}: {
  mount: OutcomeBannerMount;
  variant: OutcomeBannerVariant;
}): void {
  stopAutoHide(mount);
  const timers = timersFor(mount);
  timers.autoHideTimer = setTimeout(
    () => {
      timers.autoHideTimer = null;
      const inFlight =
        $(mount.bannerSelector)
          .find(".urlOutcomeBannerAction")
          .attr("aria-disabled") === "true";
      if (inFlight) return;
      clearOutcomeBanner({ mount });
    },
    variant === "partial" ? AUTO_HIDE_PARTIAL_MS : AUTO_HIDE_MS,
  );
}

// True for a mouse-type pointer event that follows a touch (compat event).
function isCompatMouseEvent({
  event,
  mount,
}: {
  event: JQuery.TriggeredEvent;
  mount: OutcomeBannerMount;
}): boolean {
  const timers = timersFor(mount);
  const pointerType = (event.originalEvent as PointerEvent | undefined)
    ?.pointerType;
  if (pointerType === "touch") {
    timers.lastTouchAt = Date.now();
    return false;
  }
  return (
    pointerType === "mouse" &&
    Date.now() - timers.lastTouchAt < TOUCH_COMPAT_MOUSE_MS
  );
}

/** Hides and empties the mount's banner. Safe to call when none is showing. */
export function clearOutcomeBanner({
  mount,
}: {
  mount: OutcomeBannerMount;
}): void {
  stopAutoHide(mount);
  const banner = $(mount.bannerSelector);
  if (banner.length === 0) {
    log("clearOutcomeBanner — container missing, skipped");
    timersByBanner.delete(mount.bannerSelector);
    return;
  }
  banner
    .off(".outcomeBannerPause")
    .addClass("hidden")
    .removeClass("success partial")
    .empty();
}

/** Hides and empties the URL deck's banner. Safe to call when none is showing. */
export function clearURLOutcomeBanner(): void {
  clearOutcomeBanner({ mount: URL_DECK_BANNER_MOUNT });
}

/** Shows the URL deck's transient outcome banner (see `showOutcomeBanner`). */
export function showURLOutcomeBanner({
  variant,
  message,
  detail,
  actionLabel,
  onAction,
  returnFocusTo,
}: {
  variant: OutcomeBannerVariant;
  message: string;
  detail?: string | readonly string[];
  actionLabel?: string;
  onAction?: () => void;
  returnFocusTo: JQuery;
}): void {
  showOutcomeBanner({
    mount: URL_DECK_BANNER_MOUNT,
    variant,
    message,
    detail,
    actionLabel,
    onAction,
    returnFocusTo,
  });
}

/**
 * Shows a transient outcome banner in `mount`. It hides itself after
 * `AUTO_HIDE_MS`; the countdown pauses while the banner is hovered, focused or
 * touched and restarts in full when released. No focus is stolen on show; it can
 * also be cleared by the next user action or its dismiss button (which returns
 * focus to `returnFocusTo`, else the mount's root).
 */
export function showOutcomeBanner({
  mount,
  variant,
  message,
  detail,
  actionLabel,
  onAction,
  returnFocusTo,
}: {
  mount: OutcomeBannerMount;
  variant: OutcomeBannerVariant;
  message: string;
  detail?: string | readonly string[];
  actionLabel?: string;
  onAction?: () => void;
  returnFocusTo: JQuery;
}): void {
  const banner = $(mount.bannerSelector);
  if (banner.length === 0) {
    log("showOutcomeBanner — container missing, skipped");
    return;
  }

  const body = $("<div>", { class: "urlOutcomeBannerBody" }).append(
    $("<span>", { class: "urlOutcomeBannerMessage" }).text(message),
  );
  // Each detail line gets its own span, so a revive banner can carry the lost tags
  // and the dropped parameters on separate lines.
  const detailLines = typeof detail === "string" ? [detail] : (detail ?? []);
  for (const detailLine of detailLines) {
    if (detailLine) {
      body.append(
        $("<span>", { class: "urlOutcomeBannerDetail" }).text(detailLine),
      );
    }
  }

  const actions = $("<div>", { class: "urlOutcomeBannerActions" });
  if (actionLabel && onAction) {
    actions.append(
      $("<button>", {
        type: "button",
        class: "urlOutcomeBannerAction",
      })
        .text(actionLabel)
        .on("click", function () {
          // One in-flight action at a time (aria-disabled keeps focus).
          if ($(this).attr("aria-disabled") === "true") return;
          $(this).attr("aria-disabled", "true");
          onAction();
        }),
    );
  }
  actions.append(
    $("<button>", {
      type: "button",
      class: "urlOutcomeBannerDismiss",
      "aria-label": APP_CONFIG.strings.URL_TRIM_DISMISS_ARIA,
    }).on("click", () => {
      clearOutcomeBanner({ mount });
      returnFocusIn({ target: returnFocusTo, mount });
    }),
  );

  banner
    .off(".outcomeBannerPause")
    .empty()
    .removeClass("hidden success partial")
    .addClass(variant)
    .append(body, actions)
    .on(PAUSE_EVENTS, (event) => {
      if (!isCompatMouseEvent({ event, mount })) stopAutoHide(mount);
    })
    .on(RESUME_EVENTS, (event) => {
      if (!isCompatMouseEvent({ event, mount })) {
        startAutoHide({ mount, variant });
      }
    });
  // A banner replaced under a still-hovering pointer stays paused until the
  // pointer leaves (its pointerleave restarts the countdown).
  if (!banner.is(":hover")) startAutoHide({ mount, variant });
}

/**
 * Restores the pre-trim URL string with a PATCH and reports the outcome.
 * Every branch ends by returning focus (see `returnFocus`).
 */
export function performUndo({
  utubID,
  utubUrlID,
  urlCard,
  originalUrlString,
  returnFocusTo,
}: {
  utubID: number;
  utubUrlID: number;
  urlCard: JQuery;
  originalUrlString: string;
  returnFocusTo: JQuery;
}): void {
  const request = ajaxCall(
    "patch",
    APP_CONFIG.routes.updateURL(utubID, utubUrlID),
    { urlString: originalUrlString },
    REQUEST_TIMEOUT_MS,
  );

  request.done(function (response: UpdateUrlStringResponse) {
    if (response.status === "No change") {
      // HTTP 200 but nothing changed: the server's tracking-param strip means
      // restoring the original yields the string already stored.
      showURLOutcomeBanner({
        variant: "partial",
        message: APP_CONFIG.strings.URL_TRIM_UNDO_NOOP,
        returnFocusTo,
      });
    } else {
      const savedURLString = urlCard.find(".urlString").attr("href");
      applyUpdatedURLString({ response, urlCard });
      // The edit form's input still holds the string it was saved with (a
      // kept-open mobile form shows it right now, split across its scheme
      // selector; a closed one on its next open). Restore it and re-render the
      // trim block, so the field reads as it did before the save — unless the
      // user has since typed something else.
      const input = urlCard.find(".urlStringUpdate");
      const formClosed = urlCard
        .find(".updateUrlStringWrap")
        .hasClass("hidden");
      const composedInput = composeURL({
        scheme: currentUpdateScheme({ urlCard }),
        text: input.length > 0 ? getInputValue(input) : "",
      });
      if (formClosed || composedInput === savedURLString) {
        resyncUpdateInputAfterUndo({
          urlCard,
          restoredURLString: response.URL.urlString,
        });
      }
      // The stored value changed (and the input may have been resynced): re-derive
      // the open mobile panel's confirm buttons. No-op when the panel isn't open.
      syncEditPanelDirtyState(urlCard);
      clearURLOutcomeBanner();
    }
    returnFocus(returnFocusTo);
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    if (is429Handled(xhr)) {
      // The banner stays up, so let the user retry the Undo.
      const banner = $(BANNER_SELECTOR);
      banner.find(".urlOutcomeBannerAction").removeAttr("aria-disabled");
      // The countdown may have fired (and been deferred) while in flight.
      if (
        timersFor(URL_DECK_BANNER_MOUNT).autoHideTimer === null &&
        !banner.is(":hover")
      ) {
        startAutoHide({
          mount: URL_DECK_BANNER_MOUNT,
          variant: bannerVariant(),
        });
      }
      returnFocus(returnFocusTo);
      return;
    }

    const responseJSON = xhr.responseJSON as UpdateUrlStringError | undefined;
    const message = responseJSON?.message ?? "";

    if (xhr.status === 409) {
      showURLOutcomeBanner({
        variant: "partial",
        message: APP_CONFIG.strings.URL_TRIM_UNDO_CONFLICT,
        returnFocusTo,
      });
      returnFocus(returnFocusTo);
      return;
    }

    clearURLOutcomeBanner();

    if (xhr.status === 404) {
      // The card is being removed, so focus the deck rather than its buttons.
      showURLDeckBannerError(message);
      deleteURLOnStale(urlCard);
      $(DECK_SELECTOR).trigger("focus");
      return;
    }

    if (!isUtubLockedHandled(xhr)) {
      // 400 (original exceeds the length limit) and any other failure.
      showURLDeckBannerError(message);
    }
    returnFocus(returnFocusTo);
  });
}

/**
 * Shows the "URL updated." banner with Undo after a plain URL-string edit (no
 * parameters dropped). Undo re-saves `previousUrlString`, the string the card
 * showed before the save. Same focus handling as the trim banner.
 */
export function showURLUpdatedBanner({
  utubID,
  utubUrlID,
  urlCard,
  previousUrlString,
}: {
  utubID: number;
  utubUrlID: number;
  urlCard: JQuery;
  previousUrlString: string;
}): void {
  const returnFocusTo = $(`.urlRow[utuburlid=${utubUrlID}]`).find(
    ".urlStringBtnUpdate",
  );

  showURLOutcomeBanner({
    variant: "success",
    message: APP_CONFIG.strings.URL_UPDATED_BANNER,
    actionLabel: APP_CONFIG.strings.URL_TRIM_UNDO,
    onAction: () => {
      emit({ event: UI_EVENTS.UI_URL_EDIT_UNDONE });
      performUndo({
        utubID,
        utubUrlID,
        urlCard,
        originalUrlString: previousUrlString,
        returnFocusTo,
      });
    },
    returnFocusTo,
  });
}

/** Message for an add that revived a trashed URL; `lostTagCount` tags no longer exist. */
export function buildReviveMessage({
  lostTagCount,
}: {
  lostTagCount: number;
}): string {
  if (lostTagCount === 0) {
    return APP_CONFIG.strings.URL_REVIVED_FROM_TRASH;
  }
  if (lostTagCount === 1) {
    return APP_CONFIG.strings.URL_REVIVED_LOST_TAGS_ONE;
  }
  return fillTemplate({
    template: APP_CONFIG.strings.URL_REVIVED_LOST_TAGS,
    values: { n: String(lostTagCount) },
  });
}

/**
 * The second banner line naming the tags that no longer exist ("Tool, Art"), or
 * `undefined` when none are known. A URL trashed before tag names were saved has a
 * lost-tag count but no names; its banner shows only the count sentence.
 */
export function buildLostTagNamesDetail({
  lostTagNames,
}: {
  lostTagNames: readonly string[];
}): string | undefined {
  return lostTagNames.length > 0 ? lostTagNames.join(", ") : undefined;
}

/**
 * Shows the "Restored from trash." banner after an add revived a trashed URL.
 * Partial (yellow) when some of its tags no longer exist, with a second line
 * naming them when known. No Undo: reviving is not reversible from the deck.
 * Used when the add also dropped no parameters; otherwise `showTrimSavedBanner`
 * carries the revive sentence.
 */
export function showReviveBanner({
  lostTagCount,
  lostTagNames,
  utubUrlID,
}: {
  lostTagCount: number;
  lostTagNames: readonly string[];
  utubUrlID: number;
}): void {
  showURLOutcomeBanner({
    variant: lostTagCount > 0 ? "partial" : "success",
    message: buildReviveMessage({ lostTagCount }),
    detail: buildLostTagNamesDetail({ lostTagNames }),
    returnFocusTo: $(`.urlRow[utuburlid=${utubUrlID}]`).find(
      ".urlStringBtnUpdate",
    ),
  });
}

/**
 * Shows the "Saved without N parameters" banner with Undo after a trim-and-save.
 * The focus destination is the just-saved card's edit button, looked up fresh
 * here; `returnFocus` falls back to the deck if it is not rendered later.
 */
export function showTrimSavedBanner({
  trimSubmission,
  utubID,
  utubUrlID,
  urlCard,
  form,
  revive,
}: {
  trimSubmission: TrimSubmission;
  utubID: number;
  utubUrlID: number;
  urlCard: JQuery;
  form: UrlParamsTrimmedForm;
  revive?: { lostTagCount: number; lostTagNames: readonly string[] };
}): void {
  const returnFocusTo = $(`.urlRow[utuburlid=${utubUrlID}]`).find(
    ".urlStringBtnUpdate",
  );
  const trimMessage =
    trimSubmission.droppedCount === 1
      ? APP_CONFIG.strings.URL_TRIM_SAVED_BANNER_ONE
      : fillTemplate({
          template: APP_CONFIG.strings.URL_TRIM_SAVED_BANNER,
          values: { n: String(trimSubmission.droppedCount) },
        });
  // An add that both revived a trashed URL and trimmed params gets one banner:
  // the revive sentence leads, and lost tags make it a partial outcome.
  const message =
    revive === undefined
      ? trimMessage
      : `${buildReviveMessage(revive)} ${trimMessage}`;
  const variant: OutcomeBannerVariant =
    revive !== undefined && revive.lostTagCount > 0 ? "partial" : "success";
  // Detail lines follow the message's sentence order: the lost tags (revive) first,
  // then the dropped parameters (trim), each on its own line.
  const lostTagNamesDetail =
    revive === undefined
      ? undefined
      : buildLostTagNamesDetail({ lostTagNames: revive.lostTagNames });
  const detail = [
    lostTagNamesDetail,
    trimSubmission.droppedSegments.join(", "),
  ].filter((line): line is string => Boolean(line));

  showURLOutcomeBanner({
    variant,
    message,
    detail,
    actionLabel: APP_CONFIG.strings.URL_TRIM_UNDO,
    onAction: () => {
      emit({
        event: UI_EVENTS.UI_URL_PARAMS_TRIMMED,
        form,
        action: URL_PARAMS_TRIMMED_ACTION.UNDO,
      });
      performUndo({
        utubID,
        utubUrlID,
        urlCard,
        originalUrlString: trimSubmission.originalUrlString,
        returnFocusTo,
      });
    },
    returnFocusTo,
  });
}
