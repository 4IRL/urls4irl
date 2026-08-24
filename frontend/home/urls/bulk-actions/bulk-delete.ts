import type { SuccessResponse } from "../../../types/api-helpers.d.ts";
import type { UtubUrlItem } from "../../../types/url.js";

import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { SHOW_LOADING_ICON_AFTER_MS } from "../../../lib/constants.js";
import { debug } from "../../../lib/debug.js";
import { AppEvents, on } from "../../../lib/event-bus.js";
import { getState, setState } from "../../../store/app-store.js";
import { isUtubLockedHandled } from "../../utub-locked.js";
import {
  updateTagFilteringOnURLOrURLTagDeletion,
  updateVisibleURLsForTagCount,
  writeTagChipDenominator,
} from "../cards/filtering.js";
import { showURLsEmptyState } from "../empty-state.js";
import { hideURLSearchIcon } from "../search.js";
import {
  type BulkAction,
  type BulkActionContext,
  registerBulkAction,
} from "./bulk-action-registry.js";
import { hiddenSelectedCount } from "./bulk-bar.js";
import { exitMultiSelectMode } from "./bulk-mode.js";
import { pruneRemovedFromSelection } from "./bulk-selection.js";
import { flashCardResultCues } from "./card-cues.js";
import {
  isAnyBulkPickerOpen,
  registerPickerClose,
  setPickerOpen,
} from "./picker-guard.js";

const log = debug("urls:cards");

type DeleteUrlsResponse = SuccessResponse<"deleteUrlsFromUtub">;

const CONFIRM_MODAL_SELECTOR = "#confirmModal";
const CONFIRM_MODAL_TITLE_SELECTOR = "#confirmModalTitle";
const CONFIRM_MODAL_BODY_SELECTOR = "#confirmModalBody";
const MODAL_SUBMIT_SELECTOR = "#modalSubmit";
const MODAL_DISMISS_SELECTOR = "#modalDismiss";
const MODAL_REDIRECT_SELECTOR = "#modalRedirect";
const BANNER_SELECTOR = "#bulkDeleteResultBanner";
// Deck-level live region (subheader) — survives exitMultiSelectMode()'s bulk-bar
// banner teardown, so the deck-empties outcome is announced there, NOT in the
// bulk bar banner which is cleared on mode exit.
const OUTCOME_ANNOUNCEMENT_SELECTOR = "#URLDeckOutcomeAnnouncement";
// Stable in-mode focus-return anchor (the header Exit control) — never the
// ephemeral #bulkActionButtons Delete button, which rebuilds on selection change.
const FOCUS_RETURN_SELECTOR = "#bulkSelectExit";
const SUBMIT_LOADING_CLASS = "bulkDeleteSubmitLoading";

// Bounds the worst case (MAX_BULK_DELETE_URLS = 100 rows + their tag rows in one
// transaction) well above the 35s single-row delete precedent.
const DELETE_REQUEST_TIMEOUT_MS = 35000;

// Trusted static trash icon. Injected as raw HTML via the registry's
// `.prepend(iconHtml)`, so this MUST stay a hard-coded literal — never
// interpolate user content into it (HTML-injection sink). `stroke=currentColor`
// so it inherits the `.barBtn.danger` red text colour.
const BULK_DELETE_ICON_HTML =
  '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" ' +
  'fill="none" stroke="currentColor" stroke-width="1.6" ' +
  'stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24" ' +
  'aria-hidden="true">' +
  '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>' +
  "</svg>";

// --- Confirm-open flag (owned here; mirrored into the shared registry) ---------

let bulkDeleteConfirmOpen = false;
// When true, the hidden.bs.modal.bulkDelete handler skips its manual
// #bulkSelectExit focus-return. Set on the deck-empties path (where
// toggleBar(false) owns focus on mode exit) and on every closeAllPickers/mode-exit
// close, and reset to false on each confirm open + after each handled close.
let suppressFocusReturn = false;
let submitInFlight = false;
let loadingTimeoutID: number | null = null;

/** Whether the bulk-delete confirm modal is currently open. */
export function isBulkDeleteConfirmOpen(): boolean {
  return bulkDeleteConfirmOpen;
}

/** Set the confirm-open flag (and mirror it into the shared picker registry). */
export function setBulkDeleteConfirmOpen(open: boolean): void {
  bulkDeleteConfirmOpen = open;
  // Keep the shared open-picker registry in lock-step with this module's flag so
  // isAnyBulkPickerOpen()/closeAllPickers() (picker-guard.ts) always agree —
  // mirroring setBulkCopyPickerOpen/setBulkTagPickerOpen.
  setPickerOpen("bulk-delete", open);
}

