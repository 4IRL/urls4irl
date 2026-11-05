import type { TagSortValue } from "../../../../types/preferences.js";
import { applyTagSort, reapplyTagSortForNonDefault } from "../filtering.js";
import { effectiveTagDisplaySettings } from "../../../tags/display-settings.js";

vi.mock("../../../tags/display-settings.js", () => ({
  effectiveTagDisplaySettings: vi.fn(),
}));

const $ = window.jQuery;

interface ChipSpec {
  id: number;
  name: string;
  inView: number;
  total: number;
}

const CHIPS: ChipSpec[] = [
  { id: 1, name: "banana", inView: 1, total: 9 },
  { id: 2, name: "Apple", inView: 5, total: 2 },
  { id: 3, name: "cherry", inView: 3, total: 5 },
];

function mountChips(chips: ChipSpec[]) {
  document.body.innerHTML =
    '<div id="listTags">' +
    chips
      .map(
        (chip) =>
          `<div class="tagFilter" data-utub-tag-id="${chip.id}" tabindex="0">` +
          `<span>${chip.name}</span>` +
          '<span class="tagAppliedToUrlsCount">' +
          `<span class="tagCountInView">${chip.inView}</span>` +
          '<span class="tagCountSep"> / </span>' +
          `<span class="tagCountTotal">${chip.total}</span></span></div>`,
      )
      .join("") +
    "</div>";
}

function order(): number[] {
  return $("#listTags > .tagFilter")
    .get()
    .map((el) => Number($(el).attr("data-utub-tag-id")));
}

function useSort(tagSort: TagSortValue) {
  vi.mocked(effectiveTagDisplaySettings).mockReturnValue({
    tagSort,
    tagMatchMode: "all",
  } as ReturnType<typeof effectiveTagDisplaySettings>);
}

describe("applyTagSort", () => {
  beforeEach(() => {
    mountChips(CHIPS);
    useSort("most_in_view");
  });

  it.each([
    { sort: "most_in_view" as const, expected: [2, 3, 1] },
    { sort: "most_used" as const, expected: [1, 3, 2] },
    { sort: "name_az" as const, expected: [2, 1, 3] },
    { sort: "newest" as const, expected: [3, 2, 1] },
    { sort: "oldest" as const, expected: [1, 2, 3] },
  ])("orders by $sort", ({ sort, expected }) => {
    useSort(sort);
    applyTagSort();
    expect(order()).toEqual(expected);
  });

  it("re-stripes after reordering", () => {
    useSort("name_az");
    applyTagSort();
    const striped = $("#listTags > .tagFilter")
      .get()
      .map((el) => $(el).hasClass("tag-stripe"));
    expect(striped).toEqual([false, true, false]);
  });

  it("keeps focus on the same chip after the reorder", () => {
    const focusedChip = $('.tagFilter[data-utub-tag-id="1"]')[0];
    focusedChip.focus();
    useSort("name_az");
    applyTagSort();
    expect(document.activeElement).toBe(focusedChip);
    expect(order()).toEqual([2, 1, 3]);
  });

  it("defers while a tag drag is active and runs once the drag ends", () => {
    useSort("name_az");
    $('.tagFilter[data-utub-tag-id="3"]').addClass("tagDragging");
    applyTagSort();
    applyTagSort();
    expect(order()).toEqual([1, 2, 3]);

    $(".tagDragging").removeClass("tagDragging");
    document.dispatchEvent(new Event("dragend"));
    expect(order()).toEqual([2, 1, 3]);

    // The deferral listener is one-shot: a later reorder request is not blocked.
    mountChips(CHIPS);
    applyTagSort();
    expect(order()).toEqual([2, 1, 3]);
  });
});

describe("reapplyTagSortForNonDefault", () => {
  beforeEach(() => {
    mountChips(CHIPS);
  });

  it("does nothing under the default most-in-view sort", () => {
    useSort("most_in_view");
    reapplyTagSortForNonDefault();
    expect(order()).toEqual([1, 2, 3]);
  });

  it("re-sorts under a non-default sort (create/delete/count-change triggers)", () => {
    useSort("most_used");
    reapplyTagSortForNonDefault();
    expect(order()).toEqual([1, 3, 2]);
  });

  it("picks up a changed count under a non-default sort", () => {
    useSort("most_used");
    reapplyTagSortForNonDefault();
    $('.tagFilter[data-utub-tag-id="2"] .tagCountTotal').text("20");
    reapplyTagSortForNonDefault();
    expect(order()).toEqual([2, 1, 3]);
  });
});
