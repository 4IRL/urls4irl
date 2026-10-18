import type { SuccessResponse } from "../../../types/api-helpers.d.ts";
import type { UtubUrlItem } from "../../../types/url.js";

import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import {
  BULK_FOCUS_RETURN_SELECTOR,
  BULK_REQUEST_TIMEOUT_MS,
} from "../../../lib/constants.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { debug } from "../../../lib/debug.js";
import { AppEvents, emit as emitAppEvent } from "../../../lib/event-bus.js";
import { fillTemplate } from "../../../lib/string-template.js";
import { disposeTooltipsWithin } from "../../../lib/tooltips.js";
import { getState, setState } from "../../../store/app-store.js";
import { refreshTrashCount } from "../../trash/count.js";
import { isUtubLockedHandled } from "../../utub-locked.js";
import {
  showURLDeletedToast,
  showURLDeletionFailedToast,
} from "../cards/delete-undo.js";
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
import { isAnyBulkPickerOpen } from "./picker-guard.js";

const log = debug("urls:cards");

type DeleteUrlsResponse = SuccessResponse<"deleteUrlsFromUtub">;

// Deck-level live region (subheader) — survives exitMultiSelectMode()'s bulk-bar
// teardown, so the deck-empties outcome is announced there.
const OUTCOME_ANNOUNCEMENT_SELECTOR = "#URLDeckOutcomeAnnouncement";
const DELETE_BUTTON_SELECTOR = '[data-bulk-action-id="bulk-delete"]';

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

let submitInFlight = false;

// Read-only view of the flag for the refresh-on-focus busy gate.
export function isBulkDeleteSubmitInFlight(): boolean {
  return submitInFlight;
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
  // Rendered whenever there's a selection (same gate as Add tags / Copy) so the
  // destructive action stays a discoverable affordance. Whether it's ENABLED is a
  // separate capability check: only when ≥1 selected URL is deletable by this user
  // (server re-checks each id as the source of truth — partial-skip). When nothing
  // deletable is selected the bar shows Delete DISABLED with disabledReason rather
  // than hiding it, so a member never wonders where "Delete" went.
  isAvailable: (context: BulkActionContext) =>
    context.selectedURLCardIDs.length > 0,
  isEnabled: hasDeletableSelection,
  disabledReason: APP_CONFIG.strings.URL_BULK_DELETE_DISABLED_REASON,
  onActivate: activateBulkDelete,
};

// The action registry is append-only, so guard against a repeat initBulkActions().
let _bulkDeleteInitialized = false;

/**
 * Register the bulk-delete action. Called from initBulkActions(); the import
 * itself is what makes registration run.
 */
export function initBulkDelete(): void {
  if (_bulkDeleteInitialized) return;
  _bulkDeleteInitialized = true;

  registerBulkAction(bulkDeleteAction);
}

// --- Activate -----------------------------------------------------------------

/**
 * Snapshot the current selection + its deletable/non-deletable partition and
 * delete immediately (no confirm; the result toast offers Undo). Re-entrant /
 * cross-picker activation is a defined no-op. Everything the submit acts on is
 * captured HERE, never a fresh store read.
 */
function activateBulkDelete(context: BulkActionContext): void {
  // Re-entrant / cross-picker guard first (mirrors openBulkCopyPicker /
  // openBulkTagPicker) so a delete cannot fire over an already-open picker.
  if (isAnyBulkPickerOpen()) return;

  const activeUTubID = getState().activeUTubID;
  if (activeUTubID === null) return;

  const selectedSnapshot = [...context.selectedURLCardIDs];
  if (selectedSnapshot.length === 0) return;

  // Partition the SELECTION by canDelete. Only deletable ids are sent; the
  // non-deletable ids stay in the deck as skipped survivors (amber cue).
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
  // Defensive: isAvailable already gates on ≥1 deletable, but never send an
  // empty delete.
  if (deletableSnapshot.length === 0) return;

  const hiddenCount = hiddenSelectedCount(selectedSnapshot);

  log("activate bulk delete", {
    activeUTubID,
    totalSelected: selectedSnapshot.length,
    deletable: deletableSnapshot.length,
    skipped: skippedSnapshot.length,
    hiddenCount,
  });

  submitDelete({ deletableSnapshot, skippedSnapshot, hiddenCount });
}

// --- Submit -------------------------------------------------------------------

/**
 * Post the deletable snapshot to the active UTub, then act on the captured
 * snapshot in the response handlers (never a fresh store re-read).
 */