// --- Action registration ------------------------------------------------------

/** True when ≥1 currently-selected URL is one this user may delete. */
function hasDeletableSelection(context: BulkActionContext): boolean {
  if (context.selectedURLCardIDs.length === 0) return false;
  const selected = new Set(context.selectedURLCardIDs);
  return context.urls.some(
    (url: UtubUrlItem) => selected.has(url.utubUrlID) && url.canDelete,
  );
}

const bulkDeleteAction: BulkAction = {
  id: "bulk-delete",
  label: APP_CONFIG.strings.URL_BULK_DELETE_LABEL,
  iconHtml: BULK_DELETE_ICON_HTML,
  // Destructive variant — bulk-bar.ts adds this to the rendered .barBtn so the
  // .barBtn.danger CSS (red text/border + own full-width row on the mobile
  // drawer) applies.
  className: "danger",
  // Available only when something is selected AND ≥1 selected URL is deletable by
  // this user (server re-checks each id as the source of truth — partial-skip).
  isAvailable: hasDeletableSelection,
  onActivate: openBulkDeleteConfirm,
};

// Bus subscriptions are process-wide (no rebind), and the action registry is
// append-only, so guard both against a repeat initBulkActions().
let _bulkDeleteInitialized = false;

/**
 * Register the bulk-delete action, its confirm-modal teardown callback, and the
 * mode-exit teardown subscription. Called from initBulkActions(); the import
 * itself is what makes registration run.
 */
export function initBulkDelete(): void {
  if (_bulkDeleteInitialized) return;
  _bulkDeleteInitialized = true;

  registerBulkAction(bulkDeleteAction);

  // Register this modal's teardown so closeAllPickers() (picker-guard.ts, invoked
  // by bulk-mode.ts's exitMultiSelectMode before it clears the selection) tears
  // the confirm down consistently with the tag/copy pickers. returnFocus:false —
  // toggleBar(false) owns focus on mode exit.
  registerPickerClose("bulk-delete", () =>
    teardownConfirm({ returnFocus: false }),
  );

  // Mode exit / UTub switch tears the confirm down even if the user never closed
  // it. This module depends on the event, never on bulk-mode.ts, keeping the
  // dependency one-way. Idempotent with closeAllPickers()'s own teardown.
  on(AppEvents.URL_MULTISELECT_MODE_CHANGED, ({ active }) => {
    if (active === false && isBulkDeleteConfirmOpen()) {
      log("bulk delete confirm torn down on multi-select mode exit");
      teardownConfirm({ returnFocus: false });
    }
  });
}

// --- Open / confirm lifecycle -------------------------------------------------

/**
 * Snapshot the current selection + its deletable/non-deletable partition and
 * open the shared #confirmModal. Re-entrant / cross-picker activation is a
 * defined no-op (only one bulk sub-picker/confirm open at a time). Everything the
 * confirm acts on is captured HERE (the bar/checkboxes stay live while the modal
 * is open — #confirmModal is not an in-deck picker-guard mount — so the submit
 * MUST act on this snapshot, never a fresh store read).
 */
function openBulkDeleteConfirm(context: BulkActionContext): void {
  // Re-entrant / cross-picker guard first (mirrors openBulkCopyPicker /
  // openBulkTagPicker) so the delete confirm cannot stack on an already-open
  // bulk-tag/bulk-copy picker.
  if (isAnyBulkPickerOpen()) return;

  const activeUTubID = getState().activeUTubID;
  if (activeUTubID === null) return;

  const selectedSnapshot = [...context.selectedURLCardIDs];
  if (selectedSnapshot.length === 0) return;

  // Partition the SELECTION by canDelete at open. Only deletable ids are sent;
  // the non-deletable ids stay in the deck as skipped survivors (amber cue).
  const deletableIds = new Set(
    context.urls
      .filter((url: UtubUrlItem) => url.canDelete)
      .map((url: UtubUrlItem) => url.utubUrlID),
  );
  const deletableSnapshot = selectedSnapshot.filter((id) =>
    deletableIds.has(id),
  );
  const skippedSnapshot = selectedSnapshot.filter(
    (id) => !deletableIds.has(id),
  );
  // Defensive: isAvailable already gates on ≥1 deletable, but never open a
  // destructive confirm that would send an empty delete.
  if (deletableSnapshot.length === 0) return;

  const hiddenCount = hiddenSelectedCount(selectedSnapshot);

  log("open bulk delete confirm", {
    activeUTubID,
    totalSelected: selectedSnapshot.length,
    deletable: deletableSnapshot.length,
    skipped: skippedSnapshot.length,
    hiddenCount,
  });

  suppressFocusReturn = false;
  submitInFlight = false;
  setBulkDeleteConfirmOpen(true);

  renderConfirmModal({
    totalSelected: selectedSnapshot.length,
    deletableCount: deletableSnapshot.length,
    hiddenCount,
    skippedCount: skippedSnapshot.length,
    deletableSnapshot,
    skippedSnapshot,
  });
}

