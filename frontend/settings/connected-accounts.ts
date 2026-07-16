/**
 * Connected-accounts (OAuth link/unlink) controller for the settings page.
 *
 * The rows are server-rendered by Jinja (`pages/settings.html`), so — like
 * `admin/admin-actions.ts` — this binds delegated handlers on `document`
 * keyed by a small `data-*` contract read off the clicked element, rather
 * than binding per-row at creation time (there is no TS render step for
 * these rows to close over).
 *
 * data-* contract (rendered by the template, read-only here):
 *   #SettingsConnectedAccounts[data-has-password]   "true" | "false"
 *   .ConnectedAccountLinkBtn[data-action-url]        POST target to link
 *   .ConnectedAccountUnlinkBtn[data-action-url]       DELETE target to unlink (may be disabled)
 */

import type { Schema, SuccessResponse } from "../types/api-helpers.d.ts";
import { $ } from "../lib/globals.js";
import { ajaxCall, is429Handled } from "../lib/ajax.js";

type ProviderLinkRequest = Schema<"ProviderLinkRequest">;
type LinkOauthResponse = SuccessResponse<"linkOauthProvider">;
type UnlinkOauthResponse = SuccessResponse<"unlinkOauthProvider">;
type OauthLinkError = Schema<"ErrorResponse_OAuthLinkErrorCodes">;

const CONTAINER_ID = "SettingsConnectedAccounts";
const BANNER_ID = "SettingsLinkStatusBanner";
const ROW_SELECTOR = ".ConnectedAccountRow";
const LINK_BTN_SELECTOR = ".ConnectedAccountLinkBtn";
const UNLINK_BTN_SELECTOR = ".ConnectedAccountUnlinkBtn";
const CONTINUE_BTN_SELECTOR = ".ConnectedAccountPasswordContinueBtn";
const CANCEL_BTN_SELECTOR = ".ConnectedAccountPasswordCancelBtn";
const PASSWORD_INPUT_SELECTOR = ".ConnectedAccountPasswordInput";
const CONFIRM_BLOCK_SELECTOR = ".ConnectedAccountPasswordConfirm";

const CLICK_NAMESPACE = "click.connectedAccounts";
const KEYUP_NAMESPACE = "keyup.connectedAccounts";

const GENERIC_ERROR_MESSAGE = "Unable to process request.";

export function initConnectedAccounts(): void {
  if (document.getElementById(CONTAINER_ID) === null) return;

  $(document)
    .off(CLICK_NAMESPACE, LINK_BTN_SELECTOR)
    .on(
      CLICK_NAMESPACE,
      LINK_BTN_SELECTOR,
      function (event: JQuery.ClickEvent) {
        event.preventDefault();
        handleLinkClick(event.currentTarget as HTMLElement);
      },
    );

  $(document)
    .off(CLICK_NAMESPACE, CONTINUE_BTN_SELECTOR)
    .on(
      CLICK_NAMESPACE,
      CONTINUE_BTN_SELECTOR,
      function (event: JQuery.ClickEvent) {
        event.preventDefault();
        handleContinueClick(event.currentTarget as HTMLElement);
      },
    );

  $(document)
    .off(CLICK_NAMESPACE, CANCEL_BTN_SELECTOR)
    .on(
      CLICK_NAMESPACE,
      CANCEL_BTN_SELECTOR,
      function (event: JQuery.ClickEvent) {
        event.preventDefault();
        handleCancelClick(event.currentTarget as HTMLElement);
      },
    );

  $(document)
    .off(CLICK_NAMESPACE, UNLINK_BTN_SELECTOR)
    .on(
      CLICK_NAMESPACE,
      UNLINK_BTN_SELECTOR,
      function (event: JQuery.ClickEvent) {
        event.preventDefault();
        handleUnlinkClick(event.currentTarget as HTMLElement);
      },
    );

  $(document)
    .off(KEYUP_NAMESPACE, PASSWORD_INPUT_SELECTOR)
    .on(
      KEYUP_NAMESPACE,
      PASSWORD_INPUT_SELECTOR,
      function (event: JQuery.KeyUpEvent) {
        if (event.key !== "Enter") return;
        const continueBtn = $(event.currentTarget)
          .closest(ROW_SELECTOR)
          .find(CONTINUE_BTN_SELECTOR)
          .get(0);
        if (continueBtn) handleContinueClick(continueBtn);
      },
    );
}

