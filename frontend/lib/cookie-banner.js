import { $ } from "./globals.js";
import { APP_CONFIG } from "./config.js";
import { KEYS } from "./constants.js";

export function initCookieBanner() {
  const $banner = $("#CookieBanner");
  if (!$banner.length) return;

  // Show after render if not seen
  setTimeout(() => {
    if (!document.cookie.includes(APP_CONFIG.strings.COOKIE_BANNER_SEEN)) {
      $banner.addClass("is-visible");
    }
  }, 0);

  function setCookieBannerSeenCookie() {
    const date = new Date();
    date.setTime(date.getTime() + 365 * 24 * 60 * 60 * 1000);
    const expires = "expires=" + date.toUTCString();
    const secureFlag = location.protocol === "https:" ? "; Secure" : "";
    document.cookie = `${APP_CONFIG.strings.COOKIE_BANNER_SEEN};${expires}; path=/; SameSite=Lax${secureFlag}`;
  }

  function hideBanner() {
    setCookieBannerSeenCookie();
    $banner.removeClass("is-visible");
    $(document).off("click.clickOutsideBanner keyup.clickOutsideBanner");
  }

  // Click handler for interactive elements
  const interactiveClickSelectors = [
    "a",
    "button",
    ".UTubSelector",
    ".memberOtherBtnDelete",
    ".clickable",
    ".tagFilter",
    ".urlRow",
  ];
  $(document).on("click.clickOutsideBanner", (e) => {
    if ($(e.target.closest(interactiveClickSelectors.join(","))).length > 0) {
      hideBanner();
    }
  });

  // Keyboard handler for Enter key
  const interactiveKeySelectors = [
    ".UTubSelector",
    ".clickable",
    ".tagFilter",
    ".urlRow",
  ];
  $(document).on("keyup.clickOutsideBanner", (e) => {
    if (e.originalEvent.repeat) return;
    if (
      e.key === KEYS.ENTER &&
      $(e.target.closest(interactiveKeySelectors.join(","))).length > 0
    ) {
      hideBanner();
    }
  });
}