/**
 * Populate the shared #confirmModal for the delete confirm: a count-aware title,
 * a body that discloses hidden-by-filter + non-deletable scope, a btn-danger
 * submit labelled with the deletable count, and the "Just kidding" dismiss. All
 * text is bridged/static (XSS-safe: no URL title is ever interpolated).
 */
function renderConfirmModal({
  totalSelected,
  deletableCount,
  hiddenCount,
  skippedCount,
  deletableSnapshot,
  skippedSnapshot,
}: {
  totalSelected: number;
  deletableCount: number;
  hiddenCount: number;
  skippedCount: number;
  deletableSnapshot: number[];
  skippedSnapshot: number[];
}): void {
  const title =
    totalSelected === 1
      ? APP_CONFIG.strings.URL_BULK_DELETE_CONFIRM_TITLE_ONE
      : APP_CONFIG.strings.URL_BULK_DELETE_CONFIRM_TITLE.replace(
          "{n}",
          String(totalSelected),
        );
  $(CONFIRM_MODAL_TITLE_SELECTOR).text(title);

  const body = $(CONFIRM_MODAL_BODY_SELECTOR);
  body.empty();
  body.append(
    $(document.createElement("div")).text(
      APP_CONFIG.strings.URL_BULK_DELETE_CONFIRM_BODY,
    ),
  );
  const warnings: string[] = [];
  if (hiddenCount > 0) {
    warnings.push(
      hiddenCount === 1
        ? APP_CONFIG.strings.URL_BULK_DELETE_HIDDEN_WARNING_ONE
        : APP_CONFIG.strings.URL_BULK_DELETE_HIDDEN_WARNING.replace(
            "{n}",
            String(hiddenCount),
          ),
    );
  }
  if (skippedCount > 0) {
    warnings.push(
      skippedCount === 1
        ? APP_CONFIG.strings.URL_BULK_DELETE_SKIPPED_WARNING_ONE
        : APP_CONFIG.strings.URL_BULK_DELETE_SKIPPED_WARNING.replace(
            "{n}",
            String(skippedCount),
          ),
    );
  }
  if (warnings.length > 0) {
    const warn = $(document.createElement("div")).addClass(
      "bulkDeleteConfirmWarn",
    );
    warnings.forEach((warning) =>
      warn.append($(document.createElement("div")).text(warning)),
    );
    body.append(warn);
  }

  const submitLabel =
    deletableCount === 1
      ? APP_CONFIG.strings.URL_BULK_DELETE_SUBMIT_ONE
      : APP_CONFIG.strings.URL_BULK_DELETE_SUBMIT.replace(
          "{n}",
          String(deletableCount),
        );
  // #confirmModal is shared; other flows (e.g. utubs/create.ts) leave #modalSubmit
  // as `btn btn-success`. Reset the class list so this destructive submit always
  // renders as `btn btn-danger` (never green) regardless of the prior flow.
  $(MODAL_SUBMIT_SELECTOR)
    .removeClass()
    .addClass("btn btn-danger")
    .text(submitLabel)
    .prop("disabled", false)
    .offAndOn("click", function (event: JQuery.TriggeredEvent) {
      event.preventDefault();
      submitDelete({ deletableSnapshot, skippedSnapshot });
    });

  $(MODAL_DISMISS_SELECTOR)
    .text(APP_CONFIG.strings.URL_BULK_DELETE_CANCEL)
    .prop("disabled", false)
    .offAndOn("click", function (event: JQuery.TriggeredEvent) {
      event.preventDefault();
      // Cancel fires NO request.
      teardownConfirm({ returnFocus: true });
    });

  // No redirect button on this modal.
  $(MODAL_REDIRECT_SELECTOR).hide().hideClass();

  // Focus-return + open-flag reset on EVERY close path (dismiss/X/Escape/backdrop,
  // delete-success-with-survivors, 400-fail) EXCEPT deck-empties — Bootstrap fires
  // hidden.bs.modal after its own transition-end/focus-restore, so returning focus
  // here (rather than synchronously after .modal('hide')) never races Bootstrap.
  $(CONFIRM_MODAL_SELECTOR).offAndOnExact(
    "hidden.bs.modal.bulkDelete",
    function () {
      // Self-unbind: #confirmModal is shared, so this bulk-delete-scoped handler
      // must fire only for the close of THIS confirm session — not a later close
      // driven by another flow (single URL delete, UTub rename, …). Re-bound on
      // the next open by offAndOnExact.
      $(CONFIRM_MODAL_SELECTOR).off("hidden.bs.modal.bulkDelete");
      // FIRST, so isAnyBulkPickerOpen() reflects the closed modal on every path,
      // including a closeAllPickers()-driven close.
      setBulkDeleteConfirmOpen(false);
      if (suppressFocusReturn) {
        suppressFocusReturn = false;
        return;
      }
      const exitAnchor = $(FOCUS_RETURN_SELECTOR);
      if (exitAnchor.length > 0) exitAnchor[0]?.focus();
    },
  );

  $(CONFIRM_MODAL_SELECTOR).modal("show");
}

