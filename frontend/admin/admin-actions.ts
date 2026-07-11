/**
 * Shared admin mutation-action controller.
 *
 * Every admin mutation button carries `data-admin-action` plus a small
 * `data-*` contract (URLs and copy come from Jinja via url_for — never
 * hardcoded here). Clicking a button opens the shared #confirmModal,
 * optionally collects a reason, and POSTs to the action URL via ajaxCall.
 * Success copy renders inline directly beneath the button that triggered the
 * action (or the page reloads when `data-reload-on-success` is set) so the
 * confirmation is visible right where the admin tapped — no scrolling back to
 * a shared region. Failures surface in the modal alert banner.
 *
 * data-* contract on each action button:
 *   data-admin-action        unique action key (used for event namespacing)
 *   data-action-url          POST endpoint (required)
 *   data-confirm-title       modal title (required)
 *   data-confirm-body        modal body text (required)
 *   data-submit-text         submit button label (default: bridged "Confirm")
 *   data-reason-required     "true" to require a non-empty reason
 *                            (reason is always POSTed; empty string when blank)
 *   data-reload-on-success   "true" to reload the page after a 200
 *   data-timeout-ms          AJAX timeout override (default 30000)
 */

import { $ } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import { ajaxCall, is429Handled } from "../lib/ajax.js";

const ACTION_SELECTOR = "[data-admin-action]";
const CLICK_NAMESPACE = "click.adminActions";
const HIDDEN_NAMESPACE = "hidden.bs.modal.adminActions";
const REASON_WRAPPER_ID = "AdminActionReasonWrapper";
const REASON_INPUT_ID = "AdminActionReasonInput";
const INLINE_RESULT_CLASS = "admin-action-inline-result";
const DEFAULT_TIMEOUT_MS = 30000;

interface AdminActionConfig {
  actionUrl: string;
  confirmTitle: string;
  confirmBody: string;
  submitText: string;
  reasonRequired: boolean;
  reloadOnSuccess: boolean;
  timeoutMs: number;
}

interface AdminActionResponse {
  status?: string;
  message?: string;
}

/**
 * Wire up the shared admin-action confirm flow. Uses a delegated document
 * listener so buttons inside server-swapped fragments are covered without
 * rebinding. Returns immediately when the shared modal is absent.
 */
export function initAdminActions(): void {
  if (document.getElementById("confirmModal") === null) return;

  $(document)
    .off(CLICK_NAMESPACE, ACTION_SELECTOR)
    .on(CLICK_NAMESPACE, ACTION_SELECTOR, function (event: JQuery.ClickEvent) {
      event.preventDefault();
      const triggerEl = event.currentTarget as HTMLElement;
      const actionConfig = readActionConfig(triggerEl);
      if (actionConfig === null) return;
      openConfirmModal({ actionConfig, triggerEl });
    });
}

function readActionConfig(buttonEl: HTMLElement): AdminActionConfig | null {
  const { actionUrl, confirmTitle, confirmBody } = buttonEl.dataset;
  if (!actionUrl || !confirmTitle || !confirmBody) return null;

  const parsedTimeout = parseInt(buttonEl.dataset.timeoutMs ?? "", 10);
  return {
    actionUrl,
    confirmTitle,
    confirmBody,
    submitText:
      buttonEl.dataset.submitText ??
      APP_CONFIG.strings.ADMIN_ACTION_SUBMIT_DEFAULT,
    reasonRequired: buttonEl.dataset.reasonRequired === "true",
    reloadOnSuccess: buttonEl.dataset.reloadOnSuccess === "true",
    timeoutMs: Number.isNaN(parsedTimeout) ? DEFAULT_TIMEOUT_MS : parsedTimeout,
  };
}

function openConfirmModal({
  actionConfig,
  triggerEl,
}: {
  actionConfig: AdminActionConfig;
  triggerEl: HTMLElement;
}): void {
  hideModalAlert();
  $("#confirmModalTitle").text(actionConfig.confirmTitle);

  const modalBody = $("#confirmModalBody");
  modalBody.text(actionConfig.confirmBody);
  appendReasonField({ modalBody, reasonRequired: actionConfig.reasonRequired });

  $("#modalDismiss")
    .removeClass()
    .addClass("btn btn-secondary")
    .text(APP_CONFIG.strings.ADMIN_ACTION_DISMISS)
    .offAndOn("click", function (event: JQuery.TriggeredEvent) {
      event.preventDefault();
      $("#confirmModal").modal("hide");
    });

  $("#modalRedirect").hide();

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-danger")
    .text(actionConfig.submitText)
    .prop("disabled", false)
    .offAndOn("click", function (event: JQuery.TriggeredEvent) {
      event.preventDefault();
      submitAdminAction({ actionConfig, triggerEl });
    });

  $("#confirmModal").offAndOnExact(HIDDEN_NAMESPACE, function () {
    removeReasonField();
    hideModalAlert();
  });

  $("#confirmModal").modal("show");
}

