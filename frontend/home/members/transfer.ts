import type { SuccessResponse } from "../../types/api-helpers.d.ts";

import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { isUtubLockedHandled } from "../utub-locked.js";
import { emit } from "../../lib/metrics-client.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import { getState } from "../../store/app-store.js";
import { debug } from "../../lib/debug.js";
import { buildSelectedUTub, getUTubInfo } from "../utubs/selectors.js";
import { buildUTubDeck, setUTubDeckOnUTubSelected } from "../utubs/deck.js";
import { getAllUTubs } from "../utubs/utils.js";
import {
  CANCEL_BTN_SELECTOR,
  CONFIRM_VIEW_SELECTOR,
  FOOTER_MSG_SELECTOR,
  MODAL_SELECTOR,
  PICK_VIEW_SELECTOR,
  SUBMIT_BTN_SELECTOR,
  TITLE_SELECTOR,
} from "./transfer-selectors.js";

const log = debug("members");

export type OwnershipTransferredResponse =
  SuccessResponse<"transferUtubOwnership">;

// Ownership hand-off lifecycle + confirm view + commit core. The transfer now
// lives in a DEDICATED modal (#transferOwnerModal) with an inline pick→confirm
// transition: transfer-picker.ts renders the pick view + calls beginTransferFlow
// to open the modal; onContinue → showTransferConfirmView swaps the same modal to
// the confirm view; the confirm submit commits. Targets PATCH /utubs/<id>/owner
// with { new_owner_id }. A transfer flips owner-gated flags across the whole app
// plus moves the owner/member badge, which no in-place diff helper expresses, so
// the success path re-runs the full UTub-select build + left-deck summary refetch
// rather than a local patch.

// "Was the confirm submit clicked" — used only to suppress the cancel metric
// after a real confirm-click (mirrors delete.ts); never drives focus.
let _transferConfirmed: boolean = false;
// "The PATCH actually succeeded" — the accurate signal the deferred
// hidden.bs.modal handler branches on for the focus-to-#MemberDeckHeaderAndCaret
// move.
let _transferSucceeded: boolean = false;
// The element/selector focus returns to if the modal is dismissed without
// confirming (returns to the trigger that opened the flow).
let _transferOpener: HTMLElement | string | null = null;

/**
 * True when the element is present, rendered, and not `visibility: hidden`.
 * Both mechanisms are covered: `offsetParent === null` catches a `display: none`
 * element or ancestor (the repo's `.hidden` class), and the `visibility` read
 * catches a `.deck.collapsed .button-container` ancestor — CSS `visibility` is
 * an inherited property, so no ancestor walk is needed for that half. Mirrors
 * the pairing in nudges.ts's `isAnchorVisible()`. Duplicated (rather than
 * shared) across the few focus-restore call sites that need it, keeping these
 * modules decoupled.
 *
 * Element-based, not id-based: `_transferOpener` is typed `HTMLElement | string`,
 * so resolving it to an element first covers both shapes with one check and
 * avoids narrowing the selector contract to `#id` strings.
 * `instanceof HTMLElement` rather than a cast — `offsetParent` is `undefined`
 * (not `null`) on an SVGElement, which a cast would read as focusable.
 */
function isFocusable(element: Element | null): boolean {
  return (
    element instanceof HTMLElement &&
    element.offsetParent !== null &&
    getComputedStyle(element).visibility !== "hidden"
  );
}

/**
 * The deck-header disclosure button to fall back to when the opener itself is
 * not focusable. Derived from the opener's ancestor deck rather than hardcoded:
 * the transfer flow is opened from BOTH #memberBtnTransferOwner (Member deck)
 * and #utubBtnDelete (UTubs deck, the "transfer instead" redirect), so a fixed
 * #MemberDeckHeaderAndCaret would strand focus in the wrong deck for the second
 * opener. Falls back to the Member deck header only when the opener has no
 * `.deck` ancestor at all.
 */
function fallbackHeaderFor(openerElement: Element): string {
  const deckId = $(openerElement).closest(".deck").attr("id");
  return deckId ? `#${deckId}HeaderAndCaret` : "#MemberDeckHeaderAndCaret";
}

/**
 * Open the dedicated transfer modal (already rendered in its PICK view by
 * transfer-picker.ts). Resets the confirm/success flags, records the opener for
 * focus-return-on-cancel, emits the SHOWN metric, arms the single close handler,
 * and shows the modal. The modal is DEDICATED to this flow, so the close handler
 * is rebound cleanly on every open (offAndOn) with no shared-modal / self-off
 * complexity.
 */