function submitDelete({
  deletableSnapshot,
  skippedSnapshot,
  hiddenCount,
}: {
  deletableSnapshot: number[];
  skippedSnapshot: number[];
  hiddenCount: number;
}): void {
  if (submitInFlight) return;
  const sourceUTubID = getState().activeUTubID;
  if (sourceUTubID === null) return;

  submitInFlight = true;
  // Hold the exact button: a successful delete rebuilds the bar (fresh, correctly
  // enabled/disabled button), so only restore this one if it is still attached.
  const deleteButton = $(DELETE_BUTTON_SELECTOR);
  deleteButton.attr("aria-disabled", "true");

  log("submit bulk delete", { sourceUTubID, deletableSnapshot });

  const request = ajaxCall(
    "post",
    APP_CONFIG.routes.bulkDeleteURLs(sourceUTubID),
    { utubUrlIds: deletableSnapshot },
    BULK_REQUEST_TIMEOUT_MS,
  );

  request.done(function (
    response: DeleteUrlsResponse,
    _: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    if (xhr.status !== 200) return;
    // Bail if the active UTub changed while the request was in flight — the
    // toast + deck mutation target a deck that is no longer showing.
    if (getState().activeUTubID !== sourceUTubID) return;
    handleDeleteSuccess({
      response,
      skippedSnapshot,
      hiddenCount,
      utubID: sourceUTubID,
    });
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    handleDeleteFail({ xhr, sourceUTubID });
  });

  request.always(function () {
    submitInFlight = false;
    deleteButton
      .filter((_, element) => document.contains(element))
      .removeAttr("aria-disabled");
  });
}

// --- Success (active-deck mutation) -------------------------------------------

/** "Moved N URLs to Trash." / "Moved 1 URL to Trash." (live-region text). */
function movedToTrashText(count: number): string {
  return count === 1
    ? APP_CONFIG.strings.URL_MOVED_TO_TRASH_ONE
    : fillTemplate({
        template: APP_CONFIG.strings.URL_MOVED_TO_TRASH,
        values: { n: String(count) },
      });
}

function handleDeleteSuccess({
  response,
  skippedSnapshot,
  hiddenCount,
  utubID,
}: {
  response: DeleteUrlsResponse;
  skippedSnapshot: number[];
  hiddenCount: number;
  utubID: number;
}): void {
  // Act on the SERVER-reported deleted ids (the source of truth), kept a
  // number[] throughout to match pruneRemovedFromSelection's signature.
  const deletedIds: number[] = response.deleted.map((entry) => entry.utubUrlID);
  const deletedCount = deletedIds.length;
  // Skipped survivors = the client-side non-deletable partition UNION any ids the
  // server itself reported skipped (permission drift between deck load and
  // submit — the server is the source of truth). Deduped; both stay in the deck.
  const skippedIds = [
    ...new Set([
      ...skippedSnapshot,
      ...response.skipped.map((entry) => entry.utubUrlID),
    ]),
  ];
  const skippedCount = skippedIds.length;

  log("bulk delete success", { deletedCount, skippedCount });
  if (deletedCount > 0) void refreshTrashCount();

  // Store patch: drop the deleted URLs, then prune them from the selection
  // (pruneRemovedFromSelection emits URL_MULTISELECT_CHANGED via commitSelection).
  setState({
    urls: getState().urls.filter(
      (url: UtubUrlItem) => !deletedIds.includes(url.utubUrlID),
    ),
  });
  // Notify the onboarding nudge system (and any future url-deck consumer) that
  // the deck's URL set changed, so it can re-arm/re-show the Add-URL tip.
  emitAppEvent(AppEvents.URL_DECK_CHANGED);
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
    // mode-exit path clears the bulk bar.
    $(OUTCOME_ANNOUNCEMENT_SELECTOR).text(movedToTrashText(deletedCount));
  }

  // The toast lives outside the bulk bar, so it survives mode exit.
  if (deletedCount === 0) {
    showURLDeletionFailedToast({ forceFail: false });
  } else {
    showURLDeletedToast({
      utubID,
      deletedIDs: deletedIds,
      skippedCount,
      hiddenCount,
      returnFocusTo: $(BULK_FOCUS_RETURN_SELECTOR),
    });
  }

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
        // A bulk delete drops many cards at once, so the per-card/per-badge
        // tooltip leak scales with the selection — dispose before detaching.
        disposeTooltipsWithin(deletedRows);
        deletedRows.remove();
        finishDeckAfterRemoval({ deckEmpties });
      });
  } else {
    finishDeckAfterRemoval({ deckEmpties });
  }
}

/**
 * Post-removal deck bookkeeping: on the deck-empties path run the empty-state +
 * mode-exit (which owns focus); otherwise recompute the tag-chip numerators (the
 * "X" of "X / Y") unconditionally — updateTagFilteringOnURLOrURLTagDeletion only
 * refreshes them when a tag is selected, so a no-filter bulk delete would leave
 * stale chips — and return focus to the stable Exit control.
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
  const exitAnchor = $(BULK_FOCUS_RETURN_SELECTOR);
  if (exitAnchor.length > 0) exitAnchor[0]?.focus();
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
  // the locked-UTub 403 must be delegated here — isUtubLockedHandled shows the
  // inline deck banner instead of redirecting away.
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
      // toast so the user re-selects. Bail if the active UTub changed mid-flight
      // (the toast targets a deck no longer showing).
      if (getState().activeUTubID !== sourceUTubID) return;
      showURLDeletionFailedToast({ forceFail: true });
      break;
    }
    case 403:
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}