function appendReasonField({
  modalBody,
  reasonRequired,
}: {
  modalBody: JQuery;
  reasonRequired: boolean;
}): void {
  removeReasonField();
  const reasonWrapper = $("<div>", {
    id: REASON_WRAPPER_ID,
    class: "admin-action-reason mt-3",
  });
  const reasonLabel = $("<label>", {
    for: REASON_INPUT_ID,
    class: "form-label",
    text: APP_CONFIG.strings.ADMIN_ACTION_REASON_LABEL,
  });
  const reasonInput = $("<input>", {
    type: "text",
    id: REASON_INPUT_ID,
    class: "form-control",
    maxlength: 500,
  });
  if (reasonRequired) reasonInput.attr("required", "required");
  reasonWrapper.append(reasonLabel, reasonInput);
  modalBody.append(reasonWrapper);
}

function removeReasonField(): void {
  $(`#${REASON_WRAPPER_ID}`).remove();
}

function submitAdminAction({
  actionConfig,
  triggerEl,
}: {
  actionConfig: AdminActionConfig;
  triggerEl: HTMLElement;
}): void {
  const reasonValue = String($(`#${REASON_INPUT_ID}`).val() ?? "").trim();
  if (actionConfig.reasonRequired && reasonValue === "") {
    showModalAlert(APP_CONFIG.strings.ADMIN_ACTION_REASON_REQUIRED);
    return;
  }

  hideModalAlert();
  $("#modalSubmit").prop("disabled", true);

  // Always include the reason key — ajaxCall omits the body entirely for an
  // empty object, and api_route rejects body-less JSON POSTs with a 400.
  const payload: Record<string, unknown> = { reason: reasonValue };
  const request = ajaxCall(
    "post",
    actionConfig.actionUrl,
    payload,
    actionConfig.timeoutMs,
  );

  request.done(function (
    response: AdminActionResponse,
    _textStatus: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    if (xhr.status !== 200) return;
    $("#confirmModal").modal("hide");
    if (actionConfig.reloadOnSuccess) {
      window.location.reload();
      return;
    }
    renderActionResult({
      message:
        response?.message ?? APP_CONFIG.strings.ADMIN_ACTION_SUCCESS_DEFAULT,
      isError: false,
      triggerEl,
    });
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    $("#modalSubmit").prop("disabled", false);
    if (is429Handled(xhr)) return;
    showModalAlert(extractErrorMessage(xhr));
  });
}

function extractErrorMessage(xhr: JQuery.jqXHR): string {
  const responseJson = xhr.responseJSON as AdminActionResponse | undefined;
  if (responseJson?.message) return responseJson.message;
  return APP_CONFIG.strings.ADMIN_ACTION_GENERIC_ERROR;
}

function renderActionResult({
  message,
  isError,
  triggerEl,
}: {
  message: string;
  isError: boolean;
  triggerEl: HTMLElement;
}): void {
  const inlineResult = ensureInlineResult(triggerEl);
  if (inlineResult === null) return;
  inlineResult
    .removeClass()
    .addClass(`${INLINE_RESULT_CLASS} ${isError ? "is-error" : "is-success"}`)
    .text(message)
    .show();
  inlineResult[0]?.scrollIntoView({ block: "nearest" });
}

/**
 * Return the inline result element that sits immediately after the triggering
 * button, creating it on first use. Rendering the result as the button's next
 * sibling keeps the confirmation right where the admin acted — inside the ops
 * card on the health page, or directly below the account-action button on the
 * user-detail page.
 */
function ensureInlineResult(triggerEl: HTMLElement): JQuery | null {
  const triggerButton = $(triggerEl);
  if (triggerButton.length === 0) return null;
  let inlineResult = triggerButton.next(`.${INLINE_RESULT_CLASS}`);
  if (inlineResult.length === 0) {
    inlineResult = $("<div>", {
      class: `${INLINE_RESULT_CLASS} hidden`,
      "aria-live": "polite",
    });
    triggerButton.after(inlineResult);
  }
  return inlineResult;
}

function showModalAlert(message: string): void {
  $("#HomeModalAlertBanner").removeClass("hidden").text(message);
}

function hideModalAlert(): void {
  $("#HomeModalAlertBanner").addClass("hidden").text("");
}
