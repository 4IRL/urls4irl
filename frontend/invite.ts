import "bootstrap/dist/css/bootstrap.min.css";
import "./styles/base.css";
import "./styles/short-link.css";
import "./styles/invite.css";
import "./lib/security-check.js";
import { $ } from "./lib/globals.js";
import { initCookieBanner } from "./lib/cookie-banner.js";
import { initNavbarBackdrop, initNavbarRouting } from "./lib/navbar-shared.js";

// Public invite page: shares the short-link shell. A logged-in viewer's navbar has
// no dropdown, which initNavbarBackdrop tolerates.
$(document).ready(() => {
  initNavbarRouting();
  initNavbarBackdrop();
  initCookieBanner();
});
