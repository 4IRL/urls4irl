import utubCardTemplate from "../../../../backend/templates/components/home/UTubDeck/UTubCard.html?raw";

import { APP_CONFIG } from "../../../lib/config.js";
import { createUTubSelector } from "../selectors.js";
import { makeUTubRowCounts, makeUTubRowCountsLabel } from "../row-counts.js";

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
      isPinned: false,
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
      isPinned: false,
      index: 1,
      urlCount: 0,
      memberCount: 1,
    });

    expect(utubSelector.find("svg.bi-diamond-fill.memberRole").length).toBe(1);
    expect(utubSelector.find(".utubLockedIcon").length).toBe(0);
  });
});

describe("createUTubSelector — row counts group", () => {
  function build(urlCount: number, memberCount: number | null) {
    return createUTubSelector({
      utubName: "Counts UTub",
      utubID: 3,
      memberRole: CREATOR_ROLE,
      isLocked: false,
      isPinned: false,
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

  it("shows only the URL count when the member count is hidden", () => {
    const counts = build(4, null).children(".UTubRowCounts");

    expect(counts.find(".visually-hidden").text()).toBe(", 4 URLs");
    expect(counts.find(".UTubRowCountNum")).toHaveLength(1);
    expect(counts.find(".bi-person-fill")).toHaveLength(0);
  });

  it("renders singular labels for a count of one", () => {
    const utubSelector = build(1, 1);

    expect(utubSelector.find(".UTubRowCounts .visually-hidden").text()).toBe(
      ", 1 URL, 1 member",
    );
  });
});

describe("createUTubSelector — pin marker", () => {
  function build(isPinned: boolean) {
    return createUTubSelector({
      utubName: "Pin UTub",
      utubID: 4,
      memberRole: CREATOR_ROLE,
      isLocked: false,
      isPinned,
      index: 0,
      urlCount: 0,
      memberCount: 1,
    });
  }

  it("renders an aria-hidden pin icon and a Pinned label before the role icon", () => {
    const utubSelector = build(true);
    const icon = utubSelector.children("svg.bi-pin-fill.UTubPinIcon");

    expect(icon.length).toBe(1);
    expect(icon.attr("aria-hidden")).toBe("true");
    expect(icon.attr("width")).toBe("16");
    expect(icon.hasClass("memberRole")).toBe(false);
    expect(icon.next(".visually-hidden").text()).toBe("Pinned");
    expect(icon.next().next().is("svg.memberRole")).toBe(true);
    expect(utubSelector.find(".memberRole .UTubPinIcon").length).toBe(0);
  });

  it("renders nothing extra for an unpinned item", () => {
    const utubSelector = build(false);

    expect(utubSelector.find(".UTubPinIcon").length).toBe(0);
    expect(utubSelector.find(".UTubPinnedLabel").length).toBe(0);
    expect(utubSelector.children().length).toBe(3);
  });

  it("matches the UTubCard.html pin marker (normalized whitespace)", () => {
    const line = utubCardTemplate
      .split("\n")
      .find((text: string) => text.includes("{% if utub.isPinned %}"));
    expect(line).toBeDefined();

    const rendered = (line ?? "")
      .replace("{% if utub.isPinned %}", "")
      .replace("{% endif %}", "")
      .replace(
        "{{ CONSTANTS.STRINGS.UTUB_PINNED_ROW_LABEL }}",
        APP_CONFIG.strings.UTUB_PINNED_ROW_LABEL,
      );
    const template = document.createElement("div");
    template.innerHTML = rendered;
    const normalize = (html: string) => html.replace(/\s+/g, " ").trim();

    expect(normalize(template.innerHTML)).toBe(
      normalize(
        build(true)
          .children(".UTubPinIcon, .UTubPinnedLabel")
          .toArray()
          .map((element) => element.outerHTML)
          .join(""),
      ),
    );
  });
});

describe("makeUTubRowCounts — Jinja markup parity", () => {
  // Renders the template's counts line by hand: resolves the memberCount
  // `{% if %}` blocks (none = drop the member clause and segment).
  function renderTemplateFragment({
    urlCount,
    memberCount,
  }: {
    urlCount: number;
    memberCount: number | null;
  }): string {
    const fragment = utubCardTemplate
      .split("\n")
      .find((line: string) => line.includes('<span class="UTubRowCounts'));
    expect(fragment).toBeDefined();

    const withoutBlocks =
      memberCount === null
        ? (fragment ?? "").replace(
            /\{% if utub\.memberCount is not none %\}.*?\{% endif %\}/g,
            "",
          )
        : (fragment ?? "").replace(
            /\{% (?:if utub\.memberCount is not none|endif) %\}/g,
            "",
          );
    return withoutBlocks
      .trim()
      .replace(
        /<span class="visually-hidden">.*?<\/span>/,
        `<span class="visually-hidden">${makeUTubRowCountsLabel({ urlCount, memberCount })}</span>`,
      )
      .replace("{{ utub.urlCount }}", String(urlCount))
      .replace("{{ utub.memberCount }}", String(memberCount));
  }

  it.each([
    { urlCount: 3, memberCount: 2 as number | null },
    { urlCount: 3, memberCount: null as number | null },
  ])(
    "matches the UTubCard.html counts group for memberCount $memberCount",
    ({ urlCount, memberCount }) => {
      // Parse the template fragment through the DOM so both sides serialize alike.
      const template = document.createElement("div");
      template.innerHTML = renderTemplateFragment({ urlCount, memberCount });
      const normalize = (html: string) => html.replace(/\s+/g, " ").trim();

      expect(normalize(template.innerHTML)).toBe(
        normalize(
          makeUTubRowCounts({ urlCount, memberCount }).prop("outerHTML"),
        ),
      );
    },
  );

  it("omits the member segment and label clause for a null memberCount", () => {
    const counts = makeUTubRowCounts({ urlCount: 1, memberCount: null });

    expect(counts.find(".UTubRowCount")).toHaveLength(1);
    expect(counts.find(".visually-hidden").text()).toBe(", 1 URL");
  });
});
