import { $ } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import { ajaxCall, is429Handled } from "../lib/ajax.js";
import { emit } from "../lib/metrics-client.js";
import { UI_EVENTS } from "../types/metrics-events.js";
import {
  hideSplashModalAlertBanner,
  resetModalFormState,
  showSplashModalAlertBanner,
  switchModal,
} from "./init.js";
import { debug } from "../lib/debug.js";

const log = debug("splash:confirm-email");

type ConfirmEmailMode = "inline" | "expired";

const RESEND_TIMEOUT_MS = 10000;
const EXPIRED_COOLDOWN_KEY = "expired";

interface CooldownRecord {
  key: string;
  endsAt: number;
}

// Survives modal close and "Back to login"; cleared only by a page reload.
let cooldownRecord: CooldownRecord | null = null;
let cooldownTimer: ReturnType<typeof setTimeout> | null = null;
let announceTimer: ReturnType<typeof setTimeout> | null = null;
// Incremented per modal open so a stale in-flight callback can never act on a
// later open, even one that reuses a byte-identical resend token.
let openCounter = 0;

/**
 * Initialize the "Confirm your email" modal. Binding uses offAndOn, so a
 * repeat init is idempotent. `inline` returns to #LoginModal on dismissal;
 * `expired` (step 3's shell, which has no login modal) reloads the splash page.
 */
export function initConfirmEmailForm(
  $modal: JQuery,
  { mode }: { mode: ConfirmEmailMode },
): void {
  const $resend: JQuery = $modal.find("#ResendConfirmationEmail");
  if ($resend.data("originalText") === undefined) {
    $resend.data("originalText", $resend.text());
  }
  $modal.data("mode", mode);

  $resend.offAndOn("click", (event) => handleResend({ event, $modal }));

  $modal.find("#BackToLoginFromConfirmEmail").offAndOn("click", () => {
    if (mode === "expired") {
      window.location.replace("/");
      return;
    }
    $modal.data("switching", true);
    switchModal($modal, "#LoginModal");
  });

  $modal.offAndOn("show.bs.modal", () => {
    if (mode === "inline") resetModalFormState($modal);
    applyCooldownState($modal);
  });

  $modal.offAndOn("shown.bs.modal", () => {
    const title: HTMLElement | null = document.getElementById(
      "ConfirmEmailModalLabel",
    );
    title?.focus();
  });

  $modal.offAndOn("hidden.bs.modal", () => handleHidden($modal));

  log("initConfirmEmailForm bound", { mode });
}

/**
 * Open the confirm modal from the login modal after an unconfirmed-account
 * 401. Keeps the typed username, clears the password.
 */
export function openConfirmEmailModal({
  resendToken,
  fromModal,
}: {
  resendToken: string;
  fromModal: JQuery;
}): void {
  const $modal: JQuery = $("#ConfirmEmailModal");
  const username: string = String(fromModal.find("#username").val() ?? "");
  fromModal.find("#password").val("");

  const key: string =
    $modal.data("mode") === "expired"
      ? EXPIRED_COOLDOWN_KEY
      : username.trim().toLowerCase();
  openCounter += 1;
  $modal.data("openNonce", openCounter);
  $modal.data("resendToken", resendToken);
  $modal.data("cooldownKey", key);

  log("openConfirmEmailModal", { hasToken: resendToken !== "" });
  switchModal(fromModal, "#ConfirmEmailModal");
}

function clearTimers(): void {
  if (cooldownTimer !== null) clearTimeout(cooldownTimer);
  if (announceTimer !== null) clearTimeout(announceTimer);
  cooldownTimer = null;
  announceTimer = null;
}

function setResendEnabled($modal: JQuery): void {
  const $resend: JQuery = $modal.find("#ResendConfirmationEmail");
  const originalText: unknown = $resend.data("originalText");
  if (originalText !== undefined) $resend.text(String(originalText));
  $resend.removeAttr("aria-disabled").removeAttr("aria-busy");
}

function setResendCooldown($modal: JQuery): void {
  $modal
    .find("#ResendConfirmationEmail")
    .attr("aria-disabled", "true")
    .removeAttr("aria-busy")
    .text(APP_CONFIG.strings.CONFIRM_EMAIL_RESEND_COOLDOWN);
}

