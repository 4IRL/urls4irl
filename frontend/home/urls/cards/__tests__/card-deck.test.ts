import type { Mock } from "vitest";
import type { UtubTag, UtubUrlItem } from "../../../../types/url.js";

import { AppEvents, emit } from "../../../../lib/event-bus.js";
import { APP_CONFIG } from "../../../../lib/config.js";
import { disposeTooltipsWithin } from "../../../../lib/tooltips.js";
import { getState, setState } from "../../../../store/app-store.js";
import { isATagSelected } from "../../../tags/utils.js";
import { getNumOfVisibleURLs } from "../../utils.js";
import { renderAppliedTagsForUrl } from "../../tags/tag-render.js";
import {
  closeURLSearchAndEraseInput,
  hideURLSearchIcon,
  showURLSearchIcon,
} from "../../search.js";
import { showURLsEmptyState } from "../../empty-state.js";
import { createURLBlock } from "../cards.js";
import { selectURLCard } from "../selection.js";
import { triggerURLSwipeNudgeIfEligible } from "../swipe.js";
import { updateColorOfFollowingURLCardsAfterURLCreated } from "../utils.js";
import {
  applyDefaultUrlSort,
  reapplyAlternatingURLCardBackgroundAfterFilter,
  updateTagFilteringOnURLOrURLTagDeletion,
  updateURLsAndTagSubheaderWhenTagSelected,
} from "../filtering.js";
import { insertURLCardIntoDeck, removeURLCardFromDeck } from "../card-deck.js";

// Partial mock: keep the real AppEvents enum but spy `emit` so the
// URL_DECK_CHANGED notification can be asserted without a bus subscriber.
vi.mock("../../../../lib/event-bus.js", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("../../../../lib/event-bus.js")>();
  return {
    ...actual,
    emit: vi.fn(),
  };
});

vi.mock("../../../../lib/tooltips.js", () => ({
  disposeTooltipsWithin: vi.fn(),
}));

vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(),
  setState: vi.fn(),
}));

vi.mock("../../../tags/utils.js", () => ({
  isATagSelected: vi.fn(() => false),
}));

vi.mock("../../utils.js", () => ({
  getNumOfVisibleURLs: vi.fn(() => 0),
}));

vi.mock("../cards.js", () => ({
  createURLBlock: vi.fn(),
}));

vi.mock("../selection.js", () => ({
  selectURLCard: vi.fn(),
}));

vi.mock("../swipe.js", () => ({
  triggerURLSwipeNudgeIfEligible: vi.fn(),
}));

vi.mock("../utils.js", () => ({
  updateColorOfFollowingURLCardsAfterURLCreated: vi.fn(),
}));

vi.mock("../filtering.js", () => ({
  applyDefaultUrlSort: vi.fn(),
  reapplyAlternatingURLCardBackgroundAfterFilter: vi.fn(),
  updateTagFilteringOnURLOrURLTagDeletion: vi.fn(),
  updateURLsAndTagSubheaderWhenTagSelected: vi.fn(),
}));

vi.mock("../../tags/tag-render.js", () => ({
  renderAppliedTagsForUrl: vi.fn(),
}));

vi.mock("../../search.js", () => ({
  closeURLSearchAndEraseInput: vi.fn(),
  hideURLSearchIcon: vi.fn(),
  showURLSearchIcon: vi.fn(),
}));

vi.mock("../../empty-state.js", () => ({
  showURLsEmptyState: vi.fn(),
}));

const $ = window.jQuery;

const NEW_URL_ID = 42;
const EXISTING_URL_IDS = [10, 11];
const HIGHLIGHT_CLASS = "url-card-created-highlight";
const HIGHLIGHT_DURATION_MS = 700;

function buildUrlItem(utubUrlID: number): UtubUrlItem {
  return {
    utubUrlID,
    urlString: `https://example.com/${utubUrlID}`,
    urlTitle: `Example ${utubUrlID}`,
    utubUrlTagIDs: [],
    canDelete: true,
    addedAt: "2024-03-09T12:00:00+00:00",
    addedByUserID: 1,
  };
}

