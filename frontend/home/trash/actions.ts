/**
 * Row actions (Restore, Delete forever) and Empty trash for the Trash panel.
 *
 * Every flow ends the same way: announce the outcome in `#TrashOutcomeBanner`,
 * keep the list and tab counts in step, move focus to a sensible row, and let
 * `refreshTrashCount()` (or the deck-rebuild response) set the badge. Nothing
 * here increments or decrements the badge by hand.
 */

import type { SuccessResponse } from "../../types/api-helpers.d.ts";
import type { TrashedUrlItem, TrashedUtubItem } from "../../types/trash.js";

import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { debug } from "../../lib/debug.js";
import { fillTemplate } from "../../lib/string-template.js";
import { setState } from "../../store/app-store.js";
import { applyRowCountDelta } from "../utubs/row-counts.js";
import { hideConfirmModal, showConfirmModal } from "../confirm-modal.js";
import { buildUTubDeck } from "../utubs/deck.js";
import { getAllUTubs } from "../utubs/utils.js";
import {
  getPrefsVersion,
  reseedListPreferences,
  syncDeckOrderToStoreSort,
} from "../utubs/list-preferences.js";
import {
  buildLostTagNamesDetail,
  buildReviveMessage,
  showOutcomeBanner,
} from "../urls/outcome-banner.js";
import type { OutcomeBannerVariant } from "../urls/outcome-banner.js";
import { TRASH_BANNER_MOUNT } from "./banner.js";
import {
  beginCountRequest,
  refreshTrashCount,
  renderTrashCount,
} from "./count.js";
import {
  closeDestinationPicker,
  initDestinationPicker,
  openDestinationPicker,
  refocusDestinationPicker,
} from "./destination-picker.js";
import {
  URL_ALREADY_IN_DESTINATION,
  URL_DESTINATION_REQUIRED,
  URL_INVALID_DESTINATION,
  isNotInTrash,
} from "./error-codes.js";
import type { TrashDomain } from "./error-codes.js";
import { loadTrashList } from "./list.js";
import { isTrashOpen } from "./panel.js";
import {
  TRASH_SCOPE_IDS,
  getTrashListState,
  removeTrashRow,
} from "./render.js";
import { consumeTrashClickSuppression } from "./swipe-click-guard.js";
import { getActiveTrashScope } from "./tabs.js";
import type { TrashScope } from "./tabs.js";

const log = debug("trash:actions");

const CONFIRM_MODAL = "#confirmModal";
const MODAL_SUBMIT = "#modalSubmit";
const EMPTY_TRASH_BUTTON = "#TrashBtnEmpty";
const ROW_BUTTONS = ".trashBtnRestore, .trashBtnPurge";
const EMPTY_TRASH_TIMEOUT_MS = 10_000;
const TRASH_PANEL = "#TrashPanel";
// Hides the `.trashRow:focus` ring on the row focused after a swipe-restore.
const SWIPE_FOCUS_RETURN_CLASS = "swipe-focus-return";
const SWIPE_FOCUS_RETURN_BLUR = "blur.trashSwipeFocusReturn";
const SWIPE_FOCUS_RETURN_POINTERDOWN = "pointerdown.trashSwipeFocusReturn";

type UrlRestoredResponse = SuccessResponse<"restoreUrl">;
type UrlPurgedResponse = SuccessResponse<"purgeUrl">;
type UtubRestoredResponse = SuccessResponse<"restoreUtub">;
type UtubPurgedResponse = SuccessResponse<"purgeUtub">;
type TrashEmptiedResponse = SuccessResponse<"emptyTrash">;

type CsrfAwareBody = { message?: string };

/**
 * A response can land after the user left Trash, by which time `closeTrash()`
 * has cleared the banner. Writing it then would resurface a stale announcement
 * on the next open, so a closed Trash gets no banner and no focus move.
 */
function showTrashBanner({
  variant,
  message,
  detail,
}: {
  variant: OutcomeBannerVariant;
  message: string;
  detail?: string;
}): void {
  if (!isTrashOpen()) return;
  showOutcomeBanner({
    mount: TRASH_BANNER_MOUNT,
    variant,
    message,
    detail,
    returnFocusTo: $(TRASH_BANNER_MOUNT.rootSelector),
  });
}

