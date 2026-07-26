import { $ } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import { is429Handled } from "../lib/ajax.js";
import { showSplashModalAlertBanner, switchModal } from "./init.js";
import { debug } from "../lib/debug.js";

const log = debug("splash:register");

/**
 * Initialize the post-register confirmation modal.
 *
 * Wires the "Back to login" button and the opaque "Resend" link. The resend
 * link POSTs the submitted email (stashed by handleRegisterSuccess) to the
 * dedicated unauthenticated /resend-registration-email endpoint, which always
 * returns an identical opaque success — so the banner is re-shown regardless of
 * outcome. Must be called once from initSplash().
 */
export function initRegisterConfirmationModal($modal: JQuery): void {
  $modal
    .find("#BackToLoginFromConfirmation")
    .offAndOn("click", () => switchModal($modal, "#LoginModal"));

  $modal
    .find("#ResendRegistrationEmail")
    .offAndOn("click", (event) => handleResendRegistrationEmail(event, $modal));

  // Clear any lingering disabled/busy state from a prior resend on every
  // (re-)open. Uses show.bs.modal (state reset, fires BEFORE visible),
  // deliberately distinct from handleRegisterSuccess's shown.bs.modal announce.
  $modal.on("show.bs.modal", () => resetResendLink($modal));

  log("initRegisterConfirmationModal bound");
}

function resetResendLink($modal: JQuery): void {
  $modal
    .find("#ResendRegistrationEmail")
    .removeClass("disabled")
    .removeAttr("aria-disabled")
    .removeAttr("aria-busy");
}

function handleResendRegistrationEmail(
  event: JQuery.TriggeredEvent,
  $modal: JQuery,
): void {
  // href="#" — prevent the browser jumping to a stray hash and keep the anchor
  // keyboard-accessible on Enter.
  event.preventDefault();

  const $link: JQuery = $modal.find("#ResendRegistrationEmail");
  $link
    .addClass("disabled")
    .attr("aria-disabled", "true")
    .attr("aria-busy", "true");

  const email: string = String($modal.data("registerEmail") ?? "");
  const confirmMessage: string = String($modal.data("confirmMessage") ?? "");

  log("resend registration email", { emailLength: email.length });

  const resendRequest: JQuery.jqXHR = $.ajax({
    url: APP_CONFIG.routes.resendRegistrationEmail,
    type: "POST",
    contentType: "application/json",
    data: JSON.stringify({ email }),
    // Raw $.ajax has no default timeout; this awaits a server-side email send,
    // so cap it at 10s so a slow-but-legitimate Mailjet round-trip doesn't
    // false-fail on the opaque endpoint.
    timeout: 10000,
  });

  resendRequest.done((response: { message: string }) => {
    resetResendLink($modal);
    // Opaque endpoint always returns 200 with the uniform confirmation message.
    showSplashModalAlertBanner($modal, response.message, "success");
  });

  resendRequest.fail((xhr: JQuery.jqXHR) => {
    // The resend endpoint is rate-limited, so a 429 lands here. The global
    // $.ajaxPrefilter already owns that case (emits the metric and replaces
    // the page on an HTML 429); bail before touching this now-stale DOM.
    if (is429Handled(xhr)) return;

    resetResendLink($modal);

    if (xhr.status === 0) {
      // Genuine network/timeout blip: no HTTP response was received. Re-show
      // the same opaque confirmation text stashed at open-time (no new bridged
      // string) so the enumeration-neutral UX is preserved.
      showSplashModalAlertBanner($modal, confirmMessage, "success");
      return;
    }

    // A real HTTP error reached us (e.g. 400 stale CSRF, 500). Surface an error
    // state instead of masquerading the failure as success.
    showSplashModalAlertBanner(
      $modal,
      "Unable to process request...",
      "danger",
    );
  });
}
