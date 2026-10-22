// Real-DOM coverage for the stale-data path's adder attribution: uses the REAL
// updateURLDeck, createURLBlock and event bus, mocking only the heavy card
// collaborators (mirrors cards.test.ts), so the members payload is proven to
// reach the stacked badge of a card built before the store is refreshed.
import { APP_CONFIG } from "../../../lib/config.js";
import { AppEvents, emit } from "../../../lib/event-bus.js";
import { setState } from "../../../store/app-store.js";
import type { MemberItem } from "../../../types/member.js";
import type { UtubUrlItem } from "../../../types/url.js";
import { createURLBlock } from "../cards/cards.js";
import { updateURLDeck } from "../deck.js";

vi.mock("../cards/selection.js", () => ({
  selectURLCard: vi.fn(),
  setURLCardSelectionEventListener: vi.fn(),
}));
vi.mock("../cards/corner-access.js", () => ({
  createGoToURLIcon: vi.fn(() =>
    window.jQuery('<button class="goToUrlIcon self-start"></button>'),
  ),
}));
vi.mock("../cards/url-title.js", () => ({
  createURLTitle: vi.fn((title) =>
    window.jQuery('<h6 class="urlTitle"></h6>').text(title),
  ),
  createURLTitleAndUpdateBlock: vi.fn(() =>
    window.jQuery('<div class="urlTitleAndUpdateIconWrap"></div>'),
  ),
}));
vi.mock("../cards/url-string.js", () => ({
  createURLString: vi.fn((url) =>
    window.jQuery('<a class="urlString"></a>').attr("href", url),
  ),
  createURLStringAndUpdateBlock: vi.fn(() =>
    window.jQuery('<div class="updateUrlStringWrap"></div>'),
  ),
  modifyURLStringForDisplay: vi.fn((url) => url),
}));
vi.mock("../tags/tags.js", () => ({
  createTagBadgeInURL: vi.fn(),
  createTagBadgesAndWrap: vi.fn(() =>
    window.jQuery('<div class="urlTagsContainer"></div>'),
  ),
}));
vi.mock("../tags/combobox.js", () => ({
  ComboboxMode: { URL: "url", CREATE: "create" },
  createTagComboboxBlock: vi.fn(() =>
    window.jQuery('<div class="urlTagComboboxWrap"></div>'),
  ),
}));
vi.mock("../cards/options/btns.js", () => ({
  createURLOptionsButtons: vi.fn(() =>
    window.jQuery('<div class="urlOptions"></div>'),
  ),
}));
vi.mock("../cards/swipe.js", () => ({
  bindURLRowSwipeGesture: vi.fn(),
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
const UTUB_ID = 42;
const ADDED_AT = "2024-03-09T12:00:00+00:00";

function makeURL(utubUrlID: number, addedByUserID: number): UtubUrlItem {
  return {
    utubUrlID,
    urlString: `https://example${utubUrlID}.com`,
    urlTitle: `Title ${utubUrlID}`,
    utubUrlTagIDs: [],
    canDelete: true,
    shortLinkExpiresAt: null,
    canRevokeShortLink: false,
    addedAt: ADDED_AT,
    addedByUserID,
  };
}

function member(id: number, username: string): MemberItem {
  return { id, username, memberRole: "member" };
}

function stackedBadge(utubUrlID: number): JQuery {
  return $(`.urlRow[utuburlid=${utubUrlID}] .urlDateAddedBadgeStacked`);
}

describe("stale-data deck refresh attributes new cards from the payload members", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="centerPanel">
        <div id="SearchURLWrap"></div>
        <div id="listURLs"></div>
      </div>
    `;
    setState({
      members: [member(1, "owner")],
      urls: [],
      selectedTagIDs: [],
      multiSelectMode: false,
      selectedURLCardIDs: [],
    });
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("names an adder present only in the payload members (store still stale)", () => {
    const payloadMembers = [member(1, "owner"), member(7, "alice")];

    updateURLDeck({
      updatedUTubUrls: [makeURL(5, 7)],
      updatedUTubTags: [],
      utubID: UTUB_ID,
      updatedMembers: payloadMembers,
    });

    expect(stackedBadge(5).text()).toBe(
      `${APP_CONFIG.strings.URL_ADDED_BY} alice · 2024-03-09`,
    );
  });

  it("credits a former member when the adder is absent from the payload members", () => {
    updateURLDeck({
      updatedUTubUrls: [makeURL(5, 99)],
      updatedUTubTags: [],
      utubID: UTUB_ID,
      updatedMembers: [member(1, "owner")],
    });

    expect(stackedBadge(5).text()).toContain(
      APP_CONFIG.strings.URL_ADDED_BY_FORMER_MEMBER,
    );
    expect(stackedBadge(5).text()).not.toContain("alice");
  });

  it("leaves an existing card's badge untouched (element update path)", () => {
    const existing = createURLBlock({
      url: makeURL(1, 1),
      dictTags: [],
      utubID: UTUB_ID,
    });
    $("#listURLs").append(existing);
    setState({ urls: [makeURL(1, 1)] } as Parameters<typeof setState>[0]);
    const before = stackedBadge(1).text();
    expect(before).toBe(
      `${APP_CONFIG.strings.URL_ADDED_BY} owner · 2024-03-09`,
    );

    // Payload edits the existing URL's title and adds a new one by alice.
    updateURLDeck({
      updatedUTubUrls: [
        { ...makeURL(1, 1), urlTitle: "Renamed" },
        makeURL(5, 7),
      ],
      updatedUTubTags: [],
      utubID: UTUB_ID,
      updatedMembers: [member(1, "owner"), member(7, "alice")],
    });

    expect(stackedBadge(1).text()).toBe(before);
    expect($(".urlRow[utuburlid=1]").length).toBe(1);
    expect(stackedBadge(1).length).toBe(1);
    expect(stackedBadge(5).text()).toBe(
      `${APP_CONFIG.strings.URL_ADDED_BY} alice · 2024-03-09`,
    );
  });

  it("forwards the members through the real STALE_DATA_DETECTED handler", () => {
    emit(AppEvents.STALE_DATA_DETECTED, {
      utubID: UTUB_ID,
      urls: [makeURL(5, 7)],
      tags: [],
      members: [member(1, "owner"), member(7, "alice")],
    });

    expect(stackedBadge(5).text()).toBe(
      `${APP_CONFIG.strings.URL_ADDED_BY} alice · 2024-03-09`,
    );
  });
});
