import type { SuccessResponse } from "../../../types/api-helpers.d.ts";
import type { UtubTag } from "../../../types/url.js";

import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import {
  BULK_FOCUS_RETURN_SELECTOR,
  BULK_REQUEST_TIMEOUT_MS,
} from "../../../lib/constants.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { debug } from "../../../lib/debug.js";
import { emit } from "../../../lib/metrics-client.js";
import { fillTemplate } from "../../../lib/string-template.js";
import { getState } from "../../../store/app-store.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";
import { isUtubLockedHandled } from "../../utub-locked.js";
import { refreshTrashCount } from "../../trash/count.js";
import {
  URL_DECK_BANNER_MOUNT,
  buildLostTagNamesDetail,
  buildReviveMessage,
  clearURLOutcomeBanner,
  currentBannerToken,
  returnFocusIn,
  showURLOutcomeBanner,
} from "../outcome-banner.js";
import { insertURLCardIntoDeck } from "./card-deck.js";
import { applyRowCountDelta } from "../../utubs/row-counts.js";

const log = debug("urls:cards");

type RestoreUrlsResponse = SuccessResponse<"restoreUrls">;

type RestoreSkipReason = RestoreUrlsResponse["skipped"][number]["reason"];
const SKIP_REASON_DESTINATION_REQUIRED: RestoreSkipReason =
  "destination_required";

type DeleteToastArgs = {
  utubID: number;
  deletedIDs: number[];
  skippedCount: number;
  hiddenCount: number;
  returnFocusTo: JQuery;
};

let _undoInFlight = false;
let _deleteToastToken: number | null = null;

/** True between an Undo click and its request settling. */
export function isURLDeleteUndoInFlight(): boolean {
  return _undoInFlight;
}

/** True while the delete toast this module last showed is still the mount's banner. */
export function isURLDeleteToastShowing(): boolean {
  return (
    _deleteToastToken !== null &&
    currentBannerToken({ mount: URL_DECK_BANNER_MOUNT }) === _deleteToastToken
  );
}

function pluralText({
  count,
  one,
  many,
}: {
  count: number;
  one: string;
  many: string;
}): string {
  return count === 1
    ? one
    : fillTemplate({ template: many, values: { n: String(count) } });
}

/**
 * Shows "Moved N URLs to Trash." with Undo. Partial when some selected URLs were
 * skipped (the detail names them), with a second detail line for URLs hidden by
 * the active filters.
 */
export function showURLDeletedToast({
  utubID,
  deletedIDs,
  skippedCount,
  hiddenCount,
  returnFocusTo,
}: DeleteToastArgs): void {
  const detail: string[] = [];
  if (skippedCount > 0) {
    detail.push(
      pluralText({
        count: skippedCount,
        one: APP_CONFIG.strings.URL_BULK_DELETE_SKIPPED_SUFFIX_ONE,
        many: APP_CONFIG.strings.URL_BULK_DELETE_SKIPPED_SUFFIX,
      }),
    );
  }
  if (hiddenCount > 0) {
    detail.push(
      pluralText({
        count: hiddenCount,
        one: APP_CONFIG.strings.URL_DELETE_HIDDEN_DETAIL_ONE,
        many: APP_CONFIG.strings.URL_DELETE_HIDDEN_DETAIL,
      }),
    );
  }

  showURLOutcomeBanner({
    variant: skippedCount > 0 ? "partial" : "success",
    message: pluralText({
      count: deletedIDs.length,
      one: APP_CONFIG.strings.URL_MOVED_TO_TRASH_ONE,
      many: APP_CONFIG.strings.URL_MOVED_TO_TRASH,
    }),
    detail,
    actionLabel: APP_CONFIG.strings.URL_TRIM_UNDO,
    actionAriaLabel: pluralText({
      count: deletedIDs.length,
      one: APP_CONFIG.strings.URL_UNDO_DELETE_ARIA_ONE,
      many: APP_CONFIG.strings.URL_UNDO_DELETE_ARIA,
    }),
    onAction: () =>
      performDeleteUndo({
        utubID,
        deletedIDs,
        skippedCount,
        hiddenCount,
        returnFocusTo,
      }),
    returnFocusTo,
  });
  _deleteToastToken = currentBannerToken({ mount: URL_DECK_BANNER_MOUNT });
}

