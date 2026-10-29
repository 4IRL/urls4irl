import utubCardTemplate from "../../../../backend/templates/components/home/UTubDeck/UTubCard.html?raw";

import { APP_CONFIG } from "../../../lib/config.js";
import { createUTubSelector, makeUTubRowCounts } from "../selectors.js";
import { makeUTubRowCountsLabel } from "../row-counts.js";

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
      urlCount: 0,
      memberCount: 1,
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
      urlCount: 0,
      memberCount: 1,
    });

    expect(utubSelector.find("svg.bi-diamond-fill.memberRole").length).toBe(1);
    expect(utubSelector.find(".utubLockedIcon").length).toBe(0);
  });
});

describe("createUTubSelector — row counts group", () => {
  function build(urlCount: number, memberCount: number) {
    return createUTubSelector({
      utubName: "Counts UTub",
      utubID: 3,
      memberRole: CREATOR_ROLE,
      isLocked: false,
      index: 2,
      urlCount,
      memberCount,
    });
  }

  it("renders plural labels and aria-hidden icon pairs before the role icon", () => {
    const utubSelector = build(3, 2);
    const counts = utubSelector.children(".UTubRowCounts");

    expect(counts.length).toBe(1);
    expect(counts.hasClass("memberRole")).toBe(false);
    expect(counts.find(".visually-hidden").text()).toBe(", 3 URLs, 2 members");
    expect(counts.find(".UTubRowCount[aria-hidden='true']").length).toBe(2);
    expect(counts.find(".UTubRowCountNum").first().text()).toBe("3");
    expect(counts.find(".UTubRowCountNum").last().text()).toBe("2");
    expect(counts.next().is("svg.memberRole")).toBe(true);
  });

  it("renders singular labels for a count of one", () => {
    const utubSelector = build(1, 1);

    expect(utubSelector.find(".UTubRowCounts .visually-hidden").text()).toBe(
      ", 1 URL, 1 member",
    );
  });
});

describe("makeUTubRowCounts — Jinja markup parity", () => {
  it("matches the UTubCard.html counts group (normalized whitespace)", () => {
    const fragment = utubCardTemplate
      .split("\n")
      .find((line: string) => line.includes('<span class="UTubRowCounts'));
    expect(fragment).toBeDefined();

    const urlCount = 3;
    const memberCount = 2;
    const rendered = (fragment ?? "")
      .trim()
      .replace(
        /<span class="visually-hidden">.*?<\/span>/,
        `<span class="visually-hidden">${makeUTubRowCountsLabel({ urlCount, memberCount })}</span>`,
      )
      .replace("{{ utub.urlCount }}", String(urlCount))
      .replace("{{ utub.memberCount }}", String(memberCount));

    // Parse the template fragment through the DOM so both sides serialize alike.
    const template = document.createElement("div");
    template.innerHTML = rendered;
    const normalize = (html: string) => html.replace(/\s+/g, " ").trim();

    expect(normalize(template.innerHTML)).toBe(
      normalize(makeUTubRowCounts({ urlCount, memberCount }).prop("outerHTML")),
    );
  });
});
