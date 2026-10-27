// Real-DOM, real-store coverage for applyServerUrlOrder: an order-only live-apply
// that moves existing nodes and permutes the store's urls, adding nothing.
import { getState, resetStore, setState } from "../../../store/app-store.js";
import type { UtubUrlItem, UtubTag } from "../../../types/url.js";
import { applyServerUrlOrder, updateURLDeck } from "../deck.js";
import { createURLBlock } from "../cards/cards.js";
import { reapplyURLSearchFilter } from "../search.js";

vi.mock("../cards/cards.js", () => ({
  createURLBlock: vi.fn(({ url }: { url: UtubUrlItem }) =>
    window.jQuery(
      `<div class="urlRow" utuburlid="${url.utubUrlID}" filterable="true"></div>`,
    ),
  ),
  updateURLAfterFindingStaleData: vi.fn(),
  newURLInputRemoveEventListeners: vi.fn(),
  newURLInputAddEventListeners: vi.fn(),
  setFocusEventListenersOnURLCard: vi.fn(),
}));

vi.mock("../search.js", async () => {
  const actual =
    await vi.importActual<typeof import("../search.js")>("../search.js");
  return { ...actual, reapplyURLSearchFilter: vi.fn() };
});

vi.mock("../cards/swipe.js", () => ({
  triggerURLSwipeNudgeIfEligible: vi.fn(),
}));

vi.mock("../../../lib/tooltips.js", () => ({
  disposeTooltipsWithin: vi.fn(),
  hideTooltip: vi.fn(),
}));

vi.mock("../../utubs/header-fit.js", () => ({
  fitUTubHeaderAndSubheader: vi.fn(),
}));

const $ = window.jQuery;

function makeURL(utubUrlID: number, utubUrlTagIDs: number[] = []): UtubUrlItem {
  return {
    utubUrlID,
    urlString: `https://example${utubUrlID}.com`,
    urlTitle: `Title ${utubUrlID}`,
    utubUrlTagIDs,
    canDelete: true,
    shortLinkExpiresAt: null,
    canRevokeShortLink: false,
    addedAt: "2024-01-01T00:00:00+00:00",
    addedByUserID: 1,
  } satisfies UtubUrlItem;
}

function seedDeck(ids: number[]): void {
  document.body.innerHTML = `
    <div id="centerPanel">
      <div id="SearchURLWrap"><input id="URLContentSearch" value="" /></div>
      <div id="listURLs">
        ${ids
          .map(
            (id) =>
              `<div class="urlRow" utuburlid="${id}" filterable="true"></div>`,
          )
          .join("")}
      </div>
    </div>
  `;
}

function domOrder(): number[] {
  return $("#listURLs .urlRow")
    .map((_, el) => Number($(el).attr("utuburlid")))
    .get();
}

function storeOrder(): number[] {
  return getState().urls.map((url) => url.utubUrlID);
}

