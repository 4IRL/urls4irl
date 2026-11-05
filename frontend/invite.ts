import "bootstrap/dist/css/bootstrap.min.css";
import "./styles/base.css";
import "./styles/short-link.css";
import "./styles/invite.css";
import "./lib/security-check.js";
import { $ } from "./lib/globals.js";
import { initCookieBanner } from "./lib/cookie-banner.js";
import { initNavbarBackdrop, initNavbarRouting } from "./lib/navbar-shared.js";

const JOIN_RESTORE_TIMEOUT_MS = 15000;

// Double-submit guard for the Join form. aria-disabled (never `disabled`) keeps focus on
// the button; a fixed timer and `pageshow` both undo the busy state.
function initJoinButton(): void {
  const form = document.getElementById("inviteJoinForm");
  const button = document.getElementById("inviteJoinBtn");
  const status = document.getElementById("inviteJoinStatus");
  if (!form || !button || !status) return;

  const originalLabel = button.textContent ?? "";
  const joiningLabel = button.dataset.joiningLabel ?? originalLabel;
  let restoreTimer: ReturnType<typeof setTimeout> | null = null;

  const restore = (): void => {
    if (restoreTimer !== null) {
      clearTimeout(restoreTimer);
      restoreTimer = null;
    }
    button.removeAttribute("aria-disabled");
    form.removeAttribute("aria-busy");
    button.textContent = originalLabel;
    status.textContent = "";
  };

  form.addEventListener("submit", (event) => {
    if (button.getAttribute("aria-disabled") === "true") {
      event.preventDefault();
      return;
    }
    button.setAttribute("aria-disabled", "true");
    form.setAttribute("aria-busy", "true");
    button.textContent = joiningLabel;
    status.textContent = joiningLabel;
    restoreTimer = setTimeout(restore, JOIN_RESTORE_TIMEOUT_MS);
  });

  window.addEventListener("pageshow", restore);
}

// Public invite page: shares the short-link shell. A logged-in viewer's navbar has
// no dropdown, which initNavbarBackdrop tolerates.
$(document).ready(() => {
  initNavbarRouting();
  initNavbarBackdrop();
  initCookieBanner();
  initJoinButton();
});