/**
 * Hide the confirm modal and reset its open flag. `returnFocus:false` suppresses
 * the hidden-handler's manual #bulkSelectExit focus (used by mode-exit /
 * closeAllPickers, where toggleBar(false) owns focus).
 */
function teardownConfirm({ returnFocus }: { returnFocus: boolean }): void {
  suppressFocusReturn = !returnFocus;
  if (loadingTimeoutID !== null) {
    clearTimeout(loadingTimeoutID);
    loadingTimeoutID = null;
  }
  $(CONFIRM_MODAL_SELECTOR).modal("hide");
  // Reset the flag directly too: in non-Bootstrap test envs the hidden.bs.modal
  // event does not fire, so the handler above would not run. Idempotent with it.
  setBulkDeleteConfirmOpen(false);
}

// --- Submit -------------------------------------------------------------------

/**
 * Post the deletable snapshot to the active UTub. Disables both footer buttons +
 * schedules a delayed spinner immediately, then acts on the captured snapshot in
 * the response handlers (never a fresh store re-read).
 */
function submitDelete({
  deletableSnapshot,
  skippedSnapshot,
}: {
  deletableSnapshot: number[];
  skippedSnapshot: number[];
}): void {
  if (submitInFlight) return;
  const sourceUTubID = getState().activeUTubID;
  if (sourceUTubID === null) return;

  const submitBtn = $(MODAL_SUBMIT_SELECTOR);
  const dismissBtn = $(MODAL_DISMISS_SELECTOR);

  submitInFlight = true;
  submitBtn.prop("disabled", true);
  dismissBtn.prop("disabled", true);
  loadingTimeoutID = window.setTimeout(() => {
    submitBtn.addClass(SUBMIT_LOADING_CLASS);
  }, SHOW_LOADING_ICON_AFTER_MS);

  log("submit bulk delete", { sourceUTubID, deletableSnapshot });

  const request = ajaxCall(
    "post",
    APP_CONFIG.routes.bulkDeleteURLs(sourceUTubID),
    { utubUrlIds: deletableSnapshot },
    DELETE_REQUEST_TIMEOUT_MS,
  );

  request.done(function (
    response: DeleteUrlsResponse,
    _: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    if (xhr.status !== 200) return;
    // Bail if the active UTub changed while the request was in flight — the
    // banner + deck mutation target a deck that is no longer showing.
    if (getState().activeUTubID !== sourceUTubID) return;
    handleDeleteSuccess({ response, skippedSnapshot });
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    handleDeleteFail({ xhr, sourceUTubID });
  });

  request.always(function () {
    submitInFlight = false;
    if (loadingTimeoutID !== null) {
      clearTimeout(loadingTimeoutID);
      loadingTimeoutID = null;
    }
    $(MODAL_SUBMIT_SELECTOR)
      .removeClass(SUBMIT_LOADING_CLASS)
      .prop("disabled", false);
    $(MODAL_DISMISS_SELECTOR).prop("disabled", false);
  });
}

// --- Success (active-deck mutation) -------------------------------------------

