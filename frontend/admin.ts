import "bootstrap/dist/css/bootstrap.min.css";
import "./styles/base.css";
import "./styles/admin/admin-portal.css";
import "./lib/security-check.js";
import htmx from "htmx.org";
import { $ } from "./lib/globals.js";
import { registerJQueryPlugins } from "./lib/jquery-plugins.js";
import { setupCSRF } from "./lib/csrf.js";
import { initCookieBanner } from "./lib/cookie-banner.js";
import { initNavbarBackdrop, initNavbarRouting } from "./lib/navbar-shared.js";

// The app ships a strict nonce-based CSP (no unsafe-eval, nonce-only
// style-src). Disable htmx's eval-dependent features (hx-on, js: prefixes,
// event filters) and its inline indicator <style> injection — indicator
// styling lives in styles/admin/admin-portal.css instead.
htmx.config.allowEval = false;
htmx.config.includeIndicatorStyles = false;

registerJQueryPlugins();
setupCSRF();

$(document).ready(() => {
  initCookieBanner();
  initNavbarRouting();
  initNavbarBackdrop();
});