function findUrlRow({
  utubID,
  utubUrlID,
}: {
  utubID: number;
  utubUrlID: number;
}): JQuery {
  return $(
    `${TRASH_SCOPE_IDS.urls.list} .trashRow[data-utub-id="${utubID}"][data-utub-url-id="${utubUrlID}"]`,
  );
}

function findUtubRow({ utubID }: { utubID: number }): JQuery {
  return $(`${TRASH_SCOPE_IDS.utubs.list} .trashRow[data-utub-id="${utubID}"]`);
}

/**
 * Disables a row's buttons synchronously (`.disabled` + `aria-disabled`, never
 * the native attribute) so a second activation sends nothing while the request
 * is in flight. Returns a release that re-enables only the buttons it disabled.
 */
function setRowBusy({ row }: { row: JQuery }): () => void {
  const buttons = row
    .find(ROW_BUTTONS)
    .filter((_, element) => $(element).attr("aria-disabled") !== "true");
  buttons.addClass("disabled").attr("aria-disabled", "true");
  return () => {
    buttons.removeClass("disabled").removeAttr("aria-disabled");
  };
}

/**
 * After a row leaves, focus the row that took its place, else the previous
 * row, else the tab's empty-state container.
 */
export function focusAfterRowRemoval({
  scope,
  removedIndex,
  viaSwipe = false,
}: {
  scope: TrashScope;
  removedIndex: number;
  viaSwipe?: boolean;
}): void {
  if (!isTrashOpen()) return;
  const ids = TRASH_SCOPE_IDS[scope];
  const rows = $(`${ids.list} .trashRow`);
  if (rows.length === 0) {
    $(ids.emptyState).trigger("focus");
    return;
  }
  const target = rows.eq(Math.max(0, Math.min(removedIndex, rows.length - 1)));
  target.trigger("focus");
  // After the focus move: a previously focused row's blur release must not
  // tear down the handler armed for this row.
  if (viaSwipe) armSwipeFocusReturnSuppression({ row: target });
}

/**
 * Hides the focus ring on the row that took focus after a swipe-restore (the
 * user never tapped it). Cleared on blur or the next pointerdown in the panel,
 * mirroring the URL deck's `swipe-focus-return`; keyboard and tap restores
 * never reach this and keep the ring.
 */
function armSwipeFocusReturnSuppression({ row }: { row: JQuery }): void {
  const panel = $(TRASH_PANEL);
  const release = () => {
    row.removeClass(SWIPE_FOCUS_RETURN_CLASS);
    row.off(SWIPE_FOCUS_RETURN_BLUR);
    panel.off(SWIPE_FOCUS_RETURN_POINTERDOWN);
  };
  panel.off(SWIPE_FOCUS_RETURN_POINTERDOWN);
  row.addClass(SWIPE_FOCUS_RETURN_CLASS);
  row.off(SWIPE_FOCUS_RETURN_BLUR).one(SWIPE_FOCUS_RETURN_BLUR, release);
  panel.one(SWIPE_FOCUS_RETURN_POINTERDOWN, release);
}

/**
 * Reload the list only while Trash is open: `openTrash()` reloads anyway, and a
 * background re-render must not touch a panel the user already left.
 */
function reloadTrashListIfOpen(): Promise<void> {
  return isTrashOpen() ? loadTrashList() : Promise.resolve();
}

function indexOfRow({
  scope,
  row,
}: {
  scope: TrashScope;
  row: JQuery;
}): number {
  return $(`${TRASH_SCOPE_IDS[scope].list} .trashRow`).index(row);
}

/**
 * Shared failure path for every Trash action. The Trash panel has its own
 * handler because `isUtubLockedHandled()` writes to the (hidden) URL-deck banner.
 */
