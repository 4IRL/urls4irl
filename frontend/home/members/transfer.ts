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
import { closeTransferPicker } from "./transfer-picker.js";

const log = debug("members");

export type OwnershipTransferredResponse =
  SuccessResponse<"transferUtubOwnership">;

// Ownership hand-off confirm-and-commit core. Mirrors role.ts's confirm-modal +
// AJAX shape, targeting PATCH /utubs/<id>/owner with { new_owner_id }. A transfer
// flips owner-gated flags across the whole app plus moves the owner/member badge,
// which no in-place diff helper expresses, so the success path re-runs the full
// UTub-select build + left-deck summary refetch rather than a local patch.

// "Was submit clicked" — used only to suppress the cancel metric after a real
// confirm-click (mirrors delete.ts:32); never drives focus.
let _transferConfirmed: boolean = false;
// "The PATCH actually succeeded" (DD-12) — the accurate signal the deferred
// hidden.bs.modal handler branches on for the focus-to-#MemberDeckHeader move.
let _transferSucceeded: boolean = false;
// The element/selector focus returns to if the modal is dismissed without
// confirming (DD-15).
let _transferOpener: HTMLElement | string | null = null;

// Show the confirm modal for transferring ownership to the chosen member. The
// picker (Step 3) supplies the target at runtime; called directly with a fixed
// target in tests.
export function transferOwnershipShowModal({
  newOwnerId,
  newOwnerUsername,
  utubID,
  opener,
}: {
  newOwnerId: number;
  newOwnerUsername: string;
  utubID: number;
  opener: HTMLElement | string;
}): void {
  _transferConfirmed = false;
  _transferSucceeded = false;
  _transferOpener = opener;

  emit({ event: UI_EVENTS.UI_UTUB_TRANSFER_OWNER_SHOWN });

  $("#confirmModalTitle").text(APP_CONFIG.strings.TRANSFER_OWNER_CONFIRM_TITLE);
  $("#confirmModalBody").text(
    APP_CONFIG.strings.TRANSFER_OWNER_CONFIRM_WARNING.replace(
      "{{ username }}",
      newOwnerUsername,
    ),
  );

  $("#modalDismiss")
    .removeClass()
    .addClass("btn btn-secondary")
    .offAndOn("click", function (event: JQuery.TriggeredEvent) {
      event.preventDefault();
      $("#confirmModal").modal("hide");
    })
    .text("Cancel");

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-success")
    .text(
      APP_CONFIG.strings.TRANSFER_OWNER_CONFIRM_SUBMIT.replace(
        "{{ username }}",
        newOwnerUsername,
      ),
    )
    .offAndOn("click", function (event: JQuery.TriggeredEvent) {
      event.preventDefault();
      _transferConfirmed = true;
      emit({ event: UI_EVENTS.UI_UTUB_TRANSFER_OWNER_CONFIRMED });
      transferOwnership({ newOwnerId, utubID });
    });

  $("#modalSubmit").prop("disabled", false);
  $("#confirmModal").modal("show");
  $("#modalRedirect").hide();

  // Deferred focus/cancel-metric handling (DD-12/DD-13/DD-14/DD-15). Bound via
  // offAndOnExact (re-bound cleanly on every reopen, never stacked) under the
  // distinct .transferOwner namespace so it can't clobber role.ts's/delete.ts's
  // own handlers on this shared modal.
  //
  // DD-14: this handler must act EXACTLY ONCE per transfer open — for this
  // flow's own close — and be inert for any later close of the shared
  // #confirmModal driven by an unrelated flow (role.ts/delete.ts). Resetting the
  // flags alone is insufficient: after a reset both flags are `false`, which
  // re-arms the `!_transferConfirmed` cancel branch and would emit a spurious
  // transfer-cancel (and steal focus to the stale opener) on the next unrelated
  // close. So after handling this flow's close, we both reset the flags AND
  // unbind our own namespace; the next transferOwnershipShowModal re-binds it.
  $("#confirmModal").offAndOnExact(
    "hidden.bs.modal.transferOwner",
    function () {
      if (_transferSucceeded) {
        $("#MemberDeckHeader").attr("tabindex", "-1").trigger("focus");
      } else if (!_transferConfirmed) {
        emit({ event: UI_EVENTS.UI_UTUB_TRANSFER_OWNER_CANCEL });
        // A union of string | HTMLElement matches no single jQuery `$()`
        // overload, so narrow before selecting (behavior identical — jQuery
        // accepts either a selector string or an element).
        if (typeof _transferOpener === "string") {
          $(_transferOpener).trigger("focus");
        } else if (_transferOpener) {
          $(_transferOpener).trigger("focus");
        }
      }
      _transferConfirmed = false;
      _transferSucceeded = false;
      $("#confirmModal").off("hidden.bs.modal.transferOwner");
    },
  );
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
  $("#modalSubmit").prop("disabled", true);

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
  // (1) Mark the PATCH as succeeded (DD-12) so the already-armed
  // hidden.bs.modal.transferOwner handler takes the focus-to-header branch once
  // the close transition completes. Then hide the modal + tear down the picker
  // (safe no-op if already closed).
  _transferSucceeded = true;
  $("#confirmModal").modal("hide");
  closeTransferPicker();

  const newOwnerUsername = response.newOwner.username;

  // (2) Sequenced full reconciliation (DD-13): resolve the select-rebuild FIRST
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
      // a stale deck + swallowing the rejection.
      window.location.assign(APP_CONFIG.routes.errorPage);
    }
    // buildUTubDeck's rebuild never sets .active on any row — re-add it.
    // Runs LAST, unconditionally (matches the prior chain's final .then).
    $(`.UTubSelector[utubid="${response.utubID}"]`).addClass("active");
    // Re-assert the Delete/Leave + owner affordances LAST, unconditionally.
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
  // …ShowModal); do NOT trigger focus here synchronously (DD-12/DD-13).
}

function transferOwnershipFail(xhr: JQuery.jqXHR): void {
  $("#modalSubmit").prop("disabled", false);
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
