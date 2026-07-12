import { APP_CONFIG } from "../../../lib/config.js";
import { createUTubSelector } from "../selectors.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../header-fit.js", () => ({ fitUTubHeaderAndSubheader: vi.fn() }));

vi.mock("../deck.js", () => ({
  showUTubLoadingIconAndSetTimeout: vi.fn(() => 0),
  hideUTubLoadingIconAndClearTimeout: vi.fn(),
  setUTubDeckOnUTubSelected: vi.fn(),
}));

vi.mock("../../urls/update-description.js", () => ({
  removeEventListenersForShowCreateUTubDescIfEmptyDesc: vi.fn(),
  showCreateDescriptionButtonAlways: vi.fn(),
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

const CREATOR_ROLE = APP_CONFIG.constants.MEMBER_ROLES.CREATOR;

describe("createUTubSelector — locked-UTub role icon", () => {
  it("renders the padlock icon and omits the member-role symbol when locked", () => {
    const utubSelector = createUTubSelector({
      utubName: "Locked UTub",
      utubID: 1,
      memberRole: CREATOR_ROLE,
      isLocked: true,
      index: 0,
    });

    expect(utubSelector.find("svg.utubLockedIcon").length).toBe(1);
    expect(utubSelector.find(".bi-diamond-fill").length).toBe(0);
    expect(utubSelector.find(".bi-people-fill").length).toBe(0);
  });

  it("renders the creator diamond and omits the padlock when unlocked for a creator", () => {
    const utubSelector = createUTubSelector({
      utubName: "Open UTub",
      utubID: 2,
      memberRole: CREATOR_ROLE,
      isLocked: false,
      index: 1,
    });

    expect(utubSelector.find("svg.bi-diamond-fill.memberRole").length).toBe(1);
    expect(utubSelector.find(".utubLockedIcon").length).toBe(0);
  });
});