export function handleTrashActionFailure({
  xhr,
  domain,
}: {
  xhr: JQuery.jqXHR;
  domain: TrashDomain;
}): void {
  if (is429Handled(xhr)) return;

  if (
    xhr.status === 403 &&
    xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
  ) {
    // Invalid CSRF token error response
    $("body").html(xhr.responseText);
    return;
  }

  const responseJSON = xhr.responseJSON as CsrfAwareBody | undefined;
  if (
    xhr.status === 403 &&
    responseJSON?.message === APP_CONFIG.strings.UTUB_IS_LOCKED
  ) {
    $(CONFIRM_MODAL).modal("hide");
    showTrashBanner({
      variant: "partial",
      message: APP_CONFIG.strings.TRASH_LOCKED,
    });
    void reloadTrashListIfOpen();
    return;
  }

  if (isNotInTrash({ xhr, domain })) {
    $(CONFIRM_MODAL).modal("hide");
    showTrashBanner({
      variant: "partial",
      message: APP_CONFIG.strings.TRASH_NOT_IN_TRASH,
    });
    void reloadTrashListIfOpen();
    void refreshTrashCount();
    return;
  }

  log("unrecoverable trash action failure", { status: xhr.status });
  window.location.assign(APP_CONFIG.routes.errorPage);
}

/** True for the 400 an in-place restore gets when the origin UTub is now trashed. */
function isDestinationRequiredFailure({ xhr }: { xhr: JQuery.jqXHR }): boolean {
  if (xhr.status !== 400) return false;
  const errorCode = (xhr.responseJSON as { errorCode?: number } | undefined)
    ?.errorCode;
  return errorCode === URL_DESTINATION_REQUIRED;
}

/**
 * Destination-restore failures the picker flow handles itself. Returns true when
 * the failure was consumed.
 */
function handleDestinationFailure({ xhr }: { xhr: JQuery.jqXHR }): boolean {
  if (xhr.status === 409) {
    const errorCode = (xhr.responseJSON as { errorCode?: number } | undefined)
      ?.errorCode;
    if (errorCode !== URL_ALREADY_IN_DESTINATION) return false;
    showTrashBanner({
      variant: "partial",
      message: APP_CONFIG.strings.TRASH_ALREADY_IN_DESTINATION,
    });
    refocusDestinationPicker();
    return true;
  }
  if (xhr.status === 400) {
    const errorCode = (xhr.responseJSON as { errorCode?: number } | undefined)
      ?.errorCode;
    if (
      errorCode !== URL_DESTINATION_REQUIRED &&
      errorCode !== URL_INVALID_DESTINATION
    ) {
      return false;
    }
    closeDestinationPicker({ returnFocus: false });
    void reloadTrashListIfOpen();
    return true;
  }
  return false;
}

/**
 * Restores a trashed URL. `destUtubID` is `undefined` for an in-place restore;
 * the key is still always passed, because a literal `{}` would make `ajaxCall`
 * send no JSON body (and no Content-Type) at all. Resolves `true` only when
 * the row was removed, `false` on every failure path (swipe snaps back on it).
 * `viaSwipe` only hides the focus ring on the row focused afterwards.
 */
export function restoreTrashedURL({
  utubID,
  utubUrlID,
  destUtubID,
  viaSwipe = false,
}: {
  utubID: number;
  utubUrlID: number;
  destUtubID?: number;
  viaSwipe?: boolean;
}): Promise<boolean> {
  const row = findUrlRow({ utubID, utubUrlID });
  const release = setRowBusy({ row });
  let restored = false;

  return new Promise((resolve) => {
    ajaxCall("post", APP_CONFIG.routes.restoreURL(utubID, utubUrlID), {
      destUtubId: destUtubID,
    })
      .done((response: UrlRestoredResponse) => {
        const removedIndex = removeTrashRow({ scope: "urls", row });
        if (response.restoredToDestination) {
          // Tags never travel to another UTub, so no lost-tag report.
          showTrashBanner({
            variant: "success",
            message: fillTemplate({
              template: APP_CONFIG.strings.TRASH_RESTORED_TO,
              values: { utub: response.utubName },
            }),
          });
        } else {
          showTrashBanner({
            variant: response.lostTagCount > 0 ? "partial" : "success",
            message: buildReviveMessage({
              lostTagCount: response.lostTagCount,
            }),
            detail: buildLostTagNamesDetail({
              lostTagNames: response.lostTagNames ?? [],
            }),
          });
        }
        restored = true;
        // Opening Trash clears the active UTub, so no "is it selected" guard: the
        // delta works from the deck's own list store, for any UTub.
        applyRowCountDelta({
          utubID: destUtubID ?? utubID,
          urlDelta: 1,
          memberDelta: 0,
        });
        focusAfterRowRemoval({ scope: "urls", removedIndex, viaSwipe });
        void refreshTrashCount();
      })
      .fail((xhr: JQuery.jqXHR) => {
        release();
        if (destUtubID !== undefined && handleDestinationFailure({ xhr })) {
          return;
        }
        if (destUtubID === undefined && isDestinationRequiredFailure({ xhr })) {
          // The origin UTub was trashed after this row was armed: re-render it
          // as an orphan (destination picker path) instead of erroring out.
          showTrashBanner({
            variant: "partial",
            message: APP_CONFIG.strings.TRASH_ORIGIN_UNAVAILABLE,
          });
          void reloadTrashListIfOpen();
          return;
        }
        handleTrashActionFailure({ xhr, domain: "url" });
      })
      .always(() => resolve(restored));
  });
}

