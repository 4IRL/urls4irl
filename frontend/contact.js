import { $ } from "./lib/globals.js";
import "./lib/security-check.js";
import { initNavbarRouting } from "./lib/navbar-shared.js";

$(document).ready(() => {
  // Initialize navbar routing
  initNavbarRouting();

  const $form = $("form#ContactForm");
  if (!$form.length) return;

  // Disable submit button on form submission
  $form.on("submit", function () {
    const $submitBtn = $(this).find('input[type="submit"]');
    $submitBtn.prop("disabled", true);
    $submitBtn.val("Sending...");
  });

  // Countdown timer if form was already submitted
  const $submitBtn = $('input[data-sent="true"]');
  if ($submitBtn.length) {
    const originalValue = $submitBtn.val();
    $submitBtn.prop("disabled", true);
    let timeLeft = 5;

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
  }
});
