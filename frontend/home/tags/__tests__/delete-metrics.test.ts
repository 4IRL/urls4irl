import { UI_EVENTS } from "../../../lib/metrics-events.js";
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

describe("tags/delete metrics — UI_TAG_DELETE_OPEN / _CONFIRM / _CANCEL (scope:utub)", () => {
  beforeEach(() => {
    document.body.innerHTML = DELETE_TAG_HTML;
    vi.clearAllMocks();
    ($.fn as unknown as Record<string, unknown>).modal = function (
      this: JQuery,
    ) {
      return this;
    };
    // The ajaxCall mock returns a chainable so deleteUTubTag doesn't throw when
    // chaining .done/.fail after the confirm-button click.
    vi.mocked(ajaxCall).mockReturnValue(createMockJqXHRChainable());
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("emits ui_tag_delete_open with scope:utub when the modal opens", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    deleteUTubTagShowModal(1, 7, "important");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_TAG_DELETE_OPEN,
      scope: "utub",
    });
  });

  it("emits ui_tag_delete_confirm with scope:utub when the modal submit button is clicked", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    deleteUTubTagShowModal(1, 7, "important");
    vi.mocked(emit).mockClear();

    $("#modalSubmit").trigger("click");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_TAG_DELETE_CONFIRM,
      scope: "utub",
    });
  });

  it("emits ui_tag_delete_cancel with scope:utub when the modal hides without confirm", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    deleteUTubTagShowModal(1, 7, "important");
    vi.mocked(emit).mockClear();

    $("#confirmModal").trigger("hidden.bs.modal.tagDelete");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_TAG_DELETE_CANCEL,
      scope: "utub",
    });
  });

  it("does not emit cancel when the modal hides after confirm", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    deleteUTubTagShowModal(1, 7, "important");
    $("#modalSubmit").trigger("click");
    vi.mocked(emit).mockClear();

    $("#confirmModal").trigger("hidden.bs.modal.tagDelete");

    expect(emit).not.toHaveBeenCalledWith({
      event: UI_EVENTS.UI_TAG_DELETE_CANCEL,
      scope: "utub",
    });
  });

  it("resets confirmed flag across multiple modal opens (cancel after re-open emits cancel)", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    deleteUTubTagShowModal(1, 7, "important");
    $("#modalSubmit").trigger("click");
    $("#confirmModal").trigger("hidden.bs.modal.tagDelete");

    deleteUTubTagShowModal(1, 8, "another");
    vi.mocked(emit).mockClear();

    $("#confirmModal").trigger("hidden.bs.modal.tagDelete");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_TAG_DELETE_CANCEL,
      scope: "utub",
    });
  });
});
