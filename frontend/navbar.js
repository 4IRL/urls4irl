import "bootstrap/dist/css/bootstrap.min.css";
import "./styles/base.css";
import "./styles/privacy-terms.css";
import "./lib/security-check.js";
import { $ } from "./lib/globals.js";
import { initNavbarRouting } from "./lib/navbar-shared.js";

$(document).ready(() => {
  initNavbarRouting();
});
