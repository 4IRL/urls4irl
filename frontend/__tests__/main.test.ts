import { setState } from "../store/app-store.js";

vi.mock("bootstrap/dist/css/bootstrap.min.css", () => ({}));
vi.mock("font-awesome/css/font-awesome.min.css", () => ({}));
vi.mock("../styles/base.css", () => ({}));
vi.mock("../styles/home/index.css", () => ({}));
vi.mock("../lib/security-check.js", () => ({}));
vi.mock("../lib/globals.js", () => ({
  $: window.jQuery,
  jQuery: window.jQuery,
  bootstrap: window.bootstrap,
}));
vi.mock("../lib/config.js", () => {
  const configScript = document.getElementById("app-config")!;
  const config = JSON.parse(configScript.textContent!);
  return { APP_CONFIG: config };
});
vi.mock("../store/app-store.js", () => ({
  setState: vi.fn(),
}));
vi.mock("../lib/jquery-plugins.js", () => ({
  registerJQueryPlugins: vi.fn(),
  enableTabbableChildElements: vi.fn(),
  disableTabbableChildElements: vi.fn(),
}));
vi.mock("../lib/csrf.js", () => ({ setupCSRF: vi.fn() }));
vi.mock("../lib/cookie-banner.js", () => ({ initCookieBanner: vi.fn() }));
vi.mock("../lib/ajax.js", () => ({ ajaxCall: vi.fn(), debugCall: vi.fn() }));
vi.mock("../lib/page-utils.js", () => ({
  showNewPageOnAJAXHTMLResponse: vi.fn(),
}));
vi.mock("../lib/constants.js", () => ({
  KEYS: {},
  METHOD_TYPES: {},
  INPUT_TYPES: {},
  SHOW_LOADING_ICON_AFTER_MS: 300,
  TABLET_WIDTH: 768,
}));
vi.mock("../home/btns-forms.js", () => ({ initBtnsForms: vi.fn() }));
vi.mock("../home/visibility.js", () => ({ initVisibilityHandlers: vi.fn() }));
vi.mock("../home/init.js", () => ({}));
vi.mock("../home/navbar.js", () => ({ initNavbar: vi.fn() }));
vi.mock("../home/mobile.js", () => ({ initMobileLayout: vi.fn() }));
vi.mock("../home/window-events.js", () => ({ initWindowEvents: vi.fn() }));
vi.mock("../home/collapsible-decks.js", () => ({
  initCollapsibleDecks: vi.fn(),
}));
vi.mock("../home/utubs/deck.js", () => ({
  setUTubEventListenersOnInitialPageLoad: vi.fn(),
}));
vi.mock("../home/utubs/utils.js", () => ({}));
vi.mock("../home/utubs/selectors.js", () => ({}));
vi.mock("../home/utubs/search.js", () => ({}));
vi.mock("../home/utubs/create.js", () => ({
  setCreateUTubEventListeners: vi.fn(),
}));
vi.mock("../home/utubs/delete.js", () => ({}));
vi.mock("../home/utubs/stale-data.js", () => ({}));
vi.mock("../home/members/deck.js", () => ({}));
vi.mock("../home/members/members.js", () => ({}));
vi.mock("../home/members/create.js", () => ({}));
vi.mock("../home/members/delete.js", () => ({}));
vi.mock("../home/tags/deck.js", () => ({}));
vi.mock("../home/tags/tags.js", () => ({}));
vi.mock("../home/tags/utils.js", () => ({}));
vi.mock("../home/tags/create.js", () => ({}));
vi.mock("../home/tags/delete.js", () => ({}));
vi.mock("../home/tags/unselect-all.js", () => ({
  initUnselectAllTags: vi.fn(),
}));
vi.mock("../home/tags/update-all.js", () => ({
  initUpdateAllTags: vi.fn(),
}));
vi.mock("../home/urls/deck.js", () => ({ initURLDeck: vi.fn() }));
vi.mock("../home/urls/utils.js", () => ({}));
vi.mock("../home/urls/validation.js", () => ({}));
vi.mock("../home/urls/create-btns.js", () => ({}));
vi.mock("../home/urls/access-all.js", () => ({
  initAccessAllURLsBtn: vi.fn(),
}));
vi.mock("../home/urls/update-name.js", () => ({}));
vi.mock("../home/urls/update-description.js", () => ({}));
vi.mock("../home/urls/cards/cards.js", () => ({}));
vi.mock("../home/urls/cards/create.js", () => ({}));
vi.mock("../home/urls/cards/delete.js", () => ({}));
vi.mock("../home/urls/cards/get.js", () => ({}));
vi.mock("../home/urls/cards/update-string.js", () => ({}));
vi.mock("../home/urls/cards/update-title.js", () => ({}));
vi.mock("../home/urls/cards/copy.js", () => ({}));
vi.mock("../home/urls/cards/access.js", () => ({}));
vi.mock("../home/urls/cards/corner-access.js", () => ({}));
vi.mock("../home/urls/cards/filtering.js", () => ({}));
vi.mock("../home/urls/cards/loading.js", () => ({}));
vi.mock("../home/urls/cards/selection.js", () => ({}));
vi.mock("../home/urls/cards/url-string.js", () => ({}));
vi.mock("../home/urls/cards/url-title.js", () => ({}));
vi.mock("../home/urls/cards/utils.js", () => ({}));
vi.mock("../home/urls/cards/options/btns.js", () => ({}));
vi.mock("../home/urls/cards/options/access-btn.js", () => ({}));
vi.mock("../home/urls/cards/options/copy-btn.js", () => ({}));
vi.mock("../home/urls/cards/options/edit-string-btn.js", () => ({}));
vi.mock("../home/urls/cards/options/delete-btn.js", () => ({}));
vi.mock("../home/urls/cards/options/tag-btn.js", () => ({}));
vi.mock("../home/urls/tags/tags.js", () => ({}));
vi.mock("../home/urls/tags/create.js", () => ({}));
vi.mock("../home/urls/tags/delete.js", () => ({}));

describe("main.ts DOM-ready bootstrap", () => {
  afterEach(() => {
    vi.resetModules();
    vi.mocked(setState).mockClear();
  });

  it("calls setState with parsed utubs data when #utubs-data is present", async () => {
    const testUtubs = [{ id: 1, name: "Test UTub" }];
    const script = document.createElement("script");
    script.id = "utubs-data";
    script.type = "application/json";
    script.textContent = JSON.stringify(testUtubs);
    document.body.appendChild(script);

    // main.ts registers a $(document).ready() callback.
    // In jsdom the document is already complete, so jQuery fires it synchronously.
    await import("../main.js");

    // Flush any microtasks from jQuery ready queue
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(vi.mocked(setState)).toHaveBeenCalledWith({ utubs: testUtubs });

    script.remove();
  });

  it("does not call setState when #utubs-data is absent", async () => {
    await import("../main.js");
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(vi.mocked(setState)).not.toHaveBeenCalled();
  });
});
