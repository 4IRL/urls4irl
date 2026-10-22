/**
 * Init ordering for the home entry point: `initUTubRefreshOnFocus()` must run
 * immediately after `initVisibilityHandlers()` so focus restoration runs first.
 *
 * Every module `main.ts` imports is mocked; each mocked init records its name in
 * `callOrder`. Kept separate from main.test.ts so its app-store mock is not shared.
 */

const { callOrder, track } = vi.hoisted(() => {
  const order: string[] = [];
  return {
    callOrder: order,
    track: (name: string) =>
      vi.fn(() => {
        order.push(name);
      }),
  };
});

vi.mock("../lib/security-check.js", () => ({}));
vi.mock("../home/members/deck.js", () => ({}));
vi.mock("../home/tags/deck.js", () => ({}));

vi.mock("../lib/globals.js", () => ({
  // jQuery's real .ready is asynchronous; run the callback synchronously.
  $: () => ({ ready: (callback: () => void) => callback() }),
}));
vi.mock("../store/app-store.js", () => ({
  getState: () => ({ preferences: {} }),
}));

vi.mock("../lib/initial-state.js", () => ({
  loadInitialUtubState: track("loadInitialUtubState"),
  loadInitialPreferencesState: track("loadInitialPreferencesState"),
}));
vi.mock("../lib/jquery-plugins.js", () => ({
  registerJQueryPlugins: track("registerJQueryPlugins"),
}));
vi.mock("../lib/csrf.js", () => ({ setupCSRF: track("setupCSRF") }));
vi.mock("../lib/cookie-banner.js", () => ({
  initCookieBanner: track("initCookieBanner"),
}));
vi.mock("../lib/metrics-client.js", () => ({
  initMetricsClient: track("initMetricsClient"),
}));
vi.mock("../lib/tooltips.js", () => ({
  initTooltips: track("initTooltips"),
}));

vi.mock("../home/btns-forms.js", () => ({
  initBtnsForms: track("initBtnsForms"),
}));
vi.mock("../home/visibility.js", () => ({
  initVisibilityHandlers: track("initVisibilityHandlers"),
}));
vi.mock("../home/navbar.js", () => ({ initNavbar: track("initNavbar") }));
vi.mock("../home/mobile.js", () => ({
  initMobileLayout: track("initMobileLayout"),
}));
vi.mock("../home/window-events.js", () => ({
  initWindowEvents: track("initWindowEvents"),
}));
vi.mock("../home/collapsible-decks.js", () => ({
  initCollapsibleDecks: track("initCollapsibleDecks"),
}));
vi.mock("../home/left-panel-toggle.js", () => ({
  initLeftPanelToggle: track("initLeftPanelToggle"),
}));
vi.mock("../home/utubs/deck.js", () => ({
  setUTubEventListenersOnInitialPageLoad: track(
    "setUTubEventListenersOnInitialPageLoad",
  ),
}));
vi.mock("../home/search/cross-utub-search.js", () => ({
  initCrossUtubSearch: track("initCrossUtubSearch"),
}));
vi.mock("../home/utubs/create.js", () => ({
  setCreateUTubEventListeners: track("setCreateUTubEventListeners"),
}));
vi.mock("../home/tags/unselect-all.js", () => ({
  initUnselectAllTags: track("initUnselectAllTags"),
}));
vi.mock("../home/tags/update-all.js", () => ({
  initUpdateAllTags: track("initUpdateAllTags"),
}));
vi.mock("../home/urls/deck.js", () => ({
  initURLDeck: track("initURLDeck"),
}));
vi.mock("../home/urls/bulk-actions/index.js", () => ({
  initBulkActions: track("initBulkActions"),
}));
vi.mock("../home/urls/cards/swipe.js", () => ({
  initSwipe: track("initSwipe"),
}));
vi.mock("../home/utubs/header-fit.js", () => ({
  initURLDeckHeaderFit: track("initURLDeckHeaderFit"),
}));
vi.mock("../home/utubs/selection-indicator.js", () => ({
  initUTubSelectionIndicator: track("initUTubSelectionIndicator"),
}));
vi.mock("../home/tags/sheet.js", () => ({
  initTagSheet: track("initTagSheet"),
}));
vi.mock("../home/urls/cards/filtering.js", () => ({
  applyDefaultDensity: track("applyDefaultDensity"),
  applyDefaultViewMode: track("applyDefaultViewMode"),
}));
vi.mock("../home/members/transfer-picker.js", () => ({
  initTransferPicker: track("initTransferPicker"),
}));
vi.mock("../home/onboarding/nudges.js", () => ({
  initOnboardingNudges: track("initOnboardingNudges"),
}));
vi.mock("../home/utubs/refresh-on-focus.js", () => ({
  initUTubRefreshOnFocus: track("initUTubRefreshOnFocus"),
}));
vi.mock("../home/trash/count.js", () => ({
  loadInitialTrashCount: track("loadInitialTrashCount"),
  renderTrashCount: track("renderTrashCount"),
}));
vi.mock("../home/trash/tabs.js", () => ({
  initTrashTabs: track("initTrashTabs"),
}));
vi.mock("../home/trash/panel.js", () => ({
  initTrashPanel: track("initTrashPanel"),
}));
vi.mock("../home/trash/actions.js", () => ({
  initTrashActions: track("initTrashActions"),
}));

import "../main.js";

describe("main.ts init order", () => {
  it("runs initUTubRefreshOnFocus immediately after initVisibilityHandlers", () => {
    const visibilityIndex = callOrder.indexOf("initVisibilityHandlers");

    expect(visibilityIndex).toBeGreaterThanOrEqual(0);
    expect(callOrder.indexOf("initUTubRefreshOnFocus")).toBe(
      visibilityIndex + 1,
    );
  });
});
