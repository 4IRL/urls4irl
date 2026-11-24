import { createMockJqXHRChainable } from "../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall } from "../../../lib/ajax.js";
import { learnPolicyOff } from "../../utubs/policy.js";
import { isMobile } from "../../mobile.js";
import { getRefusalOwnedMessage } from "../policy-banner.js";
import { UTubTagErrorCodes } from "../../../types/error-codes.js";
import { isTagSheetOpen } from "../sheet.js";
import { setupOpenCreateUTubTagEventListeners } from "../create.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../../../lib/tooltips.js", () => ({
  hideTooltip: vi.fn(),
  restoreTooltipIfStillTargeted: vi.fn(),
}));

vi.mock("../../../lib/event-bus.js", async () => {
  const actual = await vi.importActual<
    typeof import("../../../lib/event-bus.js")
  >("../../../lib/event-bus.js");
  return { ...actual, emit: vi.fn() };
});

vi.mock("../../utubs/utils.js", () => ({
  getNumOfUTubs: vi.fn(() => 1),
}));

vi.mock("../tags.js", () => ({
  syncTagCapState: vi.fn(),
  buildTagFilterInDeck: vi.fn(() => window.jQuery("<div></div>")),
}));

vi.mock("../display-settings.js", () => ({
  effectiveTagDisplaySettings: vi.fn(() => ({
    tagSort: "most_in_view",
    tagMatchMode: "all",
  })),
}));

vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ tags: [] })),
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

const CREATE_MESSAGE =
  "Only the owner and co-owners can create tags in this UTub.";
const UTUB_ID = 7;

const BANNER = "#URLDeckErrorIndicator";

const CREATE_HTML = `
  <div id="URLDeckErrorIndicator"></div>
  <button id="utubTagBtnCreate"></button>
  <div id="createUTubTagWrap" class="hidden"></div>
  <div id="listTags"></div>
  <div id="utubTagStandardBtns" class="hidden"></div>
  <input id="utubTagCreate" />
  <button id="utubTagSubmitBtnCreate"></button>
  <button id="utubTagCancelBtnCreate"></button>
  <div id="utubTagCreate-error"></div>
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

function submitCreate(): void {
  setupOpenCreateUTubTagEventListeners(UTUB_ID);
  $("#utubTagBtnCreate").trigger("click.createUTubTag");
  $("#utubTagCreate").val("newtag");
  $("#utubTagSubmitBtnCreate").trigger("click");
}

describe("createUTubTagFail — tag policy refusal (TAGGING_NOT_ALLOWED)", () => {
  let assignSpy: ReturnType<typeof vi.fn>;
  const originalLocation = window.location;

  beforeEach(() => {
    document.body.innerHTML = CREATE_HTML;
    vi.clearAllMocks();
    vi.mocked(isMobile).mockReturnValue(false);
    vi.mocked(isTagSheetOpen).mockReturnValue(false);
    assignSpy = vi.fn();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...originalLocation, assign: assignSpy },
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: originalLocation,
    });
    document.body.innerHTML = "";
  });

  it("closes the form, learns the key, focuses create and shows the reason once", () => {
    failWith(403, {
      errorCode: UTubTagErrorCodes.TAGGING_NOT_ALLOWED,
      message: CREATE_MESSAGE,
    });
    const order: string[] = [];
    vi.mocked(learnPolicyOff).mockImplementation(() => {
      order.push(
        $("#createUTubTagWrap").hasClass("hidden") ? "closed" : "open-at-learn",
      );
      order.push($(BANNER).text() === "" ? "learn" : "banner-too-early");
      return true;
    });

    submitCreate();

    expect(order).toEqual(["closed", "learn"]);
    expect(learnPolicyOff).toHaveBeenCalledWith({
      utubID: UTUB_ID,
      key: "tags.members_can_tag",
    });
    const createButton = document.getElementById("utubTagBtnCreate");
    expect($(BANNER).text()).toBe(CREATE_MESSAGE);
    expect($(BANNER).hasClass("URLDeckErrorIndicatorShow")).toBe(true);
    expect(document.activeElement).toBe(createButton);
    expect(assignSpy).not.toHaveBeenCalled();
  });

  it("owns the refusal message during the learn step (store notification)", () => {
    failWith(403, { errorCode: UTubTagErrorCodes.TAGGING_NOT_ALLOWED });
    let seenMessage: string | null = null;
    vi.mocked(learnPolicyOff).mockImplementation(() => {
      seenMessage = getRefusalOwnedMessage();
      return true;
    });

    submitCreate();

    expect(seenMessage).toBe(CREATE_MESSAGE);
    expect(getRefusalOwnedMessage()).toBeNull();
  });

  it("uses the create button's note, not the deck banner, with the sheet open", () => {
    vi.mocked(isTagSheetOpen).mockReturnValue(true);
    failWith(403, { errorCode: UTubTagErrorCodes.TAGGING_NOT_ALLOWED });

    submitCreate();

    // The control note (Step 6) replaces the deck banner while the sheet is open.
    expect($(BANNER).text()).toBe("");
  });

  it("skips programmatic focus on mobile when the sheet closed mid-request", () => {
    vi.mocked(isMobile).mockReturnValue(true);
    vi.mocked(isTagSheetOpen).mockReturnValue(false);
    failWith(403, { errorCode: UTubTagErrorCodes.TAGGING_NOT_ALLOWED });
    const createButton = document.getElementById(
      "utubTagBtnCreate",
    ) as HTMLElement;
    const focusSpy = vi.spyOn(createButton, "focus");

    submitCreate();

    expect(focusSpy).not.toHaveBeenCalled();
    expect(document.activeElement).not.toBe(createButton);
    expect($(BANNER).text()).toBe(CREATE_MESSAGE);
  });

  it("keeps the generic 403 fallback (error-page redirect) for other codes", () => {
    failWith(403, { errorCode: 99 });

    submitCreate();

    expect(learnPolicyOff).not.toHaveBeenCalled();
    expect($(BANNER).text()).toBe("");
    expect(assignSpy).toHaveBeenCalledTimes(1);
  });

  it("keeps the generic 403 fallback when the body carries no errorCode", () => {
    failWith(403, { message: "nope" });

    submitCreate();

    expect($(BANNER).text()).toBe("");
    expect(assignSpy).toHaveBeenCalledTimes(1);
  });
});