export function _resetConnectedAccountsForTests(): void {
  $(document).off(CLICK_NAMESPACE).off(KEYUP_NAMESPACE);
}

function handleLinkClick(buttonEl: HTMLElement): void {
  const actionUrl = buttonEl.dataset.actionUrl;
  if (!actionUrl) return;

  const container = document.getElementById(CONTAINER_ID);
  const hasPassword = container?.dataset.hasPassword === "true";

  if (!hasPassword) {
    // OAuth-only account: no password confirmation step, link immediately.
    // ajaxCall omits the request body entirely for an empty object, and
    // api_route rejects body-less JSON POSTs with a 400 — send the
    // ProviderLinkRequest shape explicitly (password: null) instead of {}.
    submitLink({ actionUrl, password: null });
    return;
  }

  const row = $(buttonEl).closest(ROW_SELECTOR);
  const confirmBlock = row.find(CONFIRM_BLOCK_SELECTOR);
  $(CONFIRM_BLOCK_SELECTOR).not(confirmBlock).addClass("d-none");
  confirmBlock.removeClass("d-none");
  row.find(PASSWORD_INPUT_SELECTOR).trigger("focus");
}

function handleContinueClick(buttonEl: HTMLElement): void {
  const row = $(buttonEl).closest(ROW_SELECTOR);
  const actionUrl = row.find(LINK_BTN_SELECTOR).attr("data-action-url");
  if (!actionUrl) return;

  const password = String(row.find(PASSWORD_INPUT_SELECTOR).val() ?? "");
  submitLink({ actionUrl, password });
}

function handleCancelClick(buttonEl: HTMLElement): void {
  const row = $(buttonEl).closest(ROW_SELECTOR);
  row.find(CONFIRM_BLOCK_SELECTOR).addClass("d-none");
  row.find(PASSWORD_INPUT_SELECTOR).val("");
}

function handleUnlinkClick(buttonEl: HTMLElement): void {
  if ((buttonEl as HTMLButtonElement).disabled) return;

  const actionUrl = buttonEl.dataset.actionUrl;
  if (!actionUrl) return;

  const request = ajaxCall("delete", actionUrl, null);

  request.done(function (
    _response: UnlinkOauthResponse,
    _textStatus: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    if (xhr.status !== 200) return;
    window.location.reload();
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    if (is429Handled(xhr)) return;
    showLinkStatusBanner({ message: extractErrorMessage(xhr), type: "danger" });
  });
}

function submitLink({
  actionUrl,
  password,
}: {
  actionUrl: string;
  password: string | null;
}): void {
  const payload: ProviderLinkRequest = { password };
  const request = ajaxCall("post", actionUrl, payload);

  request.done(function (
    response: LinkOauthResponse,
    _textStatus: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    if (xhr.status !== 200) return;
    window.location.assign(response.redirectUrl);
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    if (is429Handled(xhr)) return;
    showLinkStatusBanner({
      message: extractLinkErrorMessage(xhr),
      type: "danger",
    });
  });
}

function extractLinkErrorMessage(xhr: JQuery.jqXHR): string {
  const responseJson = xhr.responseJSON as OauthLinkError | undefined;
  const passwordErrors = responseJson?.errors?.password;
  if (passwordErrors && passwordErrors.length > 0) return passwordErrors[0];
  return responseJson?.message ?? GENERIC_ERROR_MESSAGE;
}

function extractErrorMessage(xhr: JQuery.jqXHR): string {
  const responseJson = xhr.responseJSON as { message?: string } | undefined;
  return responseJson?.message ?? GENERIC_ERROR_MESSAGE;
}

function showLinkStatusBanner({
  message,
  type,
}: {
  message: string;
  type: "success" | "danger";
}): void {
  $(`#${BANNER_ID}`)
    .removeClass("d-none alert-success alert-danger")
    .addClass(`alert-${type}`)
    .text(message);
}
