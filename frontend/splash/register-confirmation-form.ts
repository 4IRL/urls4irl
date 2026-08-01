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
 * dedicated unauthenticated /resend-registration-email endpoint. On click the
 * link shows an in-flight "Sending…" state; on settle it restores and shows a
 * DISTINCT "resent" success banner so the state change is perceptible. The
 * endpoint stays enumeration-neutral (200 for existent AND non-existent
 * emails), so a distinct error banner appears only on a genuine transport/HTTP
 * error — never on account existence. Must be called once from initSplash().
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

// Stash the link's original text once (before the first in-flight mutation) so
// resetResendLink can restore it regardless of what Jinja rendered.
function stashOriginalLinkText($link: JQuery): void {
  if ($link.data("originalText") === undefined) {
    $link.data("originalText", $link.text());
  }
}

function resetResendLink($modal: JQuery): void {
  const $link: JQuery = $modal.find("#ResendRegistrationEmail");
  const originalText: unknown = $link.data("originalText");
  if (originalText !== undefined) {
    $link.text(String(originalText));
  }
  $link
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
  stashOriginalLinkText($link);
  $link
    .addClass("disabled")
    .attr("aria-disabled", "true")
    .attr("aria-busy", "true")
    .text(APP_CONFIG.strings.REGISTRATION_EMAIL_RESEND_SENDING);

  const email: string = String($modal.data("registerEmail") ?? "");

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

  resendRequest.done(() => {
    resetResendLink($modal);
    // Distinct "resent" copy (differs from the open-modal confirmation text) so
    // the success is perceptible. The endpoint is opaque, so this same neutral
    // message is shown for existent and non-existent emails alike.
    showSplashModalAlertBanner(
      $modal,
      APP_CONFIG.strings.REGISTRATION_EMAIL_RESENT,
      "success",
    );
  });

  resendRequest.fail((xhr: JQuery.jqXHR) => {
    // The resend endpoint is rate-limited, so a 429 lands here. The global
    // $.ajaxPrefilter already owns that case (emits the metric and replaces
    // the page on an HTML 429); bail before touching this now-stale DOM.
    if (is429Handled(xhr)) return;

    resetResendLink($modal);

    if (xhr.status === 0) {
      // Genuine network/timeout blip: no HTTP response was received. Show the
      // same distinct "resent" success copy so the UX stays uniform and
      // enumeration-neutral (never reveals send outcome).
      showSplashModalAlertBanner(
        $modal,
        APP_CONFIG.strings.REGISTRATION_EMAIL_RESENT,
        "success",
      );
      return;
    }

    // A real HTTP error reached us (e.g. 400 stale CSRF, 500) — a genuine
    // transport/server failure, independent of account existence. Surface an
    // error state instead of masquerading the failure as success.
    showSplashModalAlertBanner(
      $modal,
      APP_CONFIG.strings.REGISTRATION_EMAIL_RESEND_ERROR,
      "danger",
    );
  });
}
