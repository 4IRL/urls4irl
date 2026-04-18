import "bootstrap/dist/css/bootstrap.min.css";
import "font-awesome/css/font-awesome.min.css";
import "./styles/base.css";
import "./styles/home/index.css";
import "./lib/security-check.js";
import { $ } from "./lib/globals.js";
import { loadInitialUtubState } from "./lib/initial-state.js";
import { registerJQueryPlugins } from "./lib/jquery-plugins.js";
import { setupCSRF } from "./lib/csrf.js";
import { initCookieBanner } from "./lib/cookie-banner.js";

import { initBtnsForms } from "./home/btns-forms.js";
import { initVisibilityHandlers } from "./home/visibility.js";
import { initNavbar } from "./home/navbar.js";
import { initMobileLayout } from "./home/mobile.js";
import { initWindowEvents } from "./home/window-events.js";
import { initCollapsibleDecks } from "./home/collapsible-decks.js";
import { setUTubEventListenersOnInitialPageLoad } from "./home/utubs/deck.js";
import { setCreateUTubEventListeners } from "./home/utubs/create.js";
import { initUnselectAllTags } from "./home/tags/unselect-all.js";
import { initUpdateAllTags } from "./home/tags/update-all.js";
import { initURLDeck } from "./home/urls/deck.js";
import { initAccessAllURLsBtn } from "./home/urls/access-all.js";
import "./home/members/deck.js";
import "./home/tags/deck.js";
import "./home/urls/cards/filtering.js";

// Register jQuery plugins and setup CSRF before DOM ready
registerJQueryPlugins();
setupCSRF();

// Initialize on DOM ready
$(document).ready(() => {
  loadInitialUtubState();

  initBtnsForms();
  initVisibilityHandlers();
  initNavbar();
  initMobileLayout();
  initCollapsibleDecks();
  setCreateUTubEventListeners();
  setUTubEventListenersOnInitialPageLoad();
  initUnselectAllTags();
  initUpdateAllTags();
  initURLDeck();
  initAccessAllURLsBtn();
  initCookieBanner();
});

// Initialize window events (must be outside DOM ready)
initWindowEvents();
