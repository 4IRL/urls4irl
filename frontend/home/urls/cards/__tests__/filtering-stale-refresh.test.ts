// Real event bus with both urls/deck.ts and cards/filtering.ts loaded: pins the
// listener order (filtering's STALE_DATA_DETECTED listener runs BEFORE
// updateURLDeck adds new cards) and the end-of-updateURLDeck tag-filter re-apply.
import "../../deck.js";
import { AppEvents, emit } from "../../../../lib/event-bus.js";
import { getState, resetStore, setState } from "../../../../store/app-store.js";
import type { UtubUrlItem } from "../../../../types/url.js";

vi.mock("../cards.js", () => ({
  createURLBlock: vi.fn((url: UtubUrlItem) =>
    window.jQuery(
      `<div class="urlRow" utuburlid="${url.utubUrlID}" filterable="true" data-utub-url-tag-ids="${url.utubUrlTagIDs.join(",")}"></div>`,
    ),
  ),
  updateURLAfterFindingStaleData: vi.fn(),
  newURLInputRemoveEventListeners: vi.fn(),
  newURLInputAddEventListeners: vi.fn(),
  setFocusEventListenersOnURLCard: vi.fn(),
}));

vi.mock("../swipe.js", () => ({
  triggerURLSwipeNudgeIfEligible: vi.fn(),
}));

vi.mock("../../../../lib/tooltips.js", () => ({
  disposeTooltipsWithin: vi.fn(),
  hideTooltip: vi.fn(),
}));

vi.mock("../../../utubs/header-fit.js", () => ({
  fitUTubHeaderAndSubheader: vi.fn(),
}));

const $ = window.jQuery;
const TAG_ID = 5;

function makeUrl(utubUrlID: number, utubUrlTagIDs: number[]): UtubUrlItem {
  return {
    utubUrlID,
    urlString: `https://example${utubUrlID}.com`,
    urlTitle: `Example ${utubUrlID}`,
    utubUrlTagIDs,
    canDelete: true,
    addedAt: "2024-01-01T00:00:00+00:00",
    addedByUserID: 1,
  };
}

describe("tag filter survives a stale-data refresh that adds URLs", () => {
  beforeEach(() => {
    resetStore();
    document.body.innerHTML = `
      <p id="URLTagFilterNoResults" class="hidden"></p>
      <span id="URLTagFilterAnnouncement"></span>
      <div id="listTags"></div>
      <div id="SearchURLWrap"><input id="URLContentSearch" type="text" value="" /></div>
      <p id="URLSearchNoResults" class="hidden"></p>
      <div id="listURLs">
        <div class="urlRow" utuburlid="1" filterable="true"></div>
      </div>
    `;
    setState({
      urls: [makeUrl(1, [TAG_ID])],
      selectedTagIDs: [TAG_ID],
    });
  });

  afterEach(() => {
    resetStore();
    document.body.innerHTML = "";
  });

  it("leaves a newly added non-matching URL card hidden under the active filter", () => {
    const tags = [{ id: TAG_ID, tagString: "tag", tagApplied: 1 }];

    emit(AppEvents.STALE_DATA_DETECTED, {
      utubID: 1,
      urls: [makeUrl(1, [TAG_ID]), makeUrl(2, [])],
      tags,
      members: [],
    });

    expect($(".urlRow[utuburlid=1]").attr("filterable")).toBe("true");
    expect($(".urlRow[utuburlid=2]").attr("filterable")).toBe("false");
    expect(getState().selectedTagIDs).toEqual([TAG_ID]);
  });

  it("shows a newly added matching URL card under the active filter", () => {
    const tags = [{ id: TAG_ID, tagString: "tag", tagApplied: 2 }];

    emit(AppEvents.STALE_DATA_DETECTED, {
      utubID: 1,
      urls: [makeUrl(1, [TAG_ID]), makeUrl(2, [TAG_ID])],
      tags,
      members: [],
    });

    expect($(".urlRow[utuburlid=2]").attr("filterable")).toBe("true");
  });
});