export function beginTransferFlow(opener: HTMLElement | string): void {
  _transferConfirmed = false;
  _transferSucceeded = false;
  _transferOpener = opener;

  emit({ event: UI_EVENTS.UI_UTUB_TRANSFER_OWNER_SHOWN });

  // Close handler (fires for any dismissal path). Branches on the accurate
  // PATCH-succeeded signal — not the raw confirm-click flag — so a confirm that
  // then FAILED still restores focus to the opener rather than the deck header.
  $(MODAL_SELECTOR).offAndOn("hidden.bs.modal.transferOwner", function () {
    if (_transferSucceeded) {
      // The header BUTTON, not the #MemberDeckHeader span it wraps: the span is
      // a plain, non-interactive title, while the button is a real disclosure
      // control that is already in the tab order (so no tabindex is forced onto
      // it — that would pull it back OUT) and carries the focus ring.
      $("#MemberDeckHeaderAndCaret").trigger("focus");
    } else {
      // Any non-success dismissal — a plain cancel/Escape/backdrop OR a
      // confirmed-but-FAILED submit the user then backed out of — restores focus
      // to the opener. A union of string | HTMLElement matches no single jQuery
      // `$()` overload, so narrow with a safe cast (behavior identical — jQuery
      // accepts either a selector string or an element).
      // The opener can itself be unfocusable: both #memberBtnTransferOwner and
      // #utubBtnDelete sit in a deck's `.button-container`, which is
      // visibility:hidden while that deck is collapsed — focusing it there is a
      // silent no-op that drops focus to <body>. Fall back to that deck's own
      // header button, which is never hidden. Resolved to an element first so
      // the check covers an HTMLElement opener as well as a selector string.
      if (_transferOpener) {
        const openerElement =
          typeof _transferOpener === "string"
            ? document.querySelector(_transferOpener)
            : _transferOpener;
        if (openerElement !== null && !isFocusable(openerElement)) {
          $(fallbackHeaderFor(openerElement)).trigger("focus");
        } else {
          $(_transferOpener as string).trigger("focus");
        }
      }
      // Emit CANCEL only when no real confirm-click happened (mirrors delete.ts);
      // a confirmed-but-failed transfer already emitted CONFIRMED, not CANCEL.
      if (!_transferConfirmed) {
        emit({ event: UI_EVENTS.UI_UTUB_TRANSFER_OWNER_CANCEL });
      }
    }
    _transferConfirmed = false;
    _transferSucceeded = false;
  });

  // Cancel dismisses the modal in BOTH the pick and confirm views — bind it once
  // here (the modal is dedicated to this flow) rather than re-binding the same
  // handler on every view swap / picker open.
  $(CANCEL_BTN_SELECTOR)
    .text("Cancel")
    .offAndOn("click", function () {
      $(MODAL_SELECTOR).modal("hide");
    });

  $(MODAL_SELECTOR).modal("show");
}

/**
 * Swap the SAME modal from the pick view to the confirm view for the chosen
 * member: show the warning body, retitle, clear the pick hint, and rebind the
 * footer Cancel / Transfer buttons for the commit. The modal is NOT closed —
 * this is the inline pick→confirm transition.
 */
export function showTransferConfirmView({
  newOwnerId,
  newOwnerUsername,
  utubID,
}: {
  newOwnerId: number;
  newOwnerUsername: string;
  utubID: number;
}): void {
  $(PICK_VIEW_SELECTOR).addClass("hidden");
  $(CONFIRM_VIEW_SELECTOR)
    .removeClass("hidden")
    .text(
      APP_CONFIG.strings.TRANSFER_OWNER_CONFIRM_WARNING.replace(
        "{{ username }}",
        newOwnerUsername,
      ),
    );

  $(TITLE_SELECTOR).text(APP_CONFIG.strings.TRANSFER_OWNER_CONFIRM_TITLE);
  $(FOOTER_MSG_SELECTOR).text("");

  // Cancel is bound once in beginTransferFlow (dismisses in both views) — no
  // per-view re-bind needed here.

  $(SUBMIT_BTN_SELECTOR)
    .prop("disabled", false)
    .text(
      APP_CONFIG.strings.TRANSFER_OWNER_CONFIRM_SUBMIT.replace(
        "{{ username }}",
        newOwnerUsername,
      ),
    )
    .offAndOn("click", function () {
      _transferConfirmed = true;
      emit({ event: UI_EVENTS.UI_UTUB_TRANSFER_OWNER_CONFIRMED });
      transferOwnership({ newOwnerId, utubID });
    });
}

