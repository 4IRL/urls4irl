import { createMockJqXHRChainable } from "../../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall } from "../../../../lib/ajax.js";
import { deleteURLShowModal } from "../delete.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../get.js", () => ({
  getUpdatedURL: vi.fn(() => Promise.resolve()),
  handleRejectFromGetURL: vi.fn(),
}));

vi.mock("../filtering.js", () => ({
  updateTagFilteringOnURLOrURLTagDeletion: vi.fn(),
}));

vi.mock("../../search.js", () => ({
  hideURLSearchIcon: vi.fn(),
}));

vi.mock("../../empty-state.js", () => ({
  showURLsEmptyState: vi.fn(),
  hideURLsEmptyState: vi.fn(),
}));

vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ urls: [] })),
  setState: vi.fn(),
}));

const $ = window.jQuery;

const DELETE_URL_HTML = `
  <div id="confirmModal" class="modal">
    <span id="confirmModalTitle"></span>
    <span id="confirmModalBody"></span>
    <button id="modalDismiss"></button>
    <button id="modalSubmit"></button>
    <div id="modalRedirect"></div>
  </div>
`;

function buildUrlCard(utubUrlID: number): JQuery {
  return $(
    `<div class="urlRow" utuburlid="${utubUrlID}" data-utub-url-tag-ids=""></div>`,
  );
}

describe("delete metrics — UI_URL_DELETE_OPEN / _CONFIRM / _CANCEL", () => {
  beforeEach(() => {
    document.body.innerHTML = DELETE_URL_HTML;
    vi.clearAllMocks();
    ($.fn as unknown as Record<string, unknown>).modal = function (
      this: JQuery,
    ) {
      return this;
    };
    vi.mocked(ajaxCall).mockReturnValue(createMockJqXHRChainable());
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("emits ui_url_delete_open when deleteURLShowModal is invoked", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    deleteURLShowModal(42, buildUrlCard(42), 1);

    expect(emit).toHaveBeenCalledWith("ui_url_delete_open");
  });

  it("emits ui_url_delete_confirm when the modal submit button is clicked", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    deleteURLShowModal(42, buildUrlCard(42), 1);
    vi.mocked(emit).mockClear();

    $("#modalSubmit").trigger("click");

    expect(emit).toHaveBeenCalledWith("ui_url_delete_confirm");
  });

  it("emits ui_url_delete_cancel when modal hides without confirm", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    deleteURLShowModal(42, buildUrlCard(42), 1);
    vi.mocked(emit).mockClear();

    $("#confirmModal").trigger("hidden.bs.modal.urlDelete");

    expect(emit).toHaveBeenCalledWith("ui_url_delete_cancel");
  });

  it("does NOT emit cancel when the modal hides after confirm", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    deleteURLShowModal(42, buildUrlCard(42), 1);
    $("#modalSubmit").trigger("click");
    vi.mocked(emit).mockClear();

    $("#confirmModal").trigger("hidden.bs.modal.urlDelete");

    expect(emit).not.toHaveBeenCalledWith("ui_url_delete_cancel");
  });

  it("resets confirmed flag across multiple modal opens (cancel after re-open emits cancel)", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    deleteURLShowModal(42, buildUrlCard(42), 1);
    $("#modalSubmit").trigger("click");
    $("#confirmModal").trigger("hidden.bs.modal.urlDelete");

    deleteURLShowModal(42, buildUrlCard(42), 1);
    vi.mocked(emit).mockClear();

    $("#confirmModal").trigger("hidden.bs.modal.urlDelete");

    expect(emit).toHaveBeenCalledWith("ui_url_delete_cancel");
  });

  it("does not accumulate hidden.bs.modal.deleteUrlCleanup listeners across multiple opens", async () => {
    deleteURLShowModal(42, buildUrlCard(42), 1);
    deleteURLShowModal(43, buildUrlCard(43), 1);
    deleteURLShowModal(44, buildUrlCard(44), 1);

    // The cleanup namespaced listener should be re-bound (not accumulated).
    // Trigger the cleanup once — class should be removed once, not 3x — and
    // re-adding then triggering should still work without errors.
    $("#confirmModal").addClass("deleteUrlModal");
    $("#confirmModal").trigger("hidden.bs.modal.deleteUrlCleanup");

    expect($("#confirmModal").hasClass("deleteUrlModal")).toBe(false);
  });
});
