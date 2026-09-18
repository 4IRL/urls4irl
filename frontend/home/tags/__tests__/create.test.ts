import type { SuccessResponse } from "../../../types/api-helpers.d.ts";

import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall } from "../../../lib/ajax.js";
import { bootstrap } from "../../../lib/globals.js";
import { setupOpenCreateUTubTagEventListeners } from "../create.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

// The ambient test-setup Bootstrap mock returns null from getInstance(), which
// would make the tooltip-hide/show guards silent no-ops. Override lib/globals.js
// with a shared tooltip instance so those guards can be asserted on.
const { tooltipInstance } = vi.hoisted(() => ({
  tooltipInstance: {
    setContent: vi.fn(),
    show: vi.fn(),
    hide: vi.fn(),
  },
}));

vi.mock("../../../lib/globals.js", async () => {
  const jquery = (await import("jquery")).default;
  return {
    $: jquery,
    jQuery: jquery,
    getInputValue: (input: string | JQuery) =>
      (typeof input === "string" ? jquery(input) : input).val() as string,
    bootstrap: {
      Tooltip: {
        getInstance: vi.fn(() => tooltipInstance),
        getOrCreateInstance: vi.fn(() => tooltipInstance),
      },
    },
  };
});

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

describe("createUTubTag form buttons - hover tooltip hide/restore", () => {
  beforeEach(() => {
    document.body.innerHTML = CREATE_UTUB_TAG_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  function openCreateUTubTagForm(): void {
    setupOpenCreateUTubTagEventListeners(1);
    $("#utubTagBtnCreate").trigger("click.createUTubTag");
    $("#utubTagCreate").val("important");
  }

  function mockCreateUTubTagFailure(
    responseJSON: Record<string, unknown>,
  ): void {
    const failXhr = createMockXhr({ status: 400, responseJSON });
    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable({
        fail: (callback: unknown) =>
          (callback as (xhr: JQuery.jqXHR) => void)(failXhr),
      }),
    );
  }

  it("hides the tooltip when the submit button is clicked", () => {
    vi.mocked(ajaxCall).mockReturnValue(createMockJqXHRChainable());

    openCreateUTubTagForm();
    $("#utubTagSubmitBtnCreate").trigger("click");

    expect(tooltipInstance.hide).toHaveBeenCalled();
    // Pins the `this` binding — the handler must target its own button.
    expect(vi.mocked(bootstrap.Tooltip.getInstance)).toHaveBeenCalledWith(
      document.getElementById("utubTagSubmitBtnCreate"),
    );
  });

  it("hides the tooltip when the cancel button is clicked", () => {
    openCreateUTubTagForm();
    $("#utubTagCancelBtnCreate").trigger("click");

    expect(tooltipInstance.hide).toHaveBeenCalled();
    expect(vi.mocked(bootstrap.Tooltip.getInstance)).toHaveBeenCalledWith(
      document.getElementById("utubTagCancelBtnCreate"),
    );
    expect($("#createUTubTagWrap").hasClass("hidden")).toBe(true);
  });

  it("does not throw on submit or cancel when no tooltip instance exists", () => {
    // Touch devices never construct a Tooltip, so getInstance() returns null and
    // the `?.` guard must no-op without breaking the tag-create flow.
    vi.mocked(bootstrap.Tooltip.getInstance)
      .mockReturnValueOnce(null)
      .mockReturnValueOnce(null);
    vi.mocked(ajaxCall).mockReturnValue(createMockJqXHRChainable());

    openCreateUTubTagForm();

    expect(() => $("#utubTagSubmitBtnCreate").trigger("click")).not.toThrow();
    expect(() => $("#utubTagCancelBtnCreate").trigger("click")).not.toThrow();
    expect(tooltipInstance.hide).not.toHaveBeenCalled();
  });

  it("restores the submit button tooltip on a 400 with field errors while the cursor is still on the button", () => {
    mockCreateUTubTagFailure({
      errors: { tagString: ["Tag already exists in UTub"] },
    });
    openCreateUTubTagForm();
    const submitBtn = document.getElementById("utubTagSubmitBtnCreate")!;
    // jsdom has no pointer, so `:hover` never matches on its own.
    vi.spyOn(submitBtn, "matches").mockReturnValue(true);

    $("#utubTagSubmitBtnCreate").trigger("click");

    expect(tooltipInstance.hide).toHaveBeenCalled();
    expect(tooltipInstance.show).toHaveBeenCalled();
    expect(vi.mocked(bootstrap.Tooltip.getInstance)).toHaveBeenCalledWith(
      submitBtn,
    );
  });

  it("restores the submit button tooltip on a 400 carrying only a message", () => {
    mockCreateUTubTagFailure({ message: "Tag already exists in UTub" });
    openCreateUTubTagForm();
    const submitBtn = document.getElementById("utubTagSubmitBtnCreate")!;
    vi.spyOn(submitBtn, "matches").mockReturnValue(true);

    $("#utubTagSubmitBtnCreate").trigger("click");

    expect(tooltipInstance.show).toHaveBeenCalled();
  });

  it("does not restore the submit button tooltip when the cursor has left the button", () => {
    // The same 400 is reachable from the Enter-key submit path, where re-showing
    // would strand a bubble with no mouseleave to come.
    mockCreateUTubTagFailure({
      errors: { tagString: ["Tag already exists in UTub"] },
    });
    openCreateUTubTagForm();

    $("#utubTagSubmitBtnCreate").trigger("click");

    expect(tooltipInstance.hide).toHaveBeenCalled();
    expect(tooltipInstance.show).not.toHaveBeenCalled();
  });
});
