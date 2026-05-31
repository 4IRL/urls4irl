import { UI_EVENTS } from "../../../lib/metrics-events.js";
import { setCreateUTubEventListeners } from "../create.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../selectors.js", () => ({
  createUTubSelector: vi.fn(),
  selectUTub: vi.fn(),
}));

vi.mock("../utils.js", () => ({
  getAllAccessibleUTubNames: vi.fn(() => []),
  getNumOfUTubs: vi.fn(() => 1),
  sameNameWarningHideModal: vi.fn(),
}));

vi.mock("../search.js", () => ({
  resetUTubSearch: vi.fn(),
  showUTubSearchBar: vi.fn(),
}));

vi.mock("../deck.js", () => ({
  removeCreateUTubEventListeners: vi.fn(),
}));

vi.mock("../../btns-forms.js", () => ({
  highlightInput: vi.fn(),
}));

vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ utubs: [] })),
  setState: vi.fn(),
}));

const $ = window.jQuery;

const CREATE_UTUB_HTML = `
  <button id="utubBtnCreate"></button>
  <div id="createUTubWrap"></div>
  <div id="listUTubs"></div>
  <div id="UTubDeck">
    <div class="button-container"></div>
  </div>
  <input id="utubNameCreate" />
  <input id="utubDescriptionCreate" />
  <button id="utubSubmitBtnCreate"></button>
  <button id="utubCancelBtnCreate"></button>
`;

describe("create metrics — UI_UTUB_CREATE_OPEN", () => {
  beforeEach(() => {
    document.body.innerHTML = CREATE_UTUB_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("emits ui_utub_create_open when the create button is clicked", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setCreateUTubEventListeners();
    $("#utubBtnCreate").trigger("click.createUTub");

    expect(emit).toHaveBeenCalledWith(UI_EVENTS.UI_UTUB_CREATE_OPEN);
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("does not emit when listeners are set up but no click occurs", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setCreateUTubEventListeners();

    expect(emit).not.toHaveBeenCalled();
  });
});
