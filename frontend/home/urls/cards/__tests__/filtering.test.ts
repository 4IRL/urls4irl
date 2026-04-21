import { updateURLsAndTagSubheaderWhenTagSelected } from "../filtering.js";
import { AppEvents, emit } from "../../../../lib/event-bus.js";

vi.mock("../../../../logic/tag-filtering.js", () => ({
  computeURLVisibility: vi.fn(() => []),
  computeVisibleTagCounts: vi.fn(() => new Map()),
  sortTagsByCount: vi.fn((tags: unknown[]) => tags),
}));

vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ selectedTagIDs: [], urls: [], tags: [] })),
  setState: vi.fn(),
  resetStore: vi.fn(),
}));

import { computeURLVisibility } from "../../../../logic/tag-filtering.js";
import { getState } from "../../../../store/app-store.js";

const $ = window.jQuery;

const TAG_FILTER_NO_RESULTS_TEXT = "No URLs match selected tags";

const FIXTURE_HTML = `
  <p id="URLTagFilterNoResults" class="hidden"></p>
  <span id="URLTagFilterAnnouncement" aria-live="polite" class="visually-hidden"></span>
  <div id="listTags"></div>
  <div id="SearchURLWrap" class="hidden"><input id="URLContentSearch" type="text" value="" /></div>
  <p id="URLSearchNoResults" class="hidden"></p>
  <div id="listURLs">
    <div class="urlRow" utuburlid="1" filterable="true"></div>
    <div class="urlRow" utuburlid="2" filterable="true"></div>
    <div class="urlRow" utuburlid="3" filterable="true"></div>
  </div>
`;

const EMPTY_FIXTURE_HTML = `
  <p id="URLTagFilterNoResults" class="hidden"></p>
  <span id="URLTagFilterAnnouncement" aria-live="polite" class="visually-hidden"></span>
  <div id="listTags"></div>
  <div id="SearchURLWrap" class="hidden"><input id="URLContentSearch" type="text" value="" /></div>
  <p id="URLSearchNoResults" class="hidden"></p>
  <div id="listURLs"></div>
`;

describe("Tag Filter Empty State", () => {
  beforeEach(() => {
    document.body.innerHTML = FIXTURE_HTML;
    vi.clearAllMocks();

    vi.mocked(getState).mockReturnValue({
      selectedTagIDs: [99],
      tags: [],
      urls: [
        { utubUrlID: 1, utubUrlTagIDs: [] },
        { utubUrlID: 2, utubUrlTagIDs: [] },
        { utubUrlID: 3, utubUrlTagIDs: [] },
      ],
    } as unknown as ReturnType<typeof getState>);
  });

  it("shows message when all URLs hidden by tag filter", () => {
    vi.mocked(computeURLVisibility).mockReturnValue([
      { urlId: 1, visible: false },
      { urlId: 2, visible: false },
      { urlId: 3, visible: false },
    ]);

    updateURLsAndTagSubheaderWhenTagSelected();

    const noResults = $("#URLTagFilterNoResults");
    expect(noResults.hasClass("hidden")).toBe(false);
    expect(noResults.text()).toBe(TAG_FILTER_NO_RESULTS_TEXT);
  });

  it("hides message when tags unselected (all URLs visible)", () => {
    $("#URLTagFilterNoResults")
      .removeClass("hidden")
      .text(TAG_FILTER_NO_RESULTS_TEXT);

    vi.mocked(getState).mockReturnValue({
      selectedTagIDs: [],
      tags: [],
      urls: [
        { utubUrlID: 1, utubUrlTagIDs: [] },
        { utubUrlID: 2, utubUrlTagIDs: [] },
        { utubUrlID: 3, utubUrlTagIDs: [] },
      ],
    } as unknown as ReturnType<typeof getState>);

    vi.mocked(computeURLVisibility).mockReturnValue([
      { urlId: 1, visible: true },
      { urlId: 2, visible: true },
      { urlId: 3, visible: true },
    ]);

    updateURLsAndTagSubheaderWhenTagSelected();

    expect($("#URLTagFilterNoResults").hasClass("hidden")).toBe(true);
  });

  it("does not show message when some URLs are visible", () => {
    vi.mocked(computeURLVisibility).mockReturnValue([
      { urlId: 1, visible: true },
      { urlId: 2, visible: false },
      { urlId: 3, visible: true },
    ]);

    updateURLsAndTagSubheaderWhenTagSelected();

    expect($("#URLTagFilterNoResults").hasClass("hidden")).toBe(true);
  });

  it("does not show message when UTub has zero URLs", () => {
    document.body.innerHTML = EMPTY_FIXTURE_HTML;

    vi.mocked(getState).mockReturnValue({
      selectedTagIDs: [99],
      tags: [],
      urls: [],
    } as unknown as ReturnType<typeof getState>);

    vi.mocked(computeURLVisibility).mockReturnValue([]);

    updateURLsAndTagSubheaderWhenTagSelected();

    expect($("#URLTagFilterNoResults").hasClass("hidden")).toBe(true);
  });

  it("sets aria-live announcement when showing message", () => {
    vi.mocked(computeURLVisibility).mockReturnValue([
      { urlId: 1, visible: false },
      { urlId: 2, visible: false },
      { urlId: 3, visible: false },
    ]);

    updateURLsAndTagSubheaderWhenTagSelected();

    expect($("#URLTagFilterAnnouncement").text()).toBe(
      TAG_FILTER_NO_RESULTS_TEXT,
    );
  });

  it("clears aria-live announcement when hiding message", () => {
    $("#URLTagFilterNoResults")
      .removeClass("hidden")
      .text(TAG_FILTER_NO_RESULTS_TEXT);
    $("#URLTagFilterAnnouncement").text(TAG_FILTER_NO_RESULTS_TEXT);

    vi.mocked(computeURLVisibility).mockReturnValue([
      { urlId: 1, visible: true },
      { urlId: 2, visible: true },
      { urlId: 3, visible: true },
    ]);

    vi.mocked(getState).mockReturnValue({
      selectedTagIDs: [],
      tags: [],
      urls: [
        { utubUrlID: 1, utubUrlTagIDs: [] },
        { utubUrlID: 2, utubUrlTagIDs: [] },
        { utubUrlID: 3, utubUrlTagIDs: [] },
      ],
    } as unknown as ReturnType<typeof getState>);

    updateURLsAndTagSubheaderWhenTagSelected();

    expect($("#URLTagFilterAnnouncement").text()).toBe("");
  });

  it("hides message on UTUB_SELECTED event", () => {
    $("#URLTagFilterNoResults")
      .removeClass("hidden")
      .text(TAG_FILTER_NO_RESULTS_TEXT);
    $("#URLTagFilterAnnouncement").text(TAG_FILTER_NO_RESULTS_TEXT);

    emit(AppEvents.UTUB_SELECTED, {
      utubID: 1,
      utubName: "Test",
      urls: [],
      tags: [],
      members: [],
      utubOwnerID: 1,
      isCurrentUserOwner: true,
      currentUserID: 1,
    });

    expect($("#URLTagFilterNoResults").hasClass("hidden")).toBe(true);
    expect($("#URLTagFilterAnnouncement").text()).toBe("");
  });
});