// Handle the PATCH request/response after confirmation. CSRF is auto-attached to
// PATCH globally (no per-call code).
export function transferOwnership({
  newOwnerId,
  utubID,
}: {
  newOwnerId: number;
  utubID: number;
}): void {
  // Double-submit guard (mirrors role/remove).
  $(SUBMIT_BTN_SELECTOR).prop("disabled", true);

  log("transferOwnership submitted", { newOwnerId, utubID });

  const request = ajaxCall(
    "patch",
    APP_CONFIG.routes.transferUtubOwnership(utubID),
    { new_owner_id: newOwnerId },
  );

  request.done(function (
    response: OwnershipTransferredResponse,
    _textStatus: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    if (xhr.status === 200) {
      transferOwnershipSuccess(response);
    }
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    transferOwnershipFail(xhr);
  });
}

function transferOwnershipSuccess(
  response: OwnershipTransferredResponse,
): void {
  // (1) Mark the PATCH as succeeded so the already-armed hidden.bs.modal
  // .transferOwner handler takes the focus-to-header branch once the close
  // transition completes. Then hide the modal (its own hidden.bs.modal
  // .transferPicker handler tears the picker state down — no explicit call needed).
  _transferSucceeded = true;
  $(MODAL_SELECTOR).modal("hide");

  const newOwnerUsername = response.newOwner.username;

  // (2) Sequenced full reconciliation: resolve the select-rebuild FIRST
  // (re-derives every owner-gated flag + moves the owner badge + re-emits
  // UTUB_SELECTED), then chain the left-deck summary refetch (the only source
  // that re-renders the demoted user's left-deck role icon — buildSelectedUTub
  // never touches AppState.utubs), then re-assert .active + the Delete/Leave
  // affordances LAST so buildUTubDeck's resetUTubDeck() can't win a race.
  void (async () => {
    try {
      const selectedUTub = await getUTubInfo(getState().activeUTubID!);
      if (selectedUTub) {
        buildSelectedUTub(selectedUTub);
        const utubData = await getAllUTubs();
        buildUTubDeck(utubData.utubs);
      }
    } catch {
      // A select-rebuild OR post-transfer summary refetch failure is equally
      // fatal to a coherent UI — redirect deterministically rather than leaving
      // a stale deck + swallowing the rejection. Return so the trailing success
      // re-render below does NOT run with now-stale owner state (isCurrentUserOwner
      // still true), which would flash the owner-only Delete affordance before the
      // error-page redirect completes.
      window.location.assign(APP_CONFIG.routes.errorPage);
      return;
    }
    // buildUTubDeck's rebuild never sets .active on any row — re-add it.
    // Runs LAST on the SUCCESS path only (the catch above returns early).
    $(`.UTubSelector[utubid="${response.utubID}"]`).addClass("active");
    // Re-assert the Delete/Leave + owner affordances LAST (success path only).
    setUTubDeckOnUTubSelected(response.utubID, getState().isCurrentUserOwner);
  })();

  // (3) Announce via the reused row-action live region. Resolve the new owner's
  // name from the response so it is correct even though the acting user's own
  // role changed.
  $("#MemberRowActionAnnouncement")
    .attr("aria-live", "polite")
    .text(
      APP_CONFIG.strings.TRANSFER_OWNER_SUCCESS.replace(
        "{{ username }}",
        newOwnerUsername,
      ),
    );

  // (4) Focus management is deferred to hidden.bs.modal.transferOwner (armed in
  // beginTransferFlow); do NOT trigger focus here synchronously.
}

function transferOwnershipFail(xhr: JQuery.jqXHR): void {
  $(SUBMIT_BTN_SELECTOR).prop("disabled", false);
  if (is429Handled(xhr)) return;
  if (isUtubLockedHandled(xhr)) return;

  if (
    xhr.status === 403 &&
    xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
  ) {
    // Invalid CSRF token — swap in the server-rendered body (mirrors role).
    $("body").html(xhr.responseText);
    return;
  }

  switch (xhr.status) {
    case 400:
    case 404:
      // Actionable server messages (TARGET_ALREADY_OWNER,
      // UNABLE_TO_TRANSFER_OWNERSHIP, MEMBER_NOT_IN_UTUB) — surface the text via
      // the row-action live region assertively, do NOT redirect.
      $("#MemberRowActionAnnouncement")
        .attr("aria-live", "assertive")
        .text(xhr.responseJSON?.message ?? "");
      break;
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}
