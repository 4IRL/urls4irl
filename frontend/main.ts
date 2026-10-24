import "bootstrap/dist/css/bootstrap.min.css";
import "font-awesome/css/font-awesome.min.css";
import "./styles/base.css";
import "./styles/home/index.css";
import "./lib/security-check.js";
import { $ } from "./lib/globals.js";
import {
  loadInitialPreferencesState,
  loadInitialUtubState,
} from "./lib/initial-state.js";
import { getState } from "./store/app-store.js";
import { registerJQueryPlugins } from "./lib/jquery-plugins.js";
import { setupCSRF } from "./lib/csrf.js";
import { initCookieBanner } from "./lib/cookie-banner.js";
import { initMetricsClient } from "./lib/metrics-client.js";
import { initTooltips } from "./lib/tooltips.js";

import { initBtnsForms } from "./home/btns-forms.js";
import { initVisibilityHandlers } from "./home/visibility.js";
import { initNavbar } from "./home/navbar.js";
import { initMobileLayout } from "./home/mobile.js";
import { initWindowEvents } from "./home/window-events.js";
import { initCollapsibleDecks } from "./home/collapsible-decks.js";
import { initLeftPanelToggle } from "./home/left-panel-toggle.js";
import { setUTubEventListenersOnInitialPageLoad } from "./home/utubs/deck.js";
import { initCrossUtubSearch } from "./home/search/cross-utub-search.js";
import { setCreateUTubEventListeners } from "./home/utubs/create.js";
import { initUnselectAllTags } from "./home/tags/unselect-all.js";
import { initUpdateAllTags } from "./home/tags/update-all.js";
import { initURLDeck } from "./home/urls/deck.js";
import { initBulkActions } from "./home/urls/bulk-actions/index.js";
import { initSwipe } from "./home/urls/cards/swipe.js";
import { initURLOutcomeBannerLifecycle } from "./home/urls/outcome-banner.js";
import { initURLDeckHeaderFit } from "./home/utubs/header-fit.js";
import { initUTubRefreshOnFocus } from "./home/utubs/refresh-on-focus.js";
import { initUTubSelectionIndicator } from "./home/utubs/selection-indicator.js";
import { initTagSheet } from "./home/tags/sheet.js";
import { initTagDragDrop } from "./home/tags/drag-drop.js";
import {
  applyDefaultDensity,
  applyDefaultViewMode,
} from "./home/urls/cards/filtering.js";
import "./home/members/deck.js";
import "./home/tags/deck.js";
import { initTransferPicker } from "./home/members/transfer-picker.js";
import { initOnboardingNudges } from "./home/onboarding/nudges.js";
import { initPanelSettings } from "./home/panel-settings/index.js";
import { registerUrlsSettingsSection } from "./home/urls/settings-section.js";
import { loadInitialTrashCount, renderTrashCount } from "./home/trash/count.js";
import { initTrashTabs } from "./home/trash/tabs.js";
import { initTrashPanel } from "./home/trash/panel.js";
import { initTrashActions } from "./home/trash/actions.js";
import { initTrashSwipe } from "./home/trash/swipe.js";

// Register jQuery plugins and setup CSRF before DOM ready
registerJQueryPlugins();
setupCSRF();

// Initialize on DOM ready
$(document).ready(() => {
  loadInitialUtubState();
  loadInitialPreferencesState();
  applyDefaultViewMode(getState().preferences.defaultView);
  applyDefaultDensity(getState().preferences.density);

  initBtnsForms();
  initVisibilityHandlers();
  // Right after initVisibilityHandlers(): focus restoration runs first.
  initUTubRefreshOnFocus();
  initNavbar();
  initMobileLayout();
  initCollapsibleDecks();
  initTagSheet();
  // After the decks/sheet (it listens for their collapse events) and before
  // initTooltips()/initOnboardingNudges(), which must see the gear states.
  initPanelSettings();
  registerUrlsSettingsSection();
  initLeftPanelToggle();
  setCreateUTubEventListeners();
  setUTubEventListenersOnInitialPageLoad();
  initCrossUtubSearch();
  initUnselectAllTags();
  initUpdateAllTags();
  initURLDeck();
  initTagDragDrop();
  initBulkActions();
  initTransferPicker();
  loadInitialTrashCount();
  renderTrashCount();
  initTrashTabs();
  initTrashPanel();
  initTrashActions();
  initTrashSwipe();
  initSwipe();
  initURLOutcomeBannerLifecycle();
  initURLDeckHeaderFit();
  initUTubSelectionIndicator();
  initCookieBanner();
  initMetricsClient();
  // Before initOnboardingNudges(): the nudge anchors are deliberately excluded
  // from the tooltip sweep, so ordering is not a correctness lever here — but
  // keeping nudge init last preserves the "nudges evaluate against fully
  // initialised state" invariant.
  initTooltips();
  initOnboardingNudges();
});

// Initialize window events (must be outside DOM ready)
initWindowEvents();