function handleDeleteSuccess({
  response,
  skippedSnapshot,
}: {
  response: DeleteUrlsResponse;
  skippedSnapshot: number[];
}): void {
  // Act on the SERVER-reported deleted ids (the source of truth), kept a
  // number[] throughout to match pruneRemovedFromSelection's signature.
  const deletedIds: number[] = response.deleted.map((entry) => entry.utubUrlID);
  const deletedCount = deletedIds.length;
  // Skipped survivors = the client-side non-deletable partition UNION any ids the
  // server itself reported skipped (permission drift between deck load and
  // confirm — the server is the source of truth). Deduped; both stay in the deck.
  const skippedIds = [
    ...new Set([
      ...skippedSnapshot,
      ...response.skipped.map((entry) => entry.utubUrlID),
    ]),
  ];
  const skippedCount = skippedIds.length;

  log("bulk delete success", { deletedCount, skippedCount });

  // Store patch: drop the deleted URLs, then prune them from the selection
  // (pruneRemovedFromSelection emits URL_MULTISELECT_CHANGED via commitSelection).
  setState({
    urls: getState().urls.filter(
      (url: UtubUrlItem) => !deletedIds.includes(url.utubUrlID),
    ),
  });
  pruneRemovedFromSelection(deletedIds);

  // Apply the aggregate per-tag applied count (the denominator half of each "X /
  // Y" chip) ONCE from server data; the numerator half is recomputed below.
  applyTagCountsInUtub(response.tagCountsInUtub);

  // Amber "Can't delete" cue on each non-deletable survivor.
  if (skippedCount > 0) {
    flashCardResultCues({
      cues: skippedIds.map((utubUrlID) => ({
        utubUrlID,
        variant: "skipped" as const,
        label: APP_CONFIG.strings.URL_BULK_CARD_CANT_DELETE,
      })),
    });
  }

  const deckEmpties = getState().urls.length === 0;

  if (deckEmpties) {
    // Persist the outcome in the deck-level live region BEFORE the empty-state /
    // mode-exit path clears the bulk bar (and its banner).
    $(OUTCOME_ANNOUNCEMENT_SELECTOR).text(deletedOutcomeText(deletedCount));
  } else {
    renderDeleteResultBanner({ deletedCount, skippedCount });
  }

  // Close the confirm modal now (before the fade). Suppress the manual focus
  // return on the deck-empties path — toggleBar(false) owns focus on mode exit.
  suppressFocusReturn = deckEmpties;
  $(CONFIRM_MODAL_SELECTOR).modal("hide");
  setBulkDeleteConfirmOpen(false);

  // Fade + remove the deleted rows, then finish deck bookkeeping once they're
  // gone (a batch .promise() so the recompute runs after ALL fades complete).
  const rowSelector = deletedIds
    .map((id) => `.urlRow[utuburlid=${id}]`)
    .join(",");
  const deletedRows = rowSelector ? $(rowSelector) : $();
  if (deletedRows.length > 0) {
    deletedRows
      .fadeOut("slow")
      .promise()
      .done(function () {
        deletedRows.remove();
        finishDeckAfterRemoval({ deckEmpties });
      });
  } else {
    finishDeckAfterRemoval({ deckEmpties });
  }
}

/**
 * Post-removal deck bookkeeping: on the deck-empties path run the empty-state +
 * mode-exit; otherwise recompute the tag-chip numerators (the "X" of "X / Y")
 * unconditionally — updateTagFilteringOnURLOrURLTagDeletion only refreshes them
 * when a tag is selected, so a no-filter bulk delete would leave stale chips.
 */
function finishDeckAfterRemoval({
  deckEmpties,
}: {
  deckEmpties: boolean;
}): void {
  if (deckEmpties || $("#listURLs .urlRow").length === 0) {
    showURLsEmptyState();
    hideURLSearchIcon();
    exitMultiSelectMode();
    return;
  }
  updateVisibleURLsForTagCount();
  updateTagFilteringOnURLOrURLTagDeletion();
}

/**
 * Write the server-reported UTub-wide applied count (denominator) onto each
 * affected tag-filter chip. Mirrors bulk-tag's "write only the denominator half
 * from server data" — the numerator is recomputed in a single later pass.
 */
function applyTagCountsInUtub(tagCountsInUtub: Record<string, number>): void {
  for (const [tagID, count] of Object.entries(tagCountsInUtub)) {
    writeTagChipDenominator({ tagId: tagID, count });
  }
}

// --- Failure ------------------------------------------------------------------