/**
 * Shows the no-Undo toast for a bulk delete that removed nothing: a 400
 * (`forceFail`) or every selected URL skipped as non-deletable. Assertive.
 */
export function showURLDeletionFailedToast({
  forceFail,
}: {
  forceFail: boolean;
}): void {
  log("showURLDeletionFailedToast", { forceFail });
  showURLOutcomeBanner({
    variant: "partial",
    message: forceFail
      ? APP_CONFIG.strings.UNABLE_TO_DELETE_URLS
      : APP_CONFIG.strings.URL_BULK_DELETE_NONE,
    returnFocusTo: $(BULK_FOCUS_RETURN_SELECTOR),
    ariaLive: "assertive",
  });
}

function lostTagsSentence({ lostTagCount }: { lostTagCount: number }): string {
  return pluralText({
    count: lostTagCount,
    one: APP_CONFIG.strings.URL_UNDO_LOST_TAGS_ONE,
    many: APP_CONFIG.strings.URL_UNDO_LOST_TAGS,
  });
}

/**
 * Builds the completion banner for an Undo from the restore response. A
 * `destination_required` skip is reported distinctly from `not_in_trash`: that
 * URL is still in Trash and needs a destination picked there.
 */
function buildUndoOutcome({
  response,
  totalRequested,
}: {
  response: RestoreUrlsResponse;
  totalRequested: number;
}): {
  variant: "success" | "partial";
  message: string;
  detail: string[];
  ariaLive: "polite" | "assertive";
} {
  const { totalRestored, lostTagCount } = response;
  const destinationRequiredCount = response.skipped.filter(
    (skip) => skip.reason === SKIP_REASON_DESTINATION_REQUIRED,
  ).length;
  const notInTrashCount = response.skipped.length - destinationRequiredCount;

  const detail: string[] = [];
  const lostNames = buildLostTagNamesDetail({
    lostTagNames: response.lostTagNames ?? [],
  });
  if (totalRestored > 0 && lostTagCount > 0 && lostNames !== undefined) {
    detail.push(lostNames);
  }
  if (notInTrashCount > 0 && totalRestored > 0) {
    detail.push(
      pluralText({
        count: notInTrashCount,
        one: APP_CONFIG.strings.URL_UNDO_NOT_IN_TRASH_ONE,
        many: APP_CONFIG.strings.URL_UNDO_NOT_IN_TRASH,
      }),
    );
  }
  if (destinationRequiredCount > 0 && totalRestored > 0) {
    detail.push(
      pluralText({
        count: destinationRequiredCount,
        one: APP_CONFIG.strings.URL_UNDO_DESTINATION_REQUIRED_ONE,
        many: APP_CONFIG.strings.URL_UNDO_DESTINATION_REQUIRED,
      }),
    );
  }

  const ariaLive =
    totalRestored === 0 || response.skipped.length > 0 ? "assertive" : "polite";

  if (totalRestored === 0) {
    if (destinationRequiredCount === 0) {
      return {
        variant: "partial",
        message: APP_CONFIG.strings.TRASH_NOT_IN_TRASH,
        detail,
        ariaLive,
      };
    }
    if (notInTrashCount > 0) {
      detail.push(
        pluralText({
          count: notInTrashCount,
          one: APP_CONFIG.strings.URL_UNDO_NOT_IN_TRASH_ONE,
          many: APP_CONFIG.strings.URL_UNDO_NOT_IN_TRASH,
        }),
      );
    }
    return {
      variant: "partial",
      message: pluralText({
        count: destinationRequiredCount,
        one: APP_CONFIG.strings.URL_UNDO_DESTINATION_REQUIRED_ONE,
        many: APP_CONFIG.strings.URL_UNDO_DESTINATION_REQUIRED,
      }),
      detail,
      ariaLive,
    };
  }

  let message: string;
  if (response.skipped.length > 0) {
    message = fillTemplate({
      template: APP_CONFIG.strings.URL_UNDO_RESTORED_SOME,
      values: {
        restored: String(totalRestored),
        total: String(totalRequested),
      },
    });
    if (lostTagCount > 0) message += ` ${lostTagsSentence({ lostTagCount })}`;
  } else if (totalRequested === 1) {
    message = buildReviveMessage({ lostTagCount });
  } else {
    message = fillTemplate({
      template: APP_CONFIG.strings.URL_UNDO_RESTORED,
      values: { n: String(totalRestored) },
    });
    if (lostTagCount > 0) message += ` ${lostTagsSentence({ lostTagCount })}`;
  }

  return {
    variant:
      response.skipped.length > 0 || lostTagCount > 0 ? "partial" : "success",
    message,
    detail,
    ariaLive,
  };
}

