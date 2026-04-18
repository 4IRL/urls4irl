import "bootstrap/dist/css/bootstrap.min.css";
import "./styles/base.css";
import "./styles/contact.css";
import { $ } from "./lib/globals.js";
import "./lib/security-check.js";
import { setupCSRF } from "./lib/csrf.js";
import { APP_CONFIG } from "./lib/config.js";
import { showNewPageOnAJAXHTMLResponse } from "./lib/page-utils.js";
import { initNavbarRouting } from "./lib/navbar-shared.js";

// Setup CSRF for AJAX requests
setupCSRF();

export function clearFieldErrors($form: JQuery): void {
  $form.find(".form-control").removeClass("is-invalid");
  $form.find(".invalid-feedback").text("");
}

export function showFieldErrors(
  $form: JQuery,
  errors: Record<string, string[]>,
): void {
  clearFieldErrors($form);
  for (const field in errors) {
    const $input = $form.find(`#${field}`);
    $input.addClass("is-invalid");
    $form.find(`#${field}-error`).text(errors[field].join(", "));
  }
}

export function showBanner(
  $banner: JQuery,
  message: string,
  type: string,
): void {
  $banner
    .removeClass("hidden alert-success alert-danger")
    .addClass(`alert-${type}`)
    .text(message);
}

export function startSubmitCountdown(
  $submitBtn: JQuery,
  seconds: number,
): ReturnType<typeof setInterval> {
  const originalValue = $submitBtn.val();
  $submitBtn.prop("disabled", true);
  let timeLeft = seconds;

  $submitBtn.val(`Submitted! Please wait ${timeLeft}s...`);

  const interval = setInterval(() => {
    timeLeft--;
    if (timeLeft > 0) {
      $submitBtn.val(`Submitted! Please wait ${timeLeft}s...`);
    } else {
      clearInterval(interval);
      $submitBtn.prop("disabled", false);
      $submitBtn.val(originalValue);
    }
  }, 1000);

  return interval;
}

export function handleContactSubmit(event: Event, $form: JQuery): void {
  event.preventDefault();

  const $banner = $form.find("#Banner");
  const $submitBtn = $form.find("#submit");
  const subject = $form.find("#subject").val();
  const content = $form.find("#content").val();

  clearFieldErrors($form);
  $banner.addClass("hidden");

  const contactRequest = $.ajax({
    url: APP_CONFIG.routes.contactUs,
    type: "POST",
    data: JSON.stringify({ subject, content }),
    contentType: "application/json",
  });

  contactRequest.done((response) => {
    showBanner($banner, response.message, "success");
    startSubmitCountdown($submitBtn, 5);
  });

  contactRequest.fail((xhr) => {
    if (xhr.responseJSON === undefined) {
      if (
        xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
      ) {
        switch (xhr.status) {
          case 403:
          case 429: {
            showNewPageOnAJAXHTMLResponse(xhr.responseText);
            return;
          }
        }
      }
      showBanner($banner, "Unable to submit contact form.", "danger");
      return;
    }

    if (xhr.status === 400 && xhr.responseJSON.errors) {
      showFieldErrors($form, xhr.responseJSON.errors);
    } else {
      showBanner(
        $banner,
        xhr.responseJSON.message || "Unable to submit contact form.",
        "danger",
      );
    }
  });
}

$(document).ready(() => {
  // Initialize navbar routing
  initNavbarRouting();

  const $form = $("form#ContactForm");
  if (!$form.length) return;

  $form.on("submit", (event) => handleContactSubmit(event, $form));
});
