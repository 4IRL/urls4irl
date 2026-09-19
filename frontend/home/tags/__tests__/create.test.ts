import type { SuccessResponse } from "../../../types/api-helpers.d.ts";

import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall } from "../../../lib/ajax.js";
import {
  hideTooltip,
  restoreTooltipIfStillTargeted,
} from "../../../lib/tooltips.js";
import { setupOpenCreateUTubTagEventListeners } from "../create.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

// Both tooltip helpers this module reaches for are stubbed, so these tests
// assert the delegation (which element each handler acts on) rather than
// Bootstrap's internals. Their own behaviour — the still-targeted guard
// (`:hover` or `:focus-visible`) and the deferral past Bootstrap's fade for
// restoreTooltipIfStillTargeted, the null-instance no-op for hideTooltip — is
// covered in lib/__tests__/tooltips.test.ts.
//
// Deliberately a full stub, not a partial mock. Measured here: a factory that
// pulls the real module in via importOriginal()/importActual() leaves the
// CONSUMING module bound to the actual tooltips module, so the
// restoreTooltipIfStillTargeted override silently stops taking effect (the real
// one then early-returns on its `:hover` guard and the assertions below see
// zero calls). Unlike the event-bus partial mock further down, lib/tooltips.js
// imports the lib/globals.js this file also mocks.
vi.mock("../../../lib/tooltips.js", () => ({
  hideTooltip: vi.fn(),
  restoreTooltipIfStillTargeted: vi.fn(),
}));

// lib/globals.js is replaced wholesale (jQuery + getInputValue + Bootstrap), so
// the Bootstrap stub has to hand back a usable Tooltip instance rather than the
// ambient test-setup mock's null — anything in this module's graph that still
// reaches Bootstrap directly would otherwise silently no-op.
const { globalsMock } = await vi.hoisted(async () => {
  const { mockGlobalsWithTooltipInstance } = await import(
    "../../../__tests__/helpers/mock-globals.js"
  );
  return await mockGlobalsWithTooltipInstance();
});

vi.mock("../../../lib/globals.js", () => globalsMock);

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

    // Pins the `this` binding — the handler must target its own button.
    expect(vi.mocked(hideTooltip)).toHaveBeenCalledWith(
      document.getElementById("utubTagSubmitBtnCreate"),
    );
  });

  it("hides the tooltip when the cancel button is clicked", () => {
    openCreateUTubTagForm();
    $("#utubTagCancelBtnCreate").trigger("click");

    expect(vi.mocked(hideTooltip)).toHaveBeenCalledWith(
      document.getElementById("utubTagCancelBtnCreate"),
    );
    expect($("#createUTubTagWrap").hasClass("hidden")).toBe(true);
  });

  it("routes the restore through restoreTooltipIfStillTargeted on a 400 with field errors", () => {
    mockCreateUTubTagFailure({
      errors: { tagString: ["Tag already exists in UTub"] },
    });
    openCreateUTubTagForm();
    const submitBtn = document.getElementById("utubTagSubmitBtnCreate")!;

    $("#utubTagSubmitBtnCreate").trigger("click");

    expect(vi.mocked(hideTooltip)).toHaveBeenCalled();
    expect(vi.mocked(restoreTooltipIfStillTargeted)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(restoreTooltipIfStillTargeted)).toHaveBeenCalledWith(submitBtn);
  });

  it("routes the restore through restoreTooltipIfStillTargeted on a 400 carrying only a message", () => {
    mockCreateUTubTagFailure({ message: "Tag already exists in UTub" });
    openCreateUTubTagForm();
    const submitBtn = document.getElementById("utubTagSubmitBtnCreate")!;

    $("#utubTagSubmitBtnCreate").trigger("click");

    expect(vi.mocked(restoreTooltipIfStillTargeted)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(restoreTooltipIfStillTargeted)).toHaveBeenCalledWith(submitBtn);
  });

  it("does not attempt a restore on a successful submit", () => {
    // Nothing to restore: success closes the form, so the hidden tooltip should
    // stay hidden rather than be re-shown over a button that is going away.
    vi.mocked(ajaxCall).mockReturnValue(createMockJqXHRChainable());
    openCreateUTubTagForm();

    $("#utubTagSubmitBtnCreate").trigger("click");

    expect(vi.mocked(hideTooltip)).toHaveBeenCalled();
    expect(vi.mocked(restoreTooltipIfStillTargeted)).not.toHaveBeenCalled();
  });
});