function refreshDeckAndCount(): Promise<void> {
  const isCurrent = beginCountRequest();
  const capturedVersion = getPrefsVersion();
  return new Promise((resolve) => {
    getAllUTubs()
      .done((response) => {
        reseedListPreferences({
          preferences: response.preferences,
          capturedVersion,
        });
        buildUTubDeck(response.utubs);
        syncDeckOrderToStoreSort({
          responseSort: response.preferences?.utubSort,
        });
        // The deck is always rebuilt; only the count is dropped when superseded.
        if (!isCurrent()) return;
        setState({ trashCount: response.trashCount });
        renderTrashCount();
      })
      .fail((xhr: JQuery.jqXHR) => {
        log("deck refresh after UTub restore failed", { status: xhr.status });
      })
      .always(() => resolve());
  });
}

/** Restores a trashed UTub; its ride-along URL rows leave Trash with it. */
export function restoreTrashedUTub({
  utubID,
}: {
  utubID: number;
}): Promise<void> {
  const row = findUtubRow({ utubID });
  const removedIndex = indexOfRow({ scope: "utubs", row });
  const release = setRowBusy({ row });

  return new Promise((resolve) => {
    ajaxCall("post", APP_CONFIG.routes.restoreUTub(utubID), null)
      .done((response: UtubRestoredResponse) => {
        showTrashBanner({
          variant: "success",
          message: fillTemplate({
            template: APP_CONFIG.strings.TRASH_UTUB_RESTORED,
            values: { utub: response.utubName },
          }),
        });
        // One GET /utubs response rebuilds the deck and sets the badge.
        void Promise.all([refreshDeckAndCount(), reloadTrashListIfOpen()]).then(
          () => {
            focusAfterRowRemoval({ scope: "utubs", removedIndex });
          },
        );
      })
      .fail((xhr: JQuery.jqXHR) => {
        release();
        handleTrashActionFailure({ xhr, domain: "utub" });
      })
      .always(() => resolve());
  });
}

// --- Confirm modal: shared #confirmModal helper lives in ../confirm-modal.ts ---

/** Confirms, then permanently deletes one trashed URL. */
export function confirmAndPurgeURL({ item }: { item: TrashedUrlItem }): void {
  showConfirmModal({
    title: APP_CONFIG.strings.TRASH_CONFIRM_PURGE_TITLE,
    body: fillTemplate({
      template: APP_CONFIG.strings.TRASH_CONFIRM_PURGE_URL_BODY,
      values: { title: item.urlTitle },
    }),
    submitLabel: APP_CONFIG.strings.TRASH_DELETE_FOREVER,
    namespace: "trashPurge",
    onConfirm: () => purgeURL({ item }),
  });
}

function purgeURL({ item }: { item: TrashedUrlItem }): void {
  const row = findUrlRow({
    utubID: item.utubID,
    utubUrlID: item.utubUrlID,
  });
  const release = setRowBusy({ row });
  $(MODAL_SUBMIT).prop("disabled", true);

  ajaxCall(
    "delete",
    APP_CONFIG.routes.purgeURL(item.utubID, item.utubUrlID),
    [],
  )
    .done((_response: UrlPurgedResponse) => {
      hideConfirmModal();
      const removedIndex = removeTrashRow({ scope: "urls", row });
      showTrashBanner({
        variant: "success",
        message: APP_CONFIG.strings.TRASH_URL_PURGED,
      });
      focusAfterRowRemoval({ scope: "urls", removedIndex });
      void refreshTrashCount();
    })
    .fail((xhr: JQuery.jqXHR) => {
      release();
      $(MODAL_SUBMIT).prop("disabled", false);
      handleTrashActionFailure({ xhr, domain: "url" });
    });
}