function mockStoreUrls(urlIDs: number[]): void {
  vi.mocked(getState).mockReturnValue({
    urls: urlIDs.map(buildUrlItem),
    preferences: {
      theme: "system",
      defaultView: "list",
      defaultSort: "newest",
      density: "comfortable",
      dateFormat: "iso",
    },
  } as unknown as ReturnType<typeof getState>);
}

function mockSortOrder(urlIDs: number[]): void {
  vi.mocked(applyDefaultUrlSort).mockReturnValue(
    urlIDs.map((utubUrlID) => ({
      utubUrlID,
    })) as unknown as ReturnType<typeof applyDefaultUrlSort>,
  );
}

function getDeckOrder(): (string | null)[] {
  return $("#listURLs .urlRow")
    .toArray()
    .map((row) => row.getAttribute("utuburlid"));
}

describe("insertURLCardIntoDeck", () => {
  let newUrlCard: JQuery;
  let scrollSpy: Mock<HTMLElement["scrollIntoView"]>;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    document.body.innerHTML = `
      <div id="listURLs">
        <div id="createURLWrap"></div>
        <div class="urlRow" utuburlid="10"></div>
        <div class="urlRow" utuburlid="11"></div>
      </div>
      <span id="fieldSavedAnnouncement"></span>
    `;
    newUrlCard = $(`<div class="urlRow" utuburlid="${NEW_URL_ID}"></div>`);
    scrollSpy = vi.fn<HTMLElement["scrollIntoView"]>();
    (newUrlCard[0] as HTMLElement).scrollIntoView = scrollSpy;
    vi.mocked(createURLBlock).mockReturnValue(newUrlCard);
    vi.mocked(isATagSelected).mockReturnValue(false);
    vi.mocked(getNumOfVisibleURLs).mockReturnValue(EXISTING_URL_IDS.length);
    mockStoreUrls(EXISTING_URL_IDS);
    // Default: the new card sorts first, so the reorder is a no-op.
    mockSortOrder([NEW_URL_ID, ...EXISTING_URL_IDS]);
  });

  afterEach(() => {
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  function insertCard({
    announce,
    appliedTags = [],
  }: {
    announce: boolean;
    appliedTags?: UtubTag[];
  }): JQuery {
    return insertURLCardIntoDeck({
      newUrl: buildUrlItem(NEW_URL_ID),
      utubID: 1,
      appliedTags,
      announce,
    });
  }

  it("appends the URL to the store, notifies the deck change and returns the new card", () => {
    const returnedCard = insertCard({ announce: true });

    expect(returnedCard).toBe(newUrlCard);
    expect(setState).toHaveBeenCalledWith({
      urls: [...EXISTING_URL_IDS, NEW_URL_ID].map(buildUrlItem),
    });
    expect(emit).toHaveBeenCalledWith(AppEvents.URL_DECK_CHANGED);
    expect(createURLBlock).toHaveBeenCalledWith(
      buildUrlItem(NEW_URL_ID),
      [],
      1,
    );
    expect(newUrlCard.hasClass("even")).toBe(true);
  });

  it("renders the applied tags, re-evaluates visibility and resets the search", () => {
    const appliedTags: UtubTag[] = [{ id: 7, tagString: "tag", tagApplied: 1 }];

    insertCard({ announce: true, appliedTags });

    expect(renderAppliedTagsForUrl).toHaveBeenCalledWith({
      appliedTags,
      utubUrlTagIDs: [],
      urlCard: newUrlCard,
      utubID: 1,
    });
    expect(updateURLsAndTagSubheaderWhenTagSelected).toHaveBeenCalledTimes(1);
    expect(closeURLSearchAndEraseInput).toHaveBeenCalledTimes(1);
    expect(showURLSearchIcon).toHaveBeenCalledTimes(1);
  });

  it("selects the new card when no tag filter is active", () => {
    insertCard({ announce: true });

    expect(selectURLCard).toHaveBeenCalledWith(newUrlCard);
  });

  it("leaves selection untouched when a tag filter is active", () => {
    vi.mocked(isATagSelected).mockReturnValue(true);

    insertCard({ announce: true });

    expect(selectURLCard).not.toHaveBeenCalled();
  });

  it("recolors the following cards only when the deck already had visible URLs", () => {
    insertCard({ announce: true });

    expect(updateColorOfFollowingURLCardsAfterURLCreated).toHaveBeenCalledTimes(
      1,
    );
  });

  it("skips recoloring and still inserts the card into an empty deck", () => {
    document.body.innerHTML = `
      <div id="listURLs"><div id="createURLWrap"></div></div>
      <span id="fieldSavedAnnouncement"></span>
    `;
    vi.mocked(getNumOfVisibleURLs).mockReturnValue(0);
    mockStoreUrls([]);
    mockSortOrder([NEW_URL_ID]);

    insertCard({ announce: true });

    expect(
      updateColorOfFollowingURLCardsAfterURLCreated,
    ).not.toHaveBeenCalled();
    expect(getDeckOrder()).toEqual([String(NEW_URL_ID)]);
    expect(scrollSpy).not.toHaveBeenCalled();
  });

  it("keeps the new card at the top when the sort places it first, with no scroll or announcement", () => {
    insertCard({ announce: true });

    expect(getDeckOrder()).toEqual(["42", "10", "11"]);
    expect(reapplyAlternatingURLCardBackgroundAfterFilter).toHaveBeenCalled();
    expect(scrollSpy).not.toHaveBeenCalled();
    expect($("#fieldSavedAnnouncement").text()).toBe("");
  });

  it("moves the card to its sorted position, scrolls it and announces when announce is true", () => {
    mockSortOrder([...EXISTING_URL_IDS, NEW_URL_ID]);

    insertCard({ announce: true });

    expect(getDeckOrder()).toEqual(["10", "11", "42"]);
    expect(scrollSpy).toHaveBeenCalledTimes(1);
    expect(scrollSpy).toHaveBeenCalledWith(
      expect.objectContaining({ block: "center" }),
    );
    expect($("#fieldSavedAnnouncement").text()).toBe(
      APP_CONFIG.strings.URL_ADDED_ANNOUNCEMENT,
    );
  });

  it("moves and scrolls the card but stays silent for screen readers when announce is false", () => {
    mockSortOrder([...EXISTING_URL_IDS, NEW_URL_ID]);

    insertCard({ announce: false });

    expect(getDeckOrder()).toEqual(["10", "11", "42"]);
    expect(scrollSpy).toHaveBeenCalledTimes(1);
    expect($("#fieldSavedAnnouncement").text()).toBe("");
  });

  it("flashes the highlight class and removes it after the highlight duration", () => {
    insertCard({ announce: true });

    expect(newUrlCard.hasClass(HIGHLIGHT_CLASS)).toBe(true);
    vi.advanceTimersByTime(HIGHLIGHT_DURATION_MS);
    expect(newUrlCard.hasClass(HIGHLIGHT_CLASS)).toBe(false);
  });

  it("fires the swipe nudge against the new card", () => {
    insertCard({ announce: true });

    expect(triggerURLSwipeNudgeIfEligible).toHaveBeenCalledWith({
      urlRow: newUrlCard,
    });
  });
});