/**
 * One request restores everything the toast moved to Trash. The completion banner
 * is written only if the mount's banner is still the one that was showing when
 * Undo was clicked; the cards are always re-inserted (never selected, since a
 * selection clears banners and would invalidate this very token).
 */
function performDeleteUndo(args: DeleteToastArgs): void {
  const { utubID, deletedIDs, returnFocusTo } = args;
  _undoInFlight = true;
  const token = currentBannerToken({ mount: URL_DECK_BANNER_MOUNT });
  const bannerStillMine = (): boolean =>
    currentBannerToken({ mount: URL_DECK_BANNER_MOUNT }) === token;

  emit({ event: UI_EVENTS.UI_URL_DELETE_UNDONE });

  const request = ajaxCall(
    "post",
    APP_CONFIG.routes.restoreURLs(utubID),
    { utubUrlIds: deletedIDs },
    BULK_REQUEST_TIMEOUT_MS,
  );

  request.done(function (response: RestoreUrlsResponse) {
    void refreshTrashCount();
    if (getState().activeUTubID !== utubID) {
      // The active path counts each card through insertURLCardIntoDeck; here the
      // user switched UTubs, so reverse the row's earlier delete delta directly.
      applyRowCountDelta({
        utubID,
        urlDelta: response.restored.length,
        memberDelta: 0,
      });
      return;
    }

    let lastInsertedCard: JQuery = $();
    for (const restoredUrl of response.restored) {
      const urlTagIDs = new Set(restoredUrl.utubUrlTagIDs);
      const appliedTags: UtubTag[] = (response.appliedTags ?? []).filter(
        (tag) => urlTagIDs.has(tag.id),
      );
      lastInsertedCard = insertURLCardIntoDeck({
        newUrl: restoredUrl,
        utubID,
        appliedTags,
        announce: false,
        select: false,
      });
    }

    if (!bannerStillMine()) {
      log("performDeleteUndo — a newer banner is showing, completion skipped");
      return;
    }

    const outcome = buildUndoOutcome({
      response,
      totalRequested: deletedIDs.length,
    });
    const focusTarget =
      lastInsertedCard.length > 0 ? lastInsertedCard : $("#URLDeck");
    showURLOutcomeBanner({
      variant: outcome.variant,
      message: outcome.message,
      detail: outcome.detail,
      returnFocusTo: focusTarget,
      ariaLive: outcome.ariaLive,
    });
    returnFocusIn({ target: focusTarget, mount: URL_DECK_BANNER_MOUNT });
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    // The bannerStillMine() guards below extend the "never overwrite a newer
    // action's banner" rule to the 429 and locked branches.
    if (is429Handled(xhr)) {
      // Re-render a fresh, enabled Undo (the rebuild destroyed the old button).
      if (bannerStillMine()) {
        showURLDeletedToast(args);
        $(URL_DECK_BANNER_MOUNT.bannerSelector)
          .find(".urlOutcomeBannerAction")
          .trigger("focus");
      }
      return;
    }

    if (isUtubLockedHandled(xhr)) {
      if (bannerStillMine()) {
        clearURLOutcomeBanner();
        returnFocusIn({ target: returnFocusTo, mount: URL_DECK_BANNER_MOUNT });
      }
      return;
    }

    if (
      xhr.status === 403 &&
      xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      // Invalid CSRF token error response.
      $("body").html(xhr.responseText);
      return;
    }

    window.location.assign(APP_CONFIG.routes.errorPage);
  });

  request.always(function () {
    _undoInFlight = false;
  });
}
