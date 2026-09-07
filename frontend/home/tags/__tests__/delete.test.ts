import type { SuccessResponse } from "../../../types/api-helpers.d.ts";

import { createMockJqXHRChainable } from "../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall } from "../../../lib/ajax.js";
import { deleteUTubTagShowModal } from "../delete.js";

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
