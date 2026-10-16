// Real-DOM coverage for updateURLDeck's post-diff reorder + restripe. Unlike
// deck.test.ts this file deliberately does NOT mock apply-deck-diff, filtering
// or tags/utils, so the real addElement, reorder and restripe code runs.
import { getState } from "../../../store/app-store.js";
import type { UtubUrlItem, UtubTag } from "../../../types/url.js";
import { updateURLDeck } from "../deck.js";

vi.mock("../cards/cards.js", () => ({
  createURLBlock: vi.fn((url: UtubUrlItem) =>
    window.jQuery(
      `<div class="urlRow" utuburlid="${url.utubUrlID}" filterable="true"><button class="inner">btn</button></div>`,
    ),
  ),
  updateURLAfterFindingStaleData: vi.fn(),
  newURLInputRemoveEventListeners: vi.fn(),
  newURLInputAddEventListeners: vi.fn(),
  setFocusEventListenersOnURLCard: vi.fn(),
}));

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

vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(),
  setState: vi.fn(),
  resetStore: vi.fn(),
}));

const $ = window.jQuery;

function makeURL(utubUrlID: number, urlTitle = `Title ${utubUrlID}`) {
  return {
    utubUrlID,
    urlString: `https://example${utubUrlID}.com`,
    urlTitle,
    utubUrlTagIDs: [],
    canDelete: true,
    addedAt: "2024-01-01T00:00:00+00:00",
    addedByUserID: 1,
  } satisfies UtubUrlItem;
}

const TAGS: UtubTag[] = [];

function seedDeck(ids: number[]): void {
  document.body.innerHTML = `
    <div id="centerPanel">
      <div id="SearchURLWrap"></div>
      <div id="listURLs">
        ${ids
          .map(
            (id) =>
              `<div class="urlRow" utuburlid="${id}" filterable="true"><button class="inner" id="btn${id}">btn</button></div>`,
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

function mockStoreUrls(urls: UtubUrlItem[]): void {
  vi.mocked(getState).mockReturnValue({
    urls,
    selectedTagIDs: [],
    multiSelectMode: false,
    selectedURLCardIDs: [],
  } as unknown as ReturnType<typeof getState>);
}

describe("updateURLDeck post-diff reorder and restripe", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = "";
  });

  it("renders a new URL first when the payload puts it first, alternating even/odd in DOM order", () => {
    seedDeck([1, 2]);
    $("#listURLs .urlRow[utuburlid=1]").addClass("even");
    $("#listURLs .urlRow[utuburlid=2]").addClass("odd");
    mockStoreUrls([makeURL(1), makeURL(2)]);

    updateURLDeck([makeURL(3), makeURL(1), makeURL(2)], TAGS, 42);

    expect(domOrder()).toEqual([3, 1, 2]);
    const classes = $("#listURLs .urlRow")
      .map((_, el) => (el.classList.contains("even") ? "even" : "odd"))
      .get();
    expect(classes).toEqual(["even", "odd", "even"]);
  });

  it("restripes cards even while the centre panel is hidden, skipping searchable=false rows", () => {
    seedDeck([1, 2]);
    $("#centerPanel").css("display", "none");
    $("#listURLs .urlRow[utuburlid=2]").attr("searchable", "false");
    mockStoreUrls([makeURL(1), makeURL(2)]);

    updateURLDeck([makeURL(3), makeURL(1), makeURL(2)], TAGS, 42);

    expect($("#listURLs .urlRow[utuburlid=3]").hasClass("even")).toBe(true);
    expect($("#listURLs .urlRow[utuburlid=1]").hasClass("odd")).toBe(true);
    // searchable=false is skipped by the alternation (never gets a class).
    expect($("#listURLs .urlRow[utuburlid=2]").hasClass("even")).toBe(false);
    expect($("#listURLs .urlRow[utuburlid=2]").hasClass("odd")).toBe(false);
  });

  it("keeps focus on a focused element inside a card when the reorder moves it", () => {
    seedDeck([1, 2]);
    const focusTarget = document.getElementById("btn1") as HTMLButtonElement;
    focusTarget.focus();
    expect(document.activeElement).toBe(focusTarget);
    const focusSpy = vi.spyOn(focusTarget, "focus");
    mockStoreUrls([makeURL(1), makeURL(2)]);

    // Payload puts 2 before 1, so card 1 is moved in the DOM.
    updateURLDeck([makeURL(2), makeURL(1)], TAGS, 42);

    expect(domOrder()).toEqual([2, 1]);
    expect(focusSpy).toHaveBeenCalledWith({ preventScroll: true });
    expect(document.activeElement).toBe(focusTarget);
  });

  it("performs no DOM move and never blurs when the payload order already matches", () => {
    seedDeck([1, 2]);
    const focusTarget = document.getElementById("btn1") as HTMLButtonElement;
    focusTarget.focus();
    const focusSpy = vi.spyOn(focusTarget, "focus");
    mockStoreUrls([makeURL(1), makeURL(2)]);
    const observer = new MutationObserver(() => {});
    observer.observe(document.getElementById("listURLs")!, { childList: true });

    updateURLDeck([makeURL(1, "Edited title"), makeURL(2)], TAGS, 42);

    expect(observer.takeRecords()).toHaveLength(0);
    observer.disconnect();
    expect(focusSpy).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(focusTarget);
    expect(domOrder()).toEqual([1, 2]);
  });
});
