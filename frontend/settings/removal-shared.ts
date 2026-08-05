/**
 * Shared mechanics for the settings-page removal/session modals.
 *
 * The account-DELETE controller (`account-removal.ts`) and the
 * "Log out everywhere" controller (`logout-everywhere.ts`) each own their own
 * purpose-built modal binder and their own delegated-event namespace (DD-1), but
 * they share the common plumbing collected here: banner/field-error rendering,
 * in-flight marking, the `ajaxCall` submit wiring (`wireRemovalRequest`), and the
 * `hidden.bs.modal` cancel-emit + focus-return.
 *
 * The per-open state maps (`_triggerByModal` / `_confirmedByModal`) are the only
 * cross-controller state; they are keyed by each modal's distinct id, so the two
 * controllers never collide. Event namespaces are intentionally NOT centralized
 * here (DD-1) — each controller keeps its own locally-scoped namespace so a
 * namespace-wide `.off()` in one controller's reset can never strip the other's
 * handlers.
 */

import type { Schema } from "../types/api-helpers.d.ts";
import type { UIEventName } from "../types/metrics-events.js";
import { $ } from "../lib/globals.js";
import { is429Handled } from "../lib/ajax.js";
import { emit as recordUIEvent } from "../lib/metrics-client.js";

export type AccountRemovalResponse = Schema<"AccountRemovalResponseSchema">;
export type RemovalErrorResponse = Schema<"ErrorResponse">;

const GENERIC_ERROR_MESSAGE = "Unable to process request.";

// Per-open state, keyed by modal id: the trigger element to restore focus to on
// close, and whether this open cycle reached a confirm (so `hidden.bs.modal`
// knows to emit CANCEL only for an actual dismissal). Shared across both the
// delete and logout-everywhere controllers, keyed by their distinct modal ids.
export const _triggerByModal = new Map<string, HTMLElement>();
export const _confirmedByModal = new Map<string, boolean>();

export interface RemovalRequestBinding {
  request: JQuery.jqXHR;
  modalId: string;
  errorId: string;
  buttonEl: HTMLButtonElement;
  // Re-enable the modal's controls after a non-200 / failed attempt (gate
  // recompute for delete, unconditional for logout-everywhere).
  reenable: () => void;
  // Runs just before a successful navigation (e.g. clear the password field).
  beforeNavigate: () => void;
  // Render server field errors onto inputs; return true if any were shown.
  renderFieldErrors: (
    responseJson: RemovalErrorResponse | undefined,
  ) => boolean;
}

// Shared `ajaxCall` submit wiring: on a 200 navigate to the server redirect,
// otherwise settle the button and surface the error (field errors first, then
// the in-modal banner). `is429Handled` short-circuits an already-handled 429.
export function wireRemovalRequest({
  request,
  modalId,
  errorId,
  buttonEl,
  reenable,
  beforeNavigate,
  renderFieldErrors,
}: RemovalRequestBinding): void {
  request.done(function (
    response: AccountRemovalResponse,
    _textStatus: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    if (xhr.status !== 200) {
      settleAfterAttempt({ modalId, buttonEl, reenable });
      return;
    }
    beforeNavigate();
    // Splash after logout, or the provider redirect for the OAuth round-trip.
    window.location.assign(response.redirectUrl);
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    settleAfterAttempt({ modalId, buttonEl, reenable });
    if (is429Handled(xhr)) return;

    const responseJson = xhr.responseJSON as RemovalErrorResponse | undefined;
    if (renderFieldErrors(responseJson)) return;

    showBanner({
      errorId,
      message: responseJson?.message ?? GENERIC_ERROR_MESSAGE,
    });
  });
}

// Settle a modal after a non-200 / failed attempt: drop the in-flight marker,
// re-enable controls per the modal's policy, and clear the confirmed flag so a
// subsequent dismiss still emits CANCEL (the removal did not complete).
function settleAfterAttempt({
  modalId,
  buttonEl,
  reenable,
}: {
  modalId: string;
  buttonEl: HTMLButtonElement;
  reenable: () => void;
}): void {
  clearInFlight(buttonEl);
  reenable();
  _confirmedByModal.set(modalId, false);
}

export function emitCancelAndRestoreFocus({
  modalId,
  cancelEvent,
}: {
  modalId: string;
  cancelEvent: UIEventName;
}): void {
  if (!_confirmedByModal.get(modalId)) {
    recordUIEvent({ event: cancelEvent });
  }
  // Return focus to the trigger that opened the modal.
  const trigger = _triggerByModal.get(modalId);
  if (trigger) $(trigger).trigger("focus");
  _confirmedByModal.set(modalId, false);
}

// Mark a control in flight: disabled + aria-busy, so both the native guard and
// the gate's `isInFlight` check keep it from re-submitting.
export function markInFlight(buttonEl: HTMLButtonElement): void {
  $(buttonEl).attr("disabled", "disabled").attr("aria-busy", "true");
}

export function clearInFlight(buttonEl: HTMLButtonElement): void {
  $(buttonEl).removeAttr("aria-busy");
}

// A control is "in flight" while markInFlight has set aria-busy; the gate must
// not re-enable it until the request settles.
export function isInFlight(elementId: string): boolean {
  return (
    document.getElementById(elementId)?.getAttribute("aria-busy") === "true"
  );
}

export function setDisabled({
  elementId,
  disabled,
}: {
  elementId: string;
  disabled: boolean;
}): void {
  const element = document.getElementById(elementId);
  if (!element) return;
  if (disabled) $(element).attr("disabled", "disabled");
  else $(element).removeAttr("disabled");
}

export function showFieldError({
  inputId,
  message,
}: {
  inputId: string;
  message: string;
}): void {
  const input = $(`#${inputId}`);
  input.addClass("is-invalid");
  input.siblings(".invalid-feedback").remove();
  $("<div>", { class: "invalid-feedback" })
    .append($("<span>").text(message))
    .insertAfter(input);
}

export function showBanner({
  errorId,
  message,
}: {
  errorId: string;
  message: string;
}): void {
  $(`#${errorId}`).removeClass("d-none").text(message);
}

export function clearBanner(errorId: string): void {
  $(`#${errorId}`).addClass("d-none").text("");
}
