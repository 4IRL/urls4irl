import { UI_EVENTS } from "../../../lib/metrics-events.js";
import { setupOpenCreateUTubTagEventListeners } from "../create.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../../utubs/utils.js", () => ({
  getNumOfUTubs: vi.fn(() => 1),
}));

vi.mock("../tags.js", () => ({
  buildTagFilterInDeck: vi.fn(() => window.jQuery("<div></div>")),
}));

vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ tags: [] })),
  setState: vi.fn(),
}));

const $ = window.jQuery;

const CREATE_UTUB_TAG_HTML = `
  <button id="utubTagBtnCreate"></button>
  <div id="createUTubTagWrap" class="hidden"></div>
  <div id="listTags"></div>
  <div id="utubTagStandardBtns"></div>
  <input id="utubTagCreate" />
  <button id="utubTagSubmitBtnCreate"></button>
  <button id="utubTagCancelBtnCreate"></button>
  <div id="utubTagCreate-error"></div>
`;

describe("tags/create metrics — UI_TAG_CREATE_OPEN (scope:utub)", () => {
  beforeEach(() => {
    document.body.innerHTML = CREATE_UTUB_TAG_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("emits ui_tag_create_open with scope:utub when the create button is clicked", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setupOpenCreateUTubTagEventListeners(1);
    $("#utubTagBtnCreate").trigger("click.createUTubTag");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_TAG_CREATE_OPEN,
      scope: "utub",
    });
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("does not emit when listeners are set up but no click occurs", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setupOpenCreateUTubTagEventListeners(1);

    expect(emit).not.toHaveBeenCalled();
  });
});
