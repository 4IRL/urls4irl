import { createMockJqXHRChainable } from "../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall } from "../../../lib/ajax.js";
import { learnPolicyOff } from "../../utubs/policy.js";
import { isMobile } from "../../mobile.js";
import { getRefusalOwnedMessage } from "../policy-banner.js";
import { isTagSheetOpen } from "../sheet.js";
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
  return { ...actual, emit: vi.fn() };
});

vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ tags: [], urls: [], selectedTagIDs: [] })),
  setState: vi.fn(),
}));

vi.mock("../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
}));

vi.mock("../sheet.js", () => ({
  isTagSheetOpen: vi.fn(() => false),
}));

vi.mock("../../utubs/policy.js", () => ({
  learnPolicyOff: vi.fn(() => true),
}));

const $ = window.jQuery;

const DELETE_MESSAGE =
  "Only the owner and co-owners can delete tags in this UTub.";
const UTUB_ID = 7;
const TAG_ID = 3;

const BANNER = "#URLDeckErrorIndicator";

const DELETE_HTML = `
  <div id="URLDeckErrorIndicator"></div>
  <div id="confirmModal">
    <div id="confirmModalTitle"></div>
    <div id="confirmModalBody"></div>
    <button id="modalDismiss"></button>
    <button id="modalSubmit"></button>
    <div id="modalRedirect"></div>
  </div>
  <div id="HomeModalAlertBanner"></div>
  <button id="utubTagBtnUpdateAllOpen"></button>
`;

function failWith(
  status: number,
  responseJSON?: Record<string, unknown>,
): void {
  const xhr = {
    status,
    responseJSON,
    getResponseHeader: vi.fn(() => "application/json"),
  } as unknown as JQuery.jqXHR;
  vi.mocked(ajaxCall).mockReturnValue(
    createMockJqXHRChainable({
      fail: (callback: unknown) => (callback as (x: unknown) => void)(xhr),
    }),
  );
}

describe("deleteUTubTagFail — tag policy refusal (errorCode 4 or 5)", () => {
  let modalSpy: ReturnType<typeof vi.fn>;
  let reloadSpy: ReturnType<typeof vi.fn>;
  const originalLocation = window.location;

  function confirmDelete(): void {
    deleteUTubTagShowModal(UTUB_ID, TAG_ID, "important");
    modalSpy.mockClear();
    $("#modalSubmit").trigger("click");
  }

  beforeEach(() => {
    document.body.innerHTML = DELETE_HTML;
    vi.clearAllMocks();
    vi.mocked(isMobile).mockReturnValue(false);
    vi.mocked(isTagSheetOpen).mockReturnValue(false);
    modalSpy = vi.fn(function (this: JQuery) {
      return this;
    });
    ($.fn as unknown as Record<string, unknown>).modal = modalSpy;
    reloadSpy = vi.fn();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...originalLocation, reload: reloadSpy },
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: originalLocation,
    });
    document.body.innerHTML = "";
  });

  it.each([
    [4, "tags.members_can_tag"],
    [5, "tags.members_can_delete_tags"],
  ])(
    "errorCode %i closes the modal, learns %s, focuses the pencil and shows the reason once",
    (errorCode, key) => {
      failWith(403, { errorCode, message: DELETE_MESSAGE });
      const order: string[] = [];
      modalSpy.mockImplementation(function (this: JQuery, arg?: unknown) {
        if (arg === "hide") order.push("close");
        return this;
      });
      vi.mocked(learnPolicyOff).mockImplementation(() => {
        order.push($(BANNER).text() === "" ? "learn" : "banner-too-early");
        return true;
      });

      deleteUTubTagShowModal(UTUB_ID, TAG_ID, "important");
      order.length = 0;
      $("#modalSubmit").trigger("click");

      expect(order).toEqual(["close", "learn"]);
      expect(learnPolicyOff).toHaveBeenCalledWith({ utubID: UTUB_ID, key });
      const pencil = document.getElementById("utubTagBtnUpdateAllOpen");
      expect($(BANNER).text()).toBe(DELETE_MESSAGE);
      expect($(BANNER).hasClass("URLDeckErrorIndicatorShow")).toBe(true);
      expect(document.activeElement).toBe(pencil);
      expect(reloadSpy).not.toHaveBeenCalled();
      expect($("#HomeModalAlertBanner").text()).toBe("");
    },
  );

  it("owns the refusal message during the learn step (store notification)", () => {
    failWith(403, { errorCode: 5 });
    let seenMessage: string | null = null;
    vi.mocked(learnPolicyOff).mockImplementation(() => {
      seenMessage = getRefusalOwnedMessage();
      return true;
    });

    confirmDelete();

    expect(seenMessage).toBe(DELETE_MESSAGE);
    expect(getRefusalOwnedMessage()).toBeNull();
  });

  it("uses the pencil's note, not the deck banner, with the sheet open", () => {
    vi.mocked(isTagSheetOpen).mockReturnValue(true);
    failWith(403, { errorCode: 5 });

    confirmDelete();

    // The control note (Step 6) replaces the deck banner while the sheet is open.
    expect($(BANNER).text()).toBe("");
  });

  it("skips programmatic focus on mobile when the sheet closed mid-request", () => {
    vi.mocked(isMobile).mockReturnValue(true);
    vi.mocked(isTagSheetOpen).mockReturnValue(false);
    const elsewhere = document.createElement("button");
    document.body.appendChild(elsewhere);
    elsewhere.focus();
    failWith(403, { errorCode: 5 });
    const pencil = document.getElementById(
      "utubTagBtnUpdateAllOpen",
    ) as HTMLElement;
    const focusSpy = vi.spyOn(pencil, "focus");

    confirmDelete();

    expect(focusSpy).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(elsewhere);
    expect($(BANNER).text()).toBe(DELETE_MESSAGE);
  });

  it("keeps the reload banner for a 403 with another errorCode", () => {
    failWith(403, { errorCode: 99 });

    confirmDelete();

    expect(learnPolicyOff).not.toHaveBeenCalled();
    expect($(BANNER).text()).toBe("");
    expect($("#HomeModalAlertBanner").text()).toContain("reload the UTub");
  });

  it("keeps the reload banner for a 404", () => {
    failWith(404, { message: "gone" });

    confirmDelete();

    expect($(BANNER).text()).toBe("");
    expect($("#HomeModalAlertBanner").text()).toContain("reload the UTub");
  });
});