describe("applyServerUrlOrder", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetStore();
  });

  afterEach(() => {
    resetStore();
    document.body.innerHTML = "";
  });

  it("moves the existing nodes to the payload order without recreating them", () => {
    seedDeck([1, 2, 3]);
    const nodesBefore = $("#listURLs .urlRow").get();
    setState({ urls: [makeURL(1), makeURL(2), makeURL(3)] });

    applyServerUrlOrder([makeURL(3), makeURL(1), makeURL(2)]);

    expect(domOrder()).toEqual([3, 1, 2]);
    const nodesAfter = $("#listURLs .urlRow").get();
    expect(new Set(nodesAfter)).toEqual(new Set(nodesBefore));
    expect(createURLBlock).not.toHaveBeenCalled();
  });

  it("ignores payload ids unknown to the DOM and adds or removes nothing", () => {
    seedDeck([1, 2]);
    setState({ urls: [makeURL(1), makeURL(2)] });

    applyServerUrlOrder([makeURL(9), makeURL(2), makeURL(1)]);

    expect(domOrder()).toEqual([2, 1]);
    expect(createURLBlock).not.toHaveBeenCalled();
  });

  it("permutes the store urls: same item objects, payload order, store-only after, payload-only ignored", () => {
    seedDeck([1, 2, 3]);
    const one = makeURL(1);
    const two = makeURL(2);
    const three = makeURL(3);
    setState({ urls: [one, two, three] });

    // 2 is store-only (absent from the payload), 9 is payload-only.
    applyServerUrlOrder([makeURL(9), makeURL(3), makeURL(1)]);

    const urls = getState().urls;
    expect(storeOrder()).toEqual([3, 1, 2]);
    expect(urls[0]).toBe(three);
    expect(urls[1]).toBe(one);
    expect(urls[2]).toBe(two);
  });

  it("never adopts the payload's field values", () => {
    seedDeck([1, 2]);
    setState({ urls: [makeURL(1), makeURL(2)] });
    const changed = { ...makeURL(1), urlTitle: "Server renamed" };

    applyServerUrlOrder([makeURL(2), changed]);

    expect(getState().urls.find((url) => url.utubUrlID === 1)?.urlTitle).toBe(
      "Title 1",
    );
  });

  it("lets a following updateURLDeck still add a card for a payload-only URL", () => {
    seedDeck([1, 2]);
    setState({ urls: [makeURL(1), makeURL(2)] });

    applyServerUrlOrder([makeURL(3), makeURL(2), makeURL(1)]);
    expect(createURLBlock).not.toHaveBeenCalled();

    const tags: UtubTag[] = [];
    updateURLDeck({
      updatedUTubUrls: [makeURL(3), makeURL(2), makeURL(1)],
      updatedUTubTags: tags,
      utubID: 42,
    });

    expect(createURLBlock).toHaveBeenCalledTimes(1);
    expect(domOrder()).toEqual([3, 2, 1]);
  });

  it("restripes in the new DOM order", () => {
    seedDeck([1, 2, 3]);
    setState({ urls: [makeURL(1), makeURL(2), makeURL(3)] });

    applyServerUrlOrder([makeURL(3), makeURL(2), makeURL(1)]);

    const classes = $("#listURLs .urlRow")
      .map((_, el) => (el.classList.contains("even") ? "even" : "odd"))
      .get();
    expect(classes).toEqual(["even", "odd", "even"]);
  });

  it("keeps the selected card selected and scrolls it into view", () => {
    seedDeck([1, 2]);
    const selected = $("#listURLs .urlRow[utuburlid=1]");
    selected.attr("urlSelected", "true");
    const scrollIntoView = vi.fn();
    selected[0].scrollIntoView = scrollIntoView;
    setState({ urls: [makeURL(1), makeURL(2)], selectedURLCardID: 1 });

    applyServerUrlOrder([makeURL(2), makeURL(1)]);

    expect(selected.attr("urlSelected")).toBe("true");
    expect(getState().selectedURLCardID).toBe(1);
    expect(scrollIntoView).toHaveBeenCalledWith({ block: "nearest" });
  });

  it("keeps tag filter attributes and visibility through the reorder", () => {
    seedDeck([1, 2, 3]);
    setState({
      urls: [makeURL(1, [7]), makeURL(2), makeURL(3, [7])],
      selectedTagIDs: [7],
    });
    // Every row starts filterable=true, so only a real reapply can mark row 2.
    applyServerUrlOrder([makeURL(3, [7]), makeURL(2), makeURL(1, [7])]);

    expect(domOrder()).toEqual([3, 2, 1]);
    expect($("#listURLs .urlRow[utuburlid=2]").attr("filterable")).toBe(
      "false",
    );
    expect($("#listURLs .urlRow[utuburlid=1]").attr("filterable")).toBe("true");
    expect($("#listURLs .urlRow[utuburlid=3]").attr("filterable")).toBe("true");
  });

  it("reapplies the search filter only while the search box is open", () => {
    seedDeck([1, 2]);
    setState({ urls: [makeURL(1), makeURL(2)] });

    applyServerUrlOrder([makeURL(2), makeURL(1)]);
    expect(reapplyURLSearchFilter).not.toHaveBeenCalled();

    $("#SearchURLWrap").addClass("visible-flex");
    applyServerUrlOrder([makeURL(1), makeURL(2)]);
    expect(reapplyURLSearchFilter).toHaveBeenCalledTimes(1);
  });
});
