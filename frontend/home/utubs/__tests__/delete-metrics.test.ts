import { createMockJqXHRChainable } from "../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall } from "../../../lib/ajax.js";
import { setDeleteEventListeners } from "../delete.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../deck.js", () => ({
  resetUTubDeckIfNoUTubs: vi.fn(),
  hideInputsAndUpdateUTubDeck: vi.fn(),
}));

vi.mock("../utils.js", () => ({ getNumOfUTubs: vi.fn(() => 0) }));
vi.mock("../search.js", () => ({ resetUTubSearch: vi.fn() }));
vi.mock("../../btns-forms.js", () => ({ hideInputs: vi.fn() }));
vi.mock("../../init.js", () => ({ setUIWhenNoUTubSelected: vi.fn() }));
vi.mock("../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  setMobileUIWhenUTubNotSelectedOrUTubDeleted: vi.fn(),
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
  getState: vi.fn(() => ({ utubs: [] })),
  setState: vi.fn(),
}));

const $ = window.jQuery;

const DELETE_UTUB_HTML = `
  <div id="confirmModal">
    <div id="confirmModalTitle"></div>
    <div id="confirmModalBody"></div>
    <button id="modalDismiss"></button>
    <button id="modalSubmit"></button>
    <div id="modalRedirect"></div>
  </div>
  <button id="utubBtnDelete"></button>
`;

describe("delete metrics — UI_UTUB_DELETE_OPEN / _CONFIRM / _CANCEL", () => {
  beforeEach(() => {
    document.body.innerHTML = DELETE_UTUB_HTML;
    vi.clearAllMocks();
    ($.fn as unknown as Record<string, unknown>).modal = function (
      this: JQuery,
    ) {
      return this;
    };
    // ajaxCall must return a chainable so deleteUTub doesn't throw when
    // chaining .done/.fail. The success path is irrelevant to these tests —
    // we only care that the modal-submit click runs the emit before the
    // AJAX call.
    vi.mocked(ajaxCall).mockReturnValue(createMockJqXHRChainable());
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("emits ui_utub_delete_open when the delete button opens the modal", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setDeleteEventListeners(42);
    $("#utubBtnDelete").trigger("click.deleteUTub");

    expect(emit).toHaveBeenCalledWith("ui_utub_delete_open");
  });

  it("emits ui_utub_delete_confirm when the modal submit button is clicked", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setDeleteEventListeners(42);
    $("#utubBtnDelete").trigger("click.deleteUTub");
    vi.mocked(emit).mockClear();

    $("#modalSubmit").trigger("click");

    expect(emit).toHaveBeenCalledWith("ui_utub_delete_confirm");
  });

  it("emits ui_utub_delete_cancel when the modal is dismissed without confirming", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setDeleteEventListeners(42);
    $("#utubBtnDelete").trigger("click.deleteUTub");
    vi.mocked(emit).mockClear();

    $("#confirmModal").trigger("hidden.bs.modal.utubDelete");

    expect(emit).toHaveBeenCalledWith("ui_utub_delete_cancel");
  });

  it("does not emit ui_utub_delete_cancel when the modal hides after confirm", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setDeleteEventListeners(42);
    $("#utubBtnDelete").trigger("click.deleteUTub");
    $("#modalSubmit").trigger("click");
    vi.mocked(emit).mockClear();

    $("#confirmModal").trigger("hidden.bs.modal.utubDelete");

    expect(emit).not.toHaveBeenCalledWith("ui_utub_delete_cancel");
  });

  it("resets confirmed flag across multiple modal opens (cancel after re-open emits cancel)", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setDeleteEventListeners(42);
    $("#utubBtnDelete").trigger("click.deleteUTub");
    $("#modalSubmit").trigger("click");
    $("#confirmModal").trigger("hidden.bs.modal.utubDelete");

    $("#utubBtnDelete").trigger("click.deleteUTub");
    vi.mocked(emit).mockClear();

    $("#confirmModal").trigger("hidden.bs.modal.utubDelete");

    expect(emit).toHaveBeenCalledWith("ui_utub_delete_cancel");
  });
});