/** Picks the singular template for a count of exactly one, else the plural. */
function pickCountTemplate({
  count,
  one,
  other,
}: {
  count: number;
  one: string;
  other: string;
}): string {
  return count === 1 ? one : other;
}

/** Confirms, then permanently deletes one trashed UTub with all its URLs. */
export function confirmAndPurgeUTub({ item }: { item: TrashedUtubItem }): void {
  showConfirmModal({
    title: APP_CONFIG.strings.TRASH_CONFIRM_PURGE_TITLE,
    body: fillTemplate({
      template: pickCountTemplate({
        count: item.urlCount,
        one: APP_CONFIG.strings.TRASH_CONFIRM_PURGE_UTUB_BODY_ONE,
        other: APP_CONFIG.strings.TRASH_CONFIRM_PURGE_UTUB_BODY,
      }),
      values: { utub: item.utubName, n: String(item.urlCount) },
    }),
    submitLabel: APP_CONFIG.strings.TRASH_DELETE_FOREVER,
    namespace: "trashPurge",
    onConfirm: () => purgeUTub({ item }),
  });
}

function purgeUTub({ item }: { item: TrashedUtubItem }): void {
  const row = findUtubRow({ utubID: item.utubID });
  const removedIndex = indexOfRow({ scope: "utubs", row });
  const release = setRowBusy({ row });
  $(MODAL_SUBMIT).prop("disabled", true);

  ajaxCall("delete", APP_CONFIG.routes.purgeUTub(item.utubID), [])
    .done((response: UtubPurgedResponse) => {
      hideConfirmModal();
      showTrashBanner({
        variant: "success",
        message: fillTemplate({
          template: APP_CONFIG.strings.TRASH_UTUB_PURGED,
          values: { utub: response.utubName },
        }),
      });
      // Its URL rows left Trash too, so reload instead of removing one row.
      void reloadTrashListIfOpen().then(() => {
        focusAfterRowRemoval({ scope: "utubs", removedIndex });
      });
      void refreshTrashCount();
    })
    .fail((xhr: JQuery.jqXHR) => {
      release();
      $(MODAL_SUBMIT).prop("disabled", false);
      handleTrashActionFailure({ xhr, domain: "utub" });
    });
}

/** Confirms, then permanently deletes everything deletable in the active tab. */
export function confirmAndEmptyTrash(): void {
  const scope = getActiveTrashScope();
  const state = getTrashListState();
  const listedAt = state.listedAt;
  if (listedAt === null) return;

  const rows: Array<{ canDelete: boolean }> =
    scope === "urls" ? state.urls : state.utubs;
  const deletableCount = rows.filter((row) => row.canDelete).length;
  const bodyTemplate =
    scope === "urls"
      ? pickCountTemplate({
          count: deletableCount,
          one: APP_CONFIG.strings.TRASH_CONFIRM_EMPTY_URLS_BODY_ONE,
          other: APP_CONFIG.strings.TRASH_CONFIRM_EMPTY_URLS_BODY,
        })
      : pickCountTemplate({
          count: deletableCount,
          one: APP_CONFIG.strings.TRASH_CONFIRM_EMPTY_UTUBS_BODY_ONE,
          other: APP_CONFIG.strings.TRASH_CONFIRM_EMPTY_UTUBS_BODY,
        });

  showConfirmModal({
    title: APP_CONFIG.strings.TRASH_CONFIRM_EMPTY_TITLE,
    body: fillTemplate({
      template: bodyTemplate,
      values: { n: String(deletableCount) },
    }),
    submitLabel: APP_CONFIG.strings.TRASH_DELETE_FOREVER,
    namespace: "trashEmpty",
    onConfirm: () => emptyTrash({ scope, listedAt }),
  });
}

