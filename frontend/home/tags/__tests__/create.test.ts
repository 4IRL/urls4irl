import type { SuccessResponse } from "../../../types/api-helpers.d.ts";

import { createMockJqXHRChainable } from "../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall } from "../../../lib/ajax.js";
import { setupOpenCreateUTubTagEventListeners } from "../create.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../../../lib/event-bus.js", async () => {
  const actual = await vi.importActual<
    typeof import("../../../lib/event-bus.js")
  >("../../../lib/event-bus.js");
  return {
    ...actual,
    emit: vi.fn(),
  };
});

vi.mock("../../utubs/utils.js", () => ({
  getNumOfUTubs: vi.fn(() => 1),
}));

vi.mock("../tags.js", () => ({
  buildTagFilterInDeck: vi.fn(() => window.jQuery("<div></div>")),
}));

vi.mock("./search.js", () => ({
  closeTagNameFilter: vi.fn(),
  reapplyTagFilter: vi.fn(),
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
  <button id="unselectAllTagFilters"></button>
  <button id="utubTagBtnUpdateAllOpen"></button>
`;

describe("tags/create — notifies the onboarding nudge system", () => {
  beforeEach(() => {
    document.body.innerHTML = CREATE_UTUB_TAG_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("emits AppEvents.TAG_DECK_CHANGED after a successful UTub-tag create", async () => {
    const { emit, AppEvents } = await import("../../../lib/event-bus.js");

    const response = {
      utubTag: { utubTagID: 5, tagString: "important" },
      tagCountsInUtub: 1,
    } as unknown as SuccessResponse<"createUtubTag">;
    const xhr = { status: 200 } as JQuery.jqXHR;
    const chainable = createMockJqXHRChainable({
      done: (callback: unknown) =>
        (callback as (r: unknown, t: unknown, x: unknown) => void)(
          response,
          "success",
          xhr,
        ),
    });
    vi.mocked(ajaxCall).mockReturnValue(chainable);

    // Open the create input (wires up the submit listener), type a tag, then
    // click submit — which fires the ajax .done() success callback synchronously
    // via the chainable above, driving createUTubTagSuccess. Mirrors the
    // URL_DECK_CHANGED precedent in
    // frontend/home/urls/cards/__tests__/create.test.ts:416.
    setupOpenCreateUTubTagEventListeners(1);
    $("#utubTagBtnCreate").trigger("click.createUTubTag");
    $("#utubTagCreate").val("important");
    $("#utubTagSubmitBtnCreate").trigger("click");

    expect(emit).toHaveBeenCalledWith(AppEvents.TAG_DECK_CHANGED);
  });
});
