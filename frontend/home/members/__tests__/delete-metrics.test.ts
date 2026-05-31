import { UI_EVENTS } from "../../../types/metrics-events.js";
import { createMockJqXHRChainable } from "../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall } from "../../../lib/ajax.js";
import { removeMemberShowModal } from "../delete.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../deck.js", () => ({ setMemberDeckForUTub: vi.fn() }));
vi.mock("../../btns-forms.js", () => ({ hideInputs: vi.fn() }));
vi.mock("../../urls/cards/selection.js", () => ({ deselectAllURLs: vi.fn() }));
vi.mock("../../utubs/utils.js", () => ({ getNumOfUTubs: vi.fn(() => 1) }));
vi.mock("../../utubs/deck.js", () => ({
  resetUTubDeckIfNoUTubs: vi.fn(),
  hideInputsAndUpdateUTubDeck: vi.fn(),
}));
vi.mock("../../init.js", () => ({ setUIWhenNoUTubSelected: vi.fn() }));

vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ members: [] })),
  setState: vi.fn(),
}));

const $ = window.jQuery;

const MEMBER_MODAL_HTML = `
  <div id="confirmModal">
    <div id="confirmModalTitle"></div>
    <div id="confirmModalBody"></div>
    <button id="modalDismiss"></button>
    <button id="modalSubmit"></button>
    <div id="modalRedirect"></div>
  </div>
`;

describe("delete-metrics — UI_MEMBER_REMOVE_* / UI_MEMBER_LEAVE_*", () => {
  beforeEach(() => {
    document.body.innerHTML = MEMBER_MODAL_HTML;
    vi.clearAllMocks();
    ($.fn as unknown as Record<string, unknown>).modal = function (
      this: JQuery,
    ) {
      return this;
    };
    // ajaxCall must return a chainable so removeMember doesn't throw when
    // chaining .done/.fail after the modal submit emit runs.
    vi.mocked(ajaxCall).mockReturnValue(createMockJqXHRChainable());
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  describe("creator path (isCreator === true)", () => {
    it("emits ui_member_remove_open when the modal is shown", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");

      removeMemberShowModal(5, true, 1);

      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_MEMBER_REMOVE_OPEN,
      });
    });

    it("emits ui_member_remove_confirm when the modal submit is clicked", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");

      removeMemberShowModal(5, true, 1);
      vi.mocked(emit).mockClear();

      $("#modalSubmit").trigger("click");

      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_MEMBER_REMOVE_CONFIRM,
      });
    });

    it("emits ui_member_remove_cancel when the modal is dismissed without confirming", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");

      removeMemberShowModal(5, true, 1);
      vi.mocked(emit).mockClear();

      $("#confirmModal").trigger("hidden.bs.modal.memberAction");

      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_MEMBER_REMOVE_CANCEL,
      });
    });

    it("does not emit ui_member_remove_cancel when the modal hides after confirm", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");

      removeMemberShowModal(5, true, 1);
      $("#modalSubmit").trigger("click");
      vi.mocked(emit).mockClear();

      $("#confirmModal").trigger("hidden.bs.modal.memberAction");

      expect(emit).not.toHaveBeenCalledWith({
        event: UI_EVENTS.UI_MEMBER_REMOVE_CANCEL,
      });
    });
  });

  describe("leave path (isCreator === false)", () => {
    it("emits ui_member_leave_open when the modal is shown", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");

      removeMemberShowModal(5, false, 1);

      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_MEMBER_LEAVE_OPEN,
      });
    });

    it("emits ui_member_leave_confirm when the modal submit is clicked", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");

      removeMemberShowModal(5, false, 1);
      vi.mocked(emit).mockClear();

      $("#modalSubmit").trigger("click");

      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_MEMBER_LEAVE_CONFIRM,
      });
    });

    it("emits ui_member_leave_cancel when the modal is dismissed without confirming", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");

      removeMemberShowModal(5, false, 1);
      vi.mocked(emit).mockClear();

      $("#confirmModal").trigger("hidden.bs.modal.memberAction");

      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_MEMBER_LEAVE_CANCEL,
      });
    });

    it("does not emit ui_member_leave_cancel when the modal hides after confirm", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");

      removeMemberShowModal(5, false, 1);
      $("#modalSubmit").trigger("click");
      vi.mocked(emit).mockClear();

      $("#confirmModal").trigger("hidden.bs.modal.memberAction");

      expect(emit).not.toHaveBeenCalledWith({
        event: UI_EVENTS.UI_MEMBER_LEAVE_CANCEL,
      });
    });
  });

  describe("flag reset across multiple opens", () => {
    it("resets the confirmed flag so a cancel after re-open emits the cancel event", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");

      removeMemberShowModal(5, true, 1);
      $("#modalSubmit").trigger("click");
      $("#confirmModal").trigger("hidden.bs.modal.memberAction");

      removeMemberShowModal(5, true, 1);
      vi.mocked(emit).mockClear();

      $("#confirmModal").trigger("hidden.bs.modal.memberAction");

      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_MEMBER_REMOVE_CANCEL,
      });
    });

    it("uses the latest isCreator value when emitting cancel after a re-open with different role", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");

      // First open with isCreator=true; dismiss to satisfy hidden listener
      removeMemberShowModal(5, true, 1);
      $("#confirmModal").trigger("hidden.bs.modal.memberAction");

      // Re-open with isCreator=false; cancel should emit leave_cancel
      removeMemberShowModal(5, false, 1);
      vi.mocked(emit).mockClear();
      $("#confirmModal").trigger("hidden.bs.modal.memberAction");

      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_MEMBER_LEAVE_CANCEL,
      });
      expect(emit).not.toHaveBeenCalledWith({
        event: UI_EVENTS.UI_MEMBER_REMOVE_CANCEL,
      });
    });
  });
});
