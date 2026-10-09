import type { Schema, SuccessResponse } from "../../types/api-helpers.d.ts";

import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { isUtubLockedHandled } from "../utub-locked.js";
import { showURLDeckBannerError } from "./deck.js";
import { deleteURLOnStale } from "./cards/get.js";
import { applyUpdatedURLString } from "./cards/apply-url-string.js";
import {
  flushParamTrim,
  type TrimSubmission,
  type UrlParamsTrimmedForm,
} from "./trim/param-trim-block.js";
import { fillTemplate } from "../../lib/string-template.js";
import { debug } from "../../lib/debug.js";
import { emit } from "../../lib/metrics-client.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import { URL_PARAMS_TRIMMED_ACTION } from "../../types/metrics-dim-values.js";

const log = debug("urls:outcome-banner");

const BANNER_SELECTOR = "#URLDeckOutcomeBanner";
const DECK_SELECTOR = "#URLDeck";
const REQUEST_TIMEOUT_MS = 35000;

type UpdateUrlStringResponse = SuccessResponse<"updateUrl">;
type UpdateUrlStringError = Schema<"ErrorResponse_URLErrorCodes">;

export type OutcomeBannerVariant = "success" | "partial";

/**
 * Moves focus to `target`, or to the URL deck itself (a `tabindex="-1"`
 * programmatic-focus root) when the target is absent or not rendered — the card
 * may be gone, filtered out, or deselected so its buttons are hidden.
 */
function returnFocus(target: JQuery): void {
  const destination =
    target.length > 0 && target.is(":visible") ? target : $(DECK_SELECTOR);
  destination.trigger("focus");
}

// How long the banner stays up before hiding itself. Long enough to read the
// message and reach Undo on a phone.
const AUTO_HIDE_MS = 10000;
const PAUSE_EVENTS =
  "mouseenter.outcomeBannerPause focusin.outcomeBannerPause touchstart.outcomeBannerPause";
const RESUME_EVENTS =
  "mouseleave.outcomeBannerPause focusout.outcomeBannerPause touchend.outcomeBannerPause touchcancel.outcomeBannerPause";

let autoHideTimer: ReturnType<typeof setTimeout> | null = null;

function stopAutoHide(): void {
  if (autoHideTimer !== null) {
    clearTimeout(autoHideTimer);
    autoHideTimer = null;
  }
}

// (Re)starts the full countdown; hides without moving focus (focus can only be
// inside the banner while the timer is paused, so nothing is lost).
function startAutoHide(): void {
  stopAutoHide();
  autoHideTimer = setTimeout(() => {
    autoHideTimer = null;
    clearURLOutcomeBanner();
  }, AUTO_HIDE_MS);
}

/** Hides and empties the banner. Safe to call when no banner is showing. */
export function clearURLOutcomeBanner(): void {
  stopAutoHide();
  $(BANNER_SELECTOR)
    .off(".outcomeBannerPause")
    .addClass("hidden")
    .removeClass("success partial")
    .empty();
}

/**
 * Shows the deck's transient outcome banner. It hides itself after
 * `AUTO_HIDE_MS`; the countdown pauses while the banner is hovered, focused or
 * touched and restarts in full when released. No focus is stolen on show; it can
 * also be cleared by the next user action or its dismiss button (which returns
 * focus to `returnFocusTo`).
 */
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
  detail?: string;
  actionLabel?: string;
  onAction?: () => void;
  returnFocusTo: JQuery;
}): void {
  const banner = $(BANNER_SELECTOR);
  if (banner.length === 0) {
    log("showURLOutcomeBanner — container missing, skipped");
    return;
  }

  const body = $("<div>", { class: "urlOutcomeBannerBody" }).append(
    $("<span>", { class: "urlOutcomeBannerMessage" }).text(message),
  );
  if (detail) {
    body.append($("<span>", { class: "urlOutcomeBannerDetail" }).text(detail));
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
      clearURLOutcomeBanner();
      returnFocus(returnFocusTo);
    }),
  );

  banner
    .off(".outcomeBannerPause")
    .empty()
    .removeClass("hidden success partial")
    .addClass(variant)
    .append(body, actions)
    .on(PAUSE_EVENTS, stopAutoHide)
    .on(RESUME_EVENTS, startAutoHide);
  startAutoHide();
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
      applyUpdatedURLString({ response, urlCard });
      // The edit form's input still holds the trimmed string it was saved with
      // (a kept-open mobile form shows it right now; a closed one would show it
      // on its next open). Restore it to the stored original and re-render the
      // trim block from it, so the field reads as it did before the trim.
      const restoredURLString = response.URL.urlString;
      urlCard.find(".urlStringUpdate").val(restoredURLString);
      flushParamTrim({
        trimWrap: urlCard.find(".urlParamTrimWrap"),
        rawValue: restoredURLString,
      });
      clearURLOutcomeBanner();
    }
    returnFocus(returnFocusTo);
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    if (is429Handled(xhr)) {
      // The banner stays up, so let the user retry the Undo.
      $(BANNER_SELECTOR)
        .find(".urlOutcomeBannerAction")
        .removeAttr("aria-disabled");
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
}: {
  trimSubmission: TrimSubmission;
  utubID: number;
  utubUrlID: number;
  urlCard: JQuery;
  form: UrlParamsTrimmedForm;
}): void {
  const returnFocusTo = $(`.urlRow[utuburlid=${utubUrlID}]`).find(
    ".urlStringBtnUpdate",
  );
  const message =
    trimSubmission.droppedCount === 1
      ? APP_CONFIG.strings.URL_TRIM_SAVED_BANNER_ONE
      : fillTemplate({
          template: APP_CONFIG.strings.URL_TRIM_SAVED_BANNER,
          values: { n: String(trimSubmission.droppedCount) },
        });

  showURLOutcomeBanner({
    variant: "success",
    message,
    detail: trimSubmission.droppedSegments.join(", "),
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