// Render the resend button from the stored cooldown (same account key only)
// and restart the re-enable timer for whatever time remains.
function applyCooldownState($modal: JQuery): void {
  if (cooldownTimer !== null) clearTimeout(cooldownTimer);
  cooldownTimer = null;

  const key: unknown = $modal.data("cooldownKey");
  const remaining: number =
    cooldownRecord !== null && cooldownRecord.key === key
      ? cooldownRecord.endsAt - Date.now()
      : 0;

  if (remaining > 0) {
    setResendCooldown($modal);
    cooldownTimer = setTimeout(() => {
      cooldownTimer = null;
      setResendEnabled($modal);
    }, remaining);
  } else {
    setResendEnabled($modal);
  }
}

// Persistent visually-hidden live region: cleared then written on a later tick
// so identical consecutive text is re-announced.
function announce({
  $modal,
  text,
  isError,
}: {
  $modal: JQuery;
  text: string;
  isError: boolean;
}): void {
  const $status: JQuery = $modal.find("#ConfirmEmailStatus");
  if (announceTimer !== null) clearTimeout(announceTimer);
  $status.attr("role", isError ? "alert" : "status").text("");
  announceTimer = setTimeout(() => {
    announceTimer = null;
    $status.text(text);
  }, 0);
}

function handleResend({
  event,
  $modal,
}: {
  event: JQuery.TriggeredEvent;
  $modal: JQuery;
}): void {
  event.preventDefault();

  const $resend: JQuery = $modal.find("#ResendConfirmationEmail");
  if ($resend.attr("aria-disabled") === "true") return;

  const resendToken: string = String($modal.data("resendToken") ?? "");
  if (resendToken === "") return;

  emit({
    event: UI_EVENTS.UI_EMAIL_VALIDATION_SUBMIT,
    trigger: "manual_click",
  });

  $resend
    .attr("aria-disabled", "true")
    .attr("aria-busy", "true")
    .text(APP_CONFIG.strings.REGISTRATION_EMAIL_RESEND_SENDING);

  const openNonce: unknown = $modal.data("openNonce");
  const isCurrent = (): boolean => $modal.data("openNonce") === openNonce;

  const onResent = (): void => {
    const key: string = String($modal.data("cooldownKey") ?? "");
    cooldownRecord = {
      key,
      endsAt:
        Date.now() + APP_CONFIG.constants.EMAIL_RESEND_COOLDOWN_SECONDS * 1000,
    };
    showSplashModalAlertBanner(
      $modal,
      APP_CONFIG.strings.REGISTRATION_EMAIL_RESENT,
      "success",
    );
    announce({
      $modal,
      text: APP_CONFIG.strings.REGISTRATION_EMAIL_RESENT,
      isError: false,
    });
    applyCooldownState($modal);
  };

  const request: JQuery.jqXHR = ajaxCall(
    "POST",
    APP_CONFIG.routes.resendRegistrationEmail,
    { resendToken },
    RESEND_TIMEOUT_MS,
  );

  request.done(() => {
    if (!isCurrent()) return;
    onResent();
  });

  request.fail((xhr: JQuery.jqXHR) => {
    if (!isCurrent()) return;
    if (is429Handled(xhr)) {
      setResendEnabled($modal);
      return;
    }

    if (xhr.status === 0) {
      // Network/timeout blip: keep the opaque, uniform success copy.
      onResent();
      return;
    }

    setResendEnabled($modal);
    showSplashModalAlertBanner(
      $modal,
      APP_CONFIG.strings.REGISTRATION_EMAIL_RESEND_ERROR,
      "danger",
    );
    announce({
      $modal,
      text: APP_CONFIG.strings.REGISTRATION_EMAIL_RESEND_ERROR,
      isError: true,
    });
  });
}

function handleHidden($modal: JQuery): void {
  clearTimers();
  hideSplashModalAlertBanner($modal);
  $modal.find("#ConfirmEmailStatus").attr("role", "status").text("");
  setResendEnabled($modal);
  $modal
    .removeData("resendToken")
    .removeData("cooldownKey")
    .removeData("openNonce");

  const switchedToLogin: boolean = $modal.data("switching") === true;
  $modal.removeData("switching");
  if (switchedToLogin) return;

  const heroLogin: HTMLElement | null = document.querySelector(
    "#splashHero .to-login",
  );
  (heroLogin ?? document.body).focus();
}
