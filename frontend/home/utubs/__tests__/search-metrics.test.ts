import { UI_EVENTS } from "../../../types/metrics-events.js";
import {
  closeUTubNameFilter,
  openUTubNameFilter,
  resetUTubSearch,
  setUTubSelectorSearchEventListener,
} from "../search.js";
import {
  UTUB_SEARCH_CLOSE_TARGET,
  UTUB_SEARCH_OPEN_TARGET,
} from "../../../types/metrics-dim-values.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../logic/utub-search.js", () => ({
  filterUTubsByName: vi.fn(() => []),
}));

const $ = window.jQuery;

const SEARCH_HTML = `
  <div id="UTubDeck">
    <button id="utubNameFilterBtn"></button>
    <button id="utubNameFilterBtnClose" class="hidden"></button>
    <div id="UTubDeckSubheader" class="hidden">Create a UTub</div>
    <div id="SearchUTubWrap">
      <input id="UTubNameSearch" type="search" value="" />
    </div>
    <p id="UTubSearchNoResults" class="hidden"></p>
    <span id="UTubSearchAnnouncement"></span>
    <button id="memberBtnCreate"></button>
    <div id="listUTubs">
      <div class="UTubSelector" utubid="1"><span class="UTubName">Alpha</span></div>
      <div class="UTubSelector" utubid="2"><span class="UTubName">Beta</span></div>
    </div>
  </div>
`;

// Module-level _utubSearchOpen flag persists across tests; explicitly reset
// by triggering a blur on the input after attaching the listener.
function resetSearchModuleState(): void {
  setUTubSelectorSearchEventListener();
  $("#UTubNameSearch").trigger("blur.searchInputEsc");
}

describe("UTub search metrics — UI_UTUB_SEARCH_OPEN / UI_UTUB_SEARCH_CLOSE", () => {
  beforeEach(() => {
    document.body.innerHTML = SEARCH_HTML;
    resetSearchModuleState();
    vi.clearAllMocks();
  });

  afterEach(() => {
    $("#UTubNameSearch").trigger("blur.searchInputEsc");
    document.body.innerHTML = "";
  });

  it("emits ui_utub_search_open with target 'utubs' when input gains focus", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    $("#UTubNameSearch").trigger("focus.searchInputEsc");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_UTUB_SEARCH_OPEN,
      target: UTUB_SEARCH_OPEN_TARGET.UTUBS,
    });
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("does not double-emit when focus fires a second time without a blur between", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    $("#UTubNameSearch").trigger("focus.searchInputEsc");
    $("#UTubNameSearch").trigger("focus.searchInputEsc");

    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("re-emits ui_utub_search_open after a blur resets the flag", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    $("#UTubNameSearch").trigger("focus.searchInputEsc");
    $("#UTubNameSearch").trigger("blur.searchInputEsc");
    $("#UTubNameSearch").trigger("focus.searchInputEsc");

    expect(emit).toHaveBeenCalledTimes(2);
    expect(emit).toHaveBeenNthCalledWith(1, {
      event: UI_EVENTS.UI_UTUB_SEARCH_OPEN,
      target: UTUB_SEARCH_OPEN_TARGET.UTUBS,
    });
    expect(emit).toHaveBeenNthCalledWith(2, {
      event: UI_EVENTS.UI_UTUB_SEARCH_OPEN,
      target: UTUB_SEARCH_OPEN_TARGET.UTUBS,
    });
  });

  it("emits ui_utub_search_close with target 'utubs' when resetUTubSearch runs while open", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    $("#UTubNameSearch").trigger("focus.searchInputEsc");
    vi.mocked(emit).mockClear();

    resetUTubSearch();

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_UTUB_SEARCH_CLOSE,
      target: UTUB_SEARCH_CLOSE_TARGET.UTUBS,
    });
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("does not emit ui_utub_search_close from resetUTubSearch when never focused (init path)", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    resetUTubSearch();

    expect(emit).not.toHaveBeenCalled();
  });

  it("does not emit on listener setup alone (no init emit)", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    // beforeEach already attached the listener and blurred to reset state.
    expect(emit).not.toHaveBeenCalled();
  });

  describe("funnel toggle show/hide", () => {
    it("emits ui_utub_search_open when the funnel is opened (focus is triggered)", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");

      openUTubNameFilter();

      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_UTUB_SEARCH_OPEN,
        target: UTUB_SEARCH_OPEN_TARGET.UTUBS,
      });
      expect(emit).toHaveBeenCalledTimes(1);
    });

    it("emits ui_utub_search_close when the funnel is closed", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");

      openUTubNameFilter();
      vi.mocked(emit).mockClear();

      closeUTubNameFilter();

      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_UTUB_SEARCH_CLOSE,
        target: UTUB_SEARCH_CLOSE_TARGET.UTUBS,
      });
      expect(emit).toHaveBeenCalledTimes(1);
    });

    it("still emits ui_utub_search_close when the input blurred first (X-button race)", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");

      openUTubNameFilter();
      // Clicking the X button blurs the input before the click handler runs,
      // clearing the focus flag — the DOM-state guard must still record the close.
      $("#UTubNameSearch").trigger("blur.searchInputEsc");
      vi.mocked(emit).mockClear();

      closeUTubNameFilter();

      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_UTUB_SEARCH_CLOSE,
        target: UTUB_SEARCH_CLOSE_TARGET.UTUBS,
      });
      expect(emit).toHaveBeenCalledTimes(1);
    });

    it("does not emit close when the funnel was not open", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");

      closeUTubNameFilter();

      expect(emit).not.toHaveBeenCalled();
    });
  });
});
