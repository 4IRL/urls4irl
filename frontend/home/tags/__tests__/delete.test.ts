import type { SuccessResponse } from "../../../types/api-helpers.d.ts";

import { createMockJqXHRChainable } from "../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall } from "../../../lib/ajax.js";
import { deleteUTubTagShowModal } from "../delete.js";
import { bootstrap } from "../../../lib/globals.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

// The ambient test-setup Bootstrap mock returns null from getInstance(), which
// would make the tooltip-hide guard a silent no-op. Override lib/globals.js with
// a shared tooltip instance so the guard can be asserted on.
const { tooltipInstance, globalsMock } = await vi.hoisted(async () => {
  const { mockGlobalsWithTooltipInstance } =
    await import("../../../__tests__/helpers/mock-globals.js");
  return await mockGlobalsWithTooltipInstance();
});

vi.mock("../../../lib/globals.js", () => globalsMock);

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

vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ tags: [], urls: [], selectedTagIDs: [] })),
  setState: vi.fn(),
}));

const $ = window.jQuery;

const DELETE_TAG_HTML = `
  <div id="confirmModal">
    <div id="confirmModalTitle"></div>
    <div id="confirmModalBody"></div>
    <button id="modalDismiss"></button>
    <button id="modalSubmit"></button>
    <div id="modalRedirect"></div>
  </div>
  <div id="HomeModalAlertBanner"></div>
`;

describe("tags/delete — notifies the onboarding nudge system", () => {
  beforeEach(() => {
    document.body.innerHTML = DELETE_TAG_HTML;
    vi.clearAllMocks();
    ($.fn as unknown as Record<string, unknown>).modal = function (
      this: JQuery,
    ) {
      return this;
    };
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("emits AppEvents.TAG_DECK_CHANGED after a successful tag delete", async () => {
    const { emit, AppEvents } = await import("../../../lib/event-bus.js");

    const response = {
      utubTag: { utubTagID: 7 },
      utubUrlIDs: [10, 11],
    } as unknown as SuccessResponse<"deleteUtubTag">;
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

    // Open the confirm modal, then drive the confirm-button click, which fires
    // the ajax .done() success callback synchronously via the chainable above.
    deleteUTubTagShowModal(1, 7, "important");
    $("#modalSubmit").trigger("click");

    expect(emit).toHaveBeenCalledWith(AppEvents.TAG_DECK_CHANGED);
  });
});

describe("tags/delete — hides the #unselectAllTagFilters hover tooltip", () => {
  const originalFadeOut = ($.fn as unknown as Record<string, unknown>).fadeOut;

  beforeEach(() => {
    document.body.innerHTML = `
      ${DELETE_TAG_HTML}
      <div id="listTags">
        <div class="tagFilter" data-utub-tag-id="7">important</div>
      </div>
      <button id="utubTagBtnUpdateAllOpen"></button>
      <button id="unselectAllTagFilters" data-bs-toggle="tooltip"></button>
      <div id="utubTagCloseUpdateTagBtnContainer"></div>
      <div id="utubTagStandardBtns"></div>
    `;
    vi.clearAllMocks();
    ($.fn as unknown as Record<string, unknown>).modal = function (
      this: JQuery,
    ) {
      return this;
    };
    // Fire the post-fade callback synchronously so the "no tags left" branch runs
    ($.fn as unknown as Record<string, unknown>).fadeOut = function (
      this: JQuery,
      _duration: unknown,
      callback?: () => void,
    ) {
      if (typeof callback === "function") callback();
      return this;
    };
  });

  afterEach(() => {
    ($.fn as unknown as Record<string, unknown>).fadeOut = originalFadeOut;
    document.body.innerHTML = "";
  });

  it("hides the tooltip before hiding the button when the last tag is deleted", () => {
    const response = {
      utubTag: { utubTagID: 7 },
      utubUrlIDs: [],
    } as unknown as SuccessResponse<"deleteUtubTag">;
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

    deleteUTubTagShowModal(1, 7, "important");
    $("#modalSubmit").trigger("click");

    expect($(".tagFilter").length).toBe(0);
    expect(tooltipInstance.hide).toHaveBeenCalled();
  });

  it("still hides the button and does not throw when no tooltip instance exists", () => {
    // Touch devices never construct a Tooltip, so getInstance() returns null and
    // the `?.` guard must no-op without breaking the last-tag cleanup.
    vi.mocked(bootstrap.Tooltip.getInstance).mockReturnValueOnce(null);

    const response = {
      utubTag: { utubTagID: 7 },
      utubUrlIDs: [],
    } as unknown as SuccessResponse<"deleteUtubTag">;
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

    deleteUTubTagShowModal(1, 7, "important");

    expect(() => $("#modalSubmit").trigger("click")).not.toThrow();

    expect(tooltipInstance.hide).not.toHaveBeenCalled();
    expect($(".tagFilter").length).toBe(0);
    expect($("#unselectAllTagFilters").hasClass("hidden")).toBe(true);
  });
});

describe("tags/delete — keeps the #TagDeckCount tag total in sync", () => {
  const originalFadeOut = ($.fn as unknown as Record<string, unknown>).fadeOut;

  beforeEach(() => {
    document.body.innerHTML = `
      ${DELETE_TAG_HTML}
      <span id="TagDeckCount">(2)</span>
      <div id="listTags">
        <div class="tagFilter" data-utub-tag-id="7">important</div>
        <div class="tagFilter" data-utub-tag-id="8">urgent</div>
      </div>
      <button id="utubTagBtnUpdateAllOpen"></button>
      <button id="unselectAllTagFilters" data-bs-toggle="tooltip"></button>
      <div id="utubTagCloseUpdateTagBtnContainer"></div>
      <div id="utubTagStandardBtns"></div>
    `;
    vi.clearAllMocks();
    ($.fn as unknown as Record<string, unknown>).modal = function (
      this: JQuery,
    ) {
      return this;
    };
    // Fire the post-fade callback synchronously — the row removal (and the
    // count refresh that follows it) lives inside fadeOut's callback.
    ($.fn as unknown as Record<string, unknown>).fadeOut = function (
      this: JQuery,
      _duration: unknown,
      callback?: () => void,
    ) {
      if (typeof callback === "function") callback();
      return this;
    };
  });

  afterEach(() => {
    ($.fn as unknown as Record<string, unknown>).fadeOut = originalFadeOut;
    document.body.innerHTML = "";
  });

  it("drops the count to the surviving tag total after a delete", () => {
    const response = {
      utubTag: { utubTagID: 7 },
      utubUrlIDs: [],
    } as unknown as SuccessResponse<"deleteUtubTag">;
    const xhr = { status: 200 } as JQuery.jqXHR;
    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable({
        done: (callback: unknown) =>
          (callback as (r: unknown, t: unknown, x: unknown) => void)(
            response,
            "success",
            xhr,
          ),
      }),
    );

    deleteUTubTagShowModal(1, 7, "important");
    $("#modalSubmit").trigger("click");

    expect($("#listTags > .tagFilter").length).toBe(1);
    expect($("#TagDeckCount").text()).toBe("(1)");
  });
});