function emptyTrash({
  scope,
  listedAt,
}: {
  scope: TrashScope;
  listedAt: string;
}): void {
  $(MODAL_SUBMIT).prop("disabled", true);
  $(EMPTY_TRASH_BUTTON).prop("disabled", true);

  // `listedAt` is forwarded verbatim: the server only sweeps items that entered
  // Trash at or before the list the user was looking at.
  ajaxCall(
    "post",
    APP_CONFIG.routes.emptyTrash,
    { scope, listedAt },
    EMPTY_TRASH_TIMEOUT_MS,
  )
    .done((response: TrashEmptiedResponse) => {
      hideConfirmModal();
      const skipped = response.totalSkippedLocked;
      showTrashBanner({
        variant: skipped > 0 ? "partial" : "success",
        message: fillTemplate({
          template: pickCountTemplate({
            count: response.totalPurged,
            one: APP_CONFIG.strings.TRASH_EMPTIED_ONE,
            other: APP_CONFIG.strings.TRASH_EMPTIED,
          }),
          values: { n: String(response.totalPurged) },
        }),
        detail:
          skipped > 0
            ? fillTemplate({
                template: pickCountTemplate({
                  count: skipped,
                  one: APP_CONFIG.strings.TRASH_EMPTY_SKIPPED_LOCKED_ONE,
                  other: APP_CONFIG.strings.TRASH_EMPTY_SKIPPED_LOCKED,
                }),
                values: { n: String(skipped) },
              })
            : undefined,
      });
      void reloadTrashListIfOpen().then(() => {
        focusAfterRowRemoval({ scope, removedIndex: 0 });
      });
      void refreshTrashCount();
    })
    .fail((xhr: JQuery.jqXHR) => {
      $(MODAL_SUBMIT).prop("disabled", false);
      // The list state is unchanged, so the button's own enablement still holds.
      $(EMPTY_TRASH_BUTTON).prop("disabled", false);
      handleTrashActionFailure({
        xhr,
        domain: scope === "urls" ? "url" : "utub",
      });
    });
}

// --- Row dispatch ---

function findUrlItem({ row }: { row: JQuery }): TrashedUrlItem | undefined {
  const utubID = Number(row.attr("data-utub-id"));
  const utubUrlID = Number(row.attr("data-utub-url-id"));
  return getTrashListState().urls.find(
    (item) => item.utubID === utubID && item.utubUrlID === utubUrlID,
  );
}

function findUtubItem({ row }: { row: JQuery }): TrashedUtubItem | undefined {
  const utubID = Number(row.attr("data-utub-id"));
  return getTrashListState().utubs.find((item) => item.utubID === utubID);
}

function handleUrlRowClick(event: JQuery.TriggeredEvent): void {
  // A committed swipe is followed by a click on whatever was under the finger.
  if (consumeTrashClickSuppression()) return;
  const button = $(event.target).closest(ROW_BUTTONS);
  if (button.length === 0 || button.attr("aria-disabled") === "true") return;
  const row = button.closest(".trashRow");
  const item = findUrlItem({ row });
  if (item === undefined) return;

  if (button.hasClass("trashBtnPurge")) {
    confirmAndPurgeURL({ item });
    return;
  }
  if (item.originUtubTrashed) {
    openDestinationPicker({ item, row, onRestore: restoreTrashedURL });
    return;
  }
  void restoreTrashedURL({
    utubID: item.utubID,
    utubUrlID: item.utubUrlID,
    destUtubID: undefined,
  });
}

function handleUtubRowClick(event: JQuery.TriggeredEvent): void {
  const button = $(event.target).closest(ROW_BUTTONS);
  if (button.length === 0 || button.attr("aria-disabled") === "true") return;
  const item = findUtubItem({ row: button.closest(".trashRow") });
  if (item === undefined) return;

  if (button.hasClass("trashBtnPurge")) {
    confirmAndPurgeUTub({ item });
    return;
  }
  void restoreTrashedUTub({ utubID: item.utubID });
}

export function initTrashActions(): void {
  initDestinationPicker();
  $(TRASH_SCOPE_IDS.urls.list).offAndOnExact(
    "click.trashActions",
    handleUrlRowClick,
  );
  $(TRASH_SCOPE_IDS.utubs.list).offAndOnExact(
    "click.trashActions",
    handleUtubRowClick,
  );
  $(EMPTY_TRASH_BUTTON).offAndOnExact("click.trashActions", () => {
    if ($(EMPTY_TRASH_BUTTON).attr("aria-disabled") === "true") return;
    confirmAndEmptyTrash();
  });
}
