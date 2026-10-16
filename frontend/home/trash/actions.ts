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
import { buildUTubDeck } from "../utubs/deck.js";
import { getAllUTubs } from "../utubs/utils.js";
import {
  buildReviveMessage,
  showOutcomeBanner,
} from "../urls/outcome-banner.js";
import type { OutcomeBannerVariant } from "../urls/outcome-banner.js";
import { TRASH_BANNER_MOUNT } from "./banner.js";
import { refreshTrashCount, renderTrashCount } from "./count.js";
import { isNotInTrash } from "./error-codes.js";
import type { TrashDomain } from "./error-codes.js";
import { loadTrashList } from "./list.js";
import {
  TRASH_SCOPE_IDS,
  getTrashListState,
  removeTrashRow,
} from "./render.js";
import { getActiveTrashScope } from "./tabs.js";
import type { TrashScope } from "./tabs.js";

const log = debug("trash:actions");

const CONFIRM_MODAL = "#confirmModal";
const MODAL_SUBMIT = "#modalSubmit";
const MODAL_DISMISS = "#modalDismiss";
const MODAL_REDIRECT = "#modalRedirect";
const EMPTY_TRASH_BUTTON = "#TrashBtnEmpty";
const ROW_BUTTONS = ".trashBtnRestore, .trashBtnPurge";
const EMPTY_TRASH_TIMEOUT_MS = 10_000;

type UrlRestoredResponse = SuccessResponse<"restoreUrl">;
type UrlPurgedResponse = SuccessResponse<"purgeUrl">;
type UtubRestoredResponse = SuccessResponse<"restoreUtub">;
type UtubPurgedResponse = SuccessResponse<"purgeUtub">;
type TrashEmptiedResponse = SuccessResponse<"emptyTrash">;

type CsrfAwareBody = { message?: string };

function showTrashBanner({
  variant,
  message,
  detail,
}: {
  variant: OutcomeBannerVariant;
  message: string;
  detail?: string;
}): void {
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
}: {
  scope: TrashScope;
  removedIndex: number;
}): void {
  const ids = TRASH_SCOPE_IDS[scope];
  const rows = $(`${ids.list} .trashRow`);
  if (rows.length === 0) {
    $(ids.emptyState).trigger("focus");
    return;
  }
  const target = Math.max(0, Math.min(removedIndex, rows.length - 1));
  rows.eq(target).trigger("focus");
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
    void loadTrashList();
    return;
  }

  if (isNotInTrash({ xhr, domain })) {
    $(CONFIRM_MODAL).modal("hide");
    showTrashBanner({
      variant: "partial",
      message: APP_CONFIG.strings.TRASH_NOT_IN_TRASH,
    });
    void loadTrashList();
    void refreshTrashCount();
    return;
  }

  log("unrecoverable trash action failure", { status: xhr.status });
  window.location.assign(APP_CONFIG.routes.errorPage);
}

/**
 * Step 8 fills this in: the destination picker for a URL whose origin UTub is
 * trashed. Until then the Restore button on such a row does nothing.
 */
export function openDestinationPicker({
  item,
}: {
  item: TrashedUrlItem;
  row: JQuery;
}): void {
  log("openDestinationPicker (not yet implemented)", {
    utubUrlID: item.utubUrlID,
  });
}

/**
 * Restores a trashed URL. `destUtubID` is `undefined` for an in-place restore;
 * the key is still always passed, because a literal `{}` would make `ajaxCall`
 * send no JSON body (and no Content-Type) at all.
 */
export function restoreTrashedURL({
  utubID,
  utubUrlID,
  destUtubID,
}: {
  utubID: number;
  utubUrlID: number;
  destUtubID?: number;
}): Promise<void> {
  const row = findUrlRow({ utubID, utubUrlID });
  const release = setRowBusy({ row });

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
          });
        }
        focusAfterRowRemoval({ scope: "urls", removedIndex });
        void refreshTrashCount();
      })
      .fail((xhr: JQuery.jqXHR) => {
        release();
        handleTrashActionFailure({ xhr, domain: "url" });
      })
      .always(() => resolve());
  });
}

function refreshDeckAndCount(): Promise<void> {
  return new Promise((resolve) => {
    getAllUTubs()
      .done((response) => {
        buildUTubDeck(response.utubs);
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
        void Promise.all([refreshDeckAndCount(), loadTrashList()]).then(() => {
          focusAfterRowRemoval({ scope: "utubs", removedIndex });
        });
      })
      .fail((xhr: JQuery.jqXHR) => {
        release();
        handleTrashActionFailure({ xhr, domain: "utub" });
      })
      .always(() => resolve());
  });
}

// --- Confirm modal (shared #confirmModal) ---

function showConfirmModal({
  title,
  body,
  submitLabel,
  namespace,
  onConfirm,
}: {
  title: string;
  body: string;
  submitLabel: string;
  namespace: "trashPurge" | "trashEmpty";
  onConfirm: () => void;
}): void {
  $("#confirmModalTitle").text(title);
  $("#confirmModalBody").text(body);

  // #confirmModal is shared: reset the submit class so a prior flow's styling
  // never leaks into this destructive confirm.
  $(MODAL_SUBMIT)
    .removeClass()
    .addClass("btn btn-danger")
    .text(submitLabel)
    .prop("disabled", false)
    .off(`click.${namespace}`)
    .on(`click.${namespace}`, (event: JQuery.TriggeredEvent) => {
      event.preventDefault();
      onConfirm();
    });

  $(MODAL_DISMISS)
    .text(APP_CONFIG.strings.URL_BULK_DELETE_CANCEL)
    .prop("disabled", false)
    .off(`click.${namespace}`)
    .on(`click.${namespace}`, (event: JQuery.TriggeredEvent) => {
      event.preventDefault();
      $(CONFIRM_MODAL).modal("hide");
    });

  // Self-unbinding: the modal is shared, so these handlers must only live for
  // this confirm session, whichever way it closes.
  $(CONFIRM_MODAL)
    .off(`hidden.bs.modal.${namespace}`)
    .on(`hidden.bs.modal.${namespace}`, () => {
      $(CONFIRM_MODAL).off(`hidden.bs.modal.${namespace}`);
      $(MODAL_SUBMIT).off(`click.${namespace}`);
      $(MODAL_DISMISS).off(`click.${namespace}`);
    });

  $(MODAL_REDIRECT).hide();
  $(CONFIRM_MODAL).modal("show");
}

function hideConfirmModal(): void {
  $(CONFIRM_MODAL).modal("hide");
}

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

/** Confirms, then permanently deletes one trashed UTub with all its URLs. */
export function confirmAndPurgeUTub({ item }: { item: TrashedUtubItem }): void {
  showConfirmModal({
    title: APP_CONFIG.strings.TRASH_CONFIRM_PURGE_TITLE,
    body: fillTemplate({
      template: APP_CONFIG.strings.TRASH_CONFIRM_PURGE_UTUB_BODY,
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
      void loadTrashList().then(() => {
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
      ? APP_CONFIG.strings.TRASH_CONFIRM_EMPTY_URLS_BODY
      : APP_CONFIG.strings.TRASH_CONFIRM_EMPTY_UTUBS_BODY;

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
          template: APP_CONFIG.strings.TRASH_EMPTIED,
          values: { n: String(response.totalPurged) },
        }),
        detail:
          skipped > 0
            ? fillTemplate({
                template: APP_CONFIG.strings.TRASH_EMPTY_SKIPPED_LOCKED,
                values: { n: String(skipped) },
              })
            : undefined,
      });
      void loadTrashList().then(() => {
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
    openDestinationPicker({ item, row });
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