describe("removeURLCardFromDeck", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = `
      <div id="listURLs">
        <div id="createURLWrap"></div>
        <div class="urlRow" utuburlid="10" data-utub-url-tag-ids=""></div>
        <div class="urlRow" utuburlid="11" data-utub-url-tag-ids=""></div>
      </div>
      <div class="tagFilter" data-utub-tag-id="1">
        <span class="tagAppliedToUrlsCount">3 / 5</span>
      </div>
      <div class="tagFilter" data-utub-tag-id="2">
        <span class="tagAppliedToUrlsCount">malformed</span>
      </div>
    `;
    mockStoreUrls([10, 11]);
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  function getUrlCard(utubUrlID: number): JQuery {
    return $(`.urlRow[utuburlid=${utubUrlID}]`);
  }

  it("drops the URL from the store, notifies the deck change and detaches the card synchronously when not animated", () => {
    removeURLCardFromDeck({
      urlCard: getUrlCard(10),
      utubUrlID: 10,
      animate: false,
    });

    expect(setState).toHaveBeenCalledWith({ urls: [buildUrlItem(11)] });
    expect(emit).toHaveBeenCalledWith(AppEvents.URL_DECK_CHANGED);
    expect(disposeTooltipsWithin).toHaveBeenCalledTimes(1);
    expect(getDeckOrder()).toEqual(["11"]);
  });

  it("re-syncs tag filtering and leaves the empty state alone while other cards remain", () => {
    removeURLCardFromDeck({
      urlCard: getUrlCard(10),
      utubUrlID: 10,
      animate: false,
    });

    expect(updateTagFilteringOnURLOrURLTagDeletion).toHaveBeenCalledTimes(1);
    expect(showURLsEmptyState).not.toHaveBeenCalled();
    expect(hideURLSearchIcon).not.toHaveBeenCalled();
  });

  it("shows the empty state and hides the search icon when the last card is removed", () => {
    mockStoreUrls([10]);
    getUrlCard(11).remove();

    removeURLCardFromDeck({
      urlCard: getUrlCard(10),
      utubUrlID: 10,
      animate: false,
    });

    expect(getDeckOrder()).toEqual([]);
    expect(showURLsEmptyState).toHaveBeenCalledTimes(1);
    expect(hideURLSearchIcon).toHaveBeenCalledTimes(1);
    expect(updateTagFilteringOnURLOrURLTagDeletion).not.toHaveBeenCalled();
  });

  it("fades the card out and defers detaching until the fade completes when animated", () => {
    const urlCard = getUrlCard(10);
    const fadeOutSpy = vi.fn();
    urlCard.fadeOut = fadeOutSpy as unknown as JQuery["fadeOut"];

    removeURLCardFromDeck({ urlCard, utubUrlID: 10, animate: true });

    // The store updates immediately; only the DOM detach waits for the fade.
    expect(setState).toHaveBeenCalledWith({ urls: [buildUrlItem(11)] });
    expect(fadeOutSpy).toHaveBeenCalledWith("slow", expect.any(Function));
    expect(getDeckOrder()).toEqual(["10", "11"]);
    expect(disposeTooltipsWithin).not.toHaveBeenCalled();

    const detachCard = fadeOutSpy.mock.calls[0][1] as () => void;
    detachCard();

    expect(getDeckOrder()).toEqual(["11"]);
    expect(disposeTooltipsWithin).toHaveBeenCalledTimes(1);
  });

  it("decrements the visible and total count of every tag the card carried", () => {
    const urlCard = getUrlCard(10).attr("data-utub-url-tag-ids", "1");

    removeURLCardFromDeck({ urlCard, utubUrlID: 10, animate: false });

    expect(
      $('.tagFilter[data-utub-tag-id="1"] .tagAppliedToUrlsCount').text(),
    ).toBe("2 / 4");
  });

  it("skips a tag whose count text is malformed", () => {
    const urlCard = getUrlCard(10).attr("data-utub-url-tag-ids", "2");

    removeURLCardFromDeck({ urlCard, utubUrlID: 10, animate: false });

    expect(
      $('.tagFilter[data-utub-tag-id="2"] .tagAppliedToUrlsCount').text(),
    ).toBe("malformed");
    expect(getDeckOrder()).toEqual(["11"]);
  });

  it("leaves every tag count untouched when the card carried no tags", () => {
    removeURLCardFromDeck({
      urlCard: getUrlCard(10),
      utubUrlID: 10,
      animate: false,
    });

    expect(
      $('.tagFilter[data-utub-tag-id="1"] .tagAppliedToUrlsCount').text(),
    ).toBe("3 / 5");
  });

  it("leaves the other URLs in the store when the id is not present", () => {
    removeURLCardFromDeck({
      urlCard: getUrlCard(10),
      utubUrlID: 999,
      animate: false,
    });

    expect(setState).toHaveBeenCalledWith({
      urls: [buildUrlItem(10), buildUrlItem(11)],
    });
  });
});
