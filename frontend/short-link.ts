import "bootstrap/dist/css/bootstrap.min.css";
import "./styles/base.css";
import "./styles/short-link.css";
import "./lib/security-check.js";
import { $ } from "./lib/globals.js";
import { initCookieBanner } from "./lib/cookie-banner.js";
import { initNavbarBackdrop, initNavbarRouting } from "./lib/navbar-shared.js";

// Public share-link page: the hamburger nav and cookie banner are all it needs.
$(document).ready(() => {
  initNavbarRouting();
  initNavbarBackdrop();
  initCookieBanner();
});
