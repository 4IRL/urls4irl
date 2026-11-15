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

// Duplicates base.css: #CookieBanner slides with a transform above this width and is flush
// at the bottom at or below it; the gap is 1.75rem + 2px while it floats.
const BANNER_FLUSH_MAX_WIDTH_PX = 1049;
const BANNER_FLOAT_GAP_REM = 1.75;
const BANNER_FLOAT_GAP_BORDER_PX = 2;

function bannerOffsetPx({
  banner,
  isFlush,
}: {
  banner: HTMLElement | null;
  isFlush: boolean;
}): number {
  if (!banner || !banner.classList.contains("is-visible")) return 0;
  if (isFlush) return banner.offsetHeight;
  const rootFontPx =
    parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
  return (
    banner.offsetHeight +
    BANNER_FLOAT_GAP_REM * rootFontPx +
    BANNER_FLOAT_GAP_BORDER_PX
  );
}

// Publishes the bar height and the cookie banner's final resting offset as CSS vars on
// <html> so the bar stacks above the banner (never its mid-transition rect).
function initPreviewBar(): void {
  const bar = document.getElementById("invitePreviewBar");
  if (!bar) return;
  const root = document.documentElement;
  const banner = document.getElementById("CookieBanner");
  const query = window.matchMedia(
    `(max-width: ${BANNER_FLUSH_MAX_WIDTH_PX}px)`,
  );

  const update = (): void => {
    root.style.setProperty("--invite-bar-height", `${bar.offsetHeight}px`);
    root.style.setProperty(
      "--invite-banner-offset",
      `${bannerOffsetPx({ banner, isFlush: query.matches })}px`,
    );
  };

  update();
  window.addEventListener("resize", update);
  query.addEventListener("change", update);
  if (banner) {
    new MutationObserver(update).observe(banner, {
      attributes: true,
      attributeFilter: ["class"],
    });
  }
  if (typeof ResizeObserver !== "undefined") {
    const resizeObserver = new ResizeObserver(update);
    resizeObserver.observe(bar);
    if (banner) resizeObserver.observe(banner);
  }
}

// Rewrites the badge date to the viewer's local date; the server renders a UTC fallback.
function localizePreviewDate(): void {
  const time = document.querySelector<HTMLTimeElement>(
    "#invitePreviewBadge time",
  );
  if (!time) return;
  const date = new Date(time.getAttribute("datetime") ?? "");
  if (Number.isNaN(date.getTime())) return;
  time.textContent = date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

// Public invite page: shares the short-link shell. A logged-in viewer's navbar has
// no dropdown, which initNavbarBackdrop tolerates.
$(document).ready(() => {
  initNavbarRouting();
  initNavbarBackdrop();
  initCookieBanner();
  initPreviewBar();
  localizePreviewDate();
  initJoinButton();
});
