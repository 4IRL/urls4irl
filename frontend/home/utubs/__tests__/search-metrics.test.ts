import { UI_EVENTS } from "../../../lib/metrics-events.js";
import {
  resetUTubSearch,
  setUTubSelectorSearchEventListener,
} from "../search.js";
import {
  SEARCH_CLOSE_TARGET,
  SEARCH_OPEN_TARGET,
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
`;

// Module-level _utubSearchOpen flag persists across tests; explicitly reset
// by triggering a blur on the input after attaching the listener.
function resetSearchModuleState(): void {
  setUTubSelectorSearchEventListener();
  $("#UTubNameSearch").trigger("blur.searchInputEsc");
}

describe("UTub search metrics — UI_SEARCH_OPEN / UI_SEARCH_CLOSE", () => {
  beforeEach(() => {
    document.body.innerHTML = SEARCH_HTML;
    resetSearchModuleState();
    vi.clearAllMocks();
  });

  afterEach(() => {
    $("#UTubNameSearch").trigger("blur.searchInputEsc");
    document.body.innerHTML = "";
  });

  it("emits ui_search_open with target 'utubs' when input gains focus", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    $("#UTubNameSearch").trigger("focus.searchInputEsc");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_SEARCH_OPEN,
      target: SEARCH_OPEN_TARGET.UTUBS,
    });
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("does not double-emit when focus fires a second time without a blur between", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    $("#UTubNameSearch").trigger("focus.searchInputEsc");
    $("#UTubNameSearch").trigger("focus.searchInputEsc");

    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("re-emits ui_search_open after a blur resets the flag", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    $("#UTubNameSearch").trigger("focus.searchInputEsc");
    $("#UTubNameSearch").trigger("blur.searchInputEsc");
    $("#UTubNameSearch").trigger("focus.searchInputEsc");

    expect(emit).toHaveBeenCalledTimes(2);
    expect(emit).toHaveBeenNthCalledWith(1, {
      event: UI_EVENTS.UI_SEARCH_OPEN,
      target: SEARCH_OPEN_TARGET.UTUBS,
    });
    expect(emit).toHaveBeenNthCalledWith(2, {
      event: UI_EVENTS.UI_SEARCH_OPEN,
      target: SEARCH_OPEN_TARGET.UTUBS,
    });
  });

  it("emits ui_search_close with target 'utubs' when resetUTubSearch runs while open", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    $("#UTubNameSearch").trigger("focus.searchInputEsc");
    vi.mocked(emit).mockClear();

    resetUTubSearch();

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_SEARCH_CLOSE,
      target: SEARCH_CLOSE_TARGET.UTUBS,
    });
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("does not emit ui_search_close from resetUTubSearch when never focused (init path)", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    resetUTubSearch();

    expect(emit).not.toHaveBeenCalled();
  });

  it("does not emit on listener setup alone (no init emit)", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    // beforeEach already attached the listener and blurred to reset state.
    expect(emit).not.toHaveBeenCalled();
  });
});