function handleDeleteFail({
  xhr,
  sourceUTubID,
}: {
  xhr: JQuery.jqXHR;
  sourceUTubID: number;
}): void {
  if (is429Handled(xhr)) return;
  // bulk-delete's service DOES call reject_if_utub_locked (unlike bulk-copy), so
  // the locked-UTub 403 must be delegated here — isUtubLockedHandled hides the
  // confirm modal and shows the inline deck banner instead of redirecting away.
  if (isUtubLockedHandled(xhr)) return;

  if (!("responseJSON" in xhr)) {
    if (
      xhr.status === 403 &&
      xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      // CSRF token expired → the server returned the login/forbidden HTML page.
      $("body").html(xhr.responseText);
      return;
    }
    window.location.assign(APP_CONFIG.routes.errorPage);
    return;
  }

  switch (xhr.status) {
    case 400: {
      // A message-level 400 is a stale/foreign selection (URLS_NOT_IN_UTUB) or a
      // list-validation failure (empty / over-cap). Surface the concise fail
      // banner and close the modal so the user re-selects. Bail if the active
      // UTub changed mid-flight (the banner targets a deck no longer showing).
      if (getState().activeUTubID !== sourceUTubID) return;
      renderDeleteResultBanner({
        deletedCount: 0,
        skippedCount: 0,
        forceFail: true,
      });
      teardownConfirm({ returnFocus: true });
      break;
    }
    case 403:
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}

// --- Result banner (concise COUNT ONLY — never a URL title) --------------------

/** "Deleted N URLs." / "Deleted 1 URL." */
function deletedOutcomeText(deletedCount: number): string {
  return deletedCount === 1
    ? APP_CONFIG.strings.URL_BULK_DELETED_ONE
    : APP_CONFIG.strings.URL_BULK_DELETED.replace("{n}", String(deletedCount));
}

/** "N skipped because you can't delete them." / singular. */
function skippedSuffixText(skippedCount: number): string {
  return skippedCount === 1
    ? APP_CONFIG.strings.URL_BULK_DELETE_SKIPPED_SUFFIX_ONE
    : APP_CONFIG.strings.URL_BULK_DELETE_SKIPPED_SUFFIX.replace(
        "{n}",
        String(skippedCount),
      );
}

/**
 * Render the count-only result banner in #bulkDeleteResultBanner (reusing the
 * shared .bulkTagBanner styling). States:
 *   - forceFail (400)                          → fail/assertive   UNABLE_TO_DELETE_URLS
 *   - nothing deleted (all skipped)            → fail/assertive   URL_BULK_DELETE_NONE
 *   - some deleted, some skipped               → partial/assertive
 *   - all deleted cleanly                      → success/polite
 * XSS-safe: `.text()` escapes everything; no URL title is ever interpolated.
 */
function renderDeleteResultBanner({
  deletedCount,
  skippedCount,
  forceFail = false,
}: {
  deletedCount: number;
  skippedCount: number;
  forceFail?: boolean;
}): void {
  const banner = $(BANNER_SELECTOR);
  banner.empty().removeClass("hidden success partial fail");

  let variant: string;
  let glyph: string;
  let ariaLive: string;
  let text: string;

  if (forceFail) {
    variant = "fail";
    glyph = "🚫";
    ariaLive = "assertive";
    text = APP_CONFIG.strings.UNABLE_TO_DELETE_URLS;
  } else if (deletedCount === 0) {
    // Nothing deleted — every selected URL was skipped as non-deletable.
    variant = "fail";
    glyph = "🚫";
    ariaLive = "assertive";
    text = APP_CONFIG.strings.URL_BULK_DELETE_NONE;
  } else if (skippedCount > 0) {
    // Some deleted, some skipped → assertive partial (something was skipped).
    variant = "partial";
    glyph = "⚠️";
    ariaLive = "assertive";
    text = `${deletedOutcomeText(deletedCount)} ${skippedSuffixText(skippedCount)}`;
  } else {
    // Every deletable URL was deleted, nothing skipped.
    variant = "success";
    glyph = "✅";
    ariaLive = "polite";
    text = deletedOutcomeText(deletedCount);
  }

  // `.text()` escapes the whole string.
  const icon = $(document.createElement("span"))
    .addClass("bulkTagBannerIcon")
    .attr({ "aria-hidden": "true" })
    .text(glyph);
  const body = $(document.createElement("div"))
    .addClass("bulkTagBannerBody")
    .text(text);

  banner
    .addClass(variant)
    .attr("aria-live", ariaLive)
    .append(icon)
    .append(body);
}
