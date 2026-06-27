import type { UtubTag } from "../../../../types/url.js";

import { mergeAppliedTagsIntoStore } from "../combobox-state.js";
import { createTagBadgeInURL } from "../tags.js";
import { isTagInUTubTagDeck } from "../../../tags/utils.js";
import { buildTagFilterInDeck } from "../../../tags/tags.js";
import {
  updateTagFilterCount,
  TagCountOperation,
} from "../../cards/filtering.js";
import { renderAppliedTagsForUrl } from "../tag-render.js";

vi.mock("../combobox-state.js", () => ({
  mergeAppliedTagsIntoStore: vi.fn(),
}));

vi.mock("../tags.js", () => ({
  createTagBadgeInURL: vi.fn(() =>
    window.jQuery("<span class='tagBadge'></span>"),
  ),
}));

vi.mock("../../../tags/utils.js", () => ({
  isTagInUTubTagDeck: vi.fn(() => false),
}));

vi.mock("../../../tags/tags.js", () => ({
  buildTagFilterInDeck: vi.fn(() =>
    window.jQuery("<div class='tagFilter'></div>"),
  ),
}));

vi.mock("../../cards/filtering.js", () => ({
  updateTagFilterCount: vi.fn(),
  TagCountOperation: { INCREMENT: 1, DECREMENT: -1 },
}));

const $ = window.jQuery;

const PAGE_HTML = `
  <div id="listTags"></div>
  <div id="unselectAllTagFilters" class="hidden"></div>
  <div id="utubTagBtnUpdateAllOpen" class="hidden"></div>
  <div class="urlRow">
    <div class="urlTagsContainer"></div>
  </div>
`;

function makeTag(id: number, tagString: string, tagApplied = 1): UtubTag {
  return { id, tagString, tagApplied };
}

describe("renderAppliedTagsForUrl", () => {
  let urlCard: JQuery;

  beforeEach(() => {
    document.body.innerHTML = PAGE_HTML;
    urlCard = $(".urlRow");
    vi.clearAllMocks();
    vi.mocked(isTagInUTubTagDeck).mockReturnValue(false);
  });

  it("snapshots isTagInUTubTagDeck for each tag BEFORE mergeAppliedTagsIntoStore", () => {
    const appliedTags = [makeTag(1, "python"), makeTag(2, "web")];

    renderAppliedTagsForUrl({
      appliedTags,
      utubUrlTagIDs: [1, 2],
      urlCard,
      utubID: 99,
    });

    expect(isTagInUTubTagDeck).toHaveBeenCalledWith(1);
    expect(isTagInUTubTagDeck).toHaveBeenCalledWith(2);
    const lastSnapshotCall = Math.max(
      ...vi.mocked(isTagInUTubTagDeck).mock.invocationCallOrder,
    );
    const mergeCall = vi.mocked(mergeAppliedTagsIntoStore).mock
      .invocationCallOrder[0];
    expect(lastSnapshotCall).toBeLessThan(mergeCall);
  });

  it("calls mergeAppliedTagsIntoStore exactly once with the applied tags", () => {
    const appliedTags = [makeTag(1, "python")];

    renderAppliedTagsForUrl({
      appliedTags,
      utubUrlTagIDs: [1],
      urlCard,
      utubID: 99,
    });

    expect(mergeAppliedTagsIntoStore).toHaveBeenCalledTimes(1);
    expect(mergeAppliedTagsIntoStore).toHaveBeenCalledWith({ appliedTags });
  });

  it("appends one badge per applied tag into .urlTagsContainer with the right args", () => {
    const appliedTags = [makeTag(1, "python"), makeTag(2, "web")];

    renderAppliedTagsForUrl({
      appliedTags,
      utubUrlTagIDs: [1, 2],
      urlCard,
      utubID: 99,
    });

    expect(createTagBadgeInURL).toHaveBeenCalledTimes(2);
    expect(createTagBadgeInURL).toHaveBeenCalledWith(1, "python", urlCard, 99);
    expect(createTagBadgeInURL).toHaveBeenCalledWith(2, "web", urlCard, 99);
    expect(urlCard.find(".urlTagsContainer .tagBadge").length).toBe(2);
  });

  it("sets data-utub-url-tag-ids from utubUrlTagIDs", () => {
    renderAppliedTagsForUrl({
      appliedTags: [makeTag(1, "python")],
      utubUrlTagIDs: [1, 7, 9],
      urlCard,
      utubID: 99,
    });

    expect(urlCard.attr("data-utub-url-tag-ids")).toBe("1,7,9");
  });

  it("builds a deck filter (not updateTagFilterCount) for a tag NOT yet in deck", () => {
    vi.mocked(isTagInUTubTagDeck).mockReturnValue(false);

    renderAppliedTagsForUrl({
      appliedTags: [makeTag(5, "fresh")],
      utubUrlTagIDs: [5],
      urlCard,
      utubID: 99,
    });

    expect(buildTagFilterInDeck).toHaveBeenCalledWith(99, 5, "fresh", 1);
    expect(updateTagFilterCount).not.toHaveBeenCalled();
    expect($("#listTags .tagFilter").length).toBe(1);
  });

  it("updates the count (not buildTagFilterInDeck) for a tag already in deck", () => {
    vi.mocked(isTagInUTubTagDeck).mockReturnValue(true);

    renderAppliedTagsForUrl({
      appliedTags: [makeTag(3, "existing", 4)],
      utubUrlTagIDs: [3],
      urlCard,
      utubID: 99,
    });

    expect(updateTagFilterCount).toHaveBeenCalledWith(
      3,
      4,
      TagCountOperation.INCREMENT,
    );
    expect(buildTagFilterInDeck).not.toHaveBeenCalled();
  });

  it("shows #unselectAllTagFilters when at least one tag was applied", () => {
    renderAppliedTagsForUrl({
      appliedTags: [makeTag(1, "python")],
      utubUrlTagIDs: [1],
      urlCard,
      utubID: 99,
    });

    expect($("#unselectAllTagFilters").hasClass("hidden")).toBe(false);
  });

  it("does NOT show #unselectAllTagFilters when no tags were applied", () => {
    renderAppliedTagsForUrl({
      appliedTags: [],
      utubUrlTagIDs: [],
      urlCard,
      utubID: 99,
    });

    expect($("#unselectAllTagFilters").hasClass("hidden")).toBe(true);
  });

  it("shows #utubTagBtnUpdateAllOpen when a new deck filter was built", () => {
    vi.mocked(isTagInUTubTagDeck).mockReturnValue(false);

    renderAppliedTagsForUrl({
      appliedTags: [makeTag(5, "fresh")],
      utubUrlTagIDs: [5],
      urlCard,
      utubID: 99,
    });

    expect($("#utubTagBtnUpdateAllOpen").hasClass("hidden")).toBe(false);
  });

  it("does NOT show #utubTagBtnUpdateAllOpen when no new deck filter was built", () => {
    vi.mocked(isTagInUTubTagDeck).mockReturnValue(true);

    renderAppliedTagsForUrl({
      appliedTags: [makeTag(3, "existing", 4)],
      utubUrlTagIDs: [3],
      urlCard,
      utubID: 99,
    });

    expect($("#utubTagBtnUpdateAllOpen").hasClass("hidden")).toBe(true);
  });
});
