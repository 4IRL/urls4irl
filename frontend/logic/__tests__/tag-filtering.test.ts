import {
  compareTags,
  computeURLVisibility,
  computeVisibleTagCounts,
  sortTagsByCount,
} from "../tag-filtering.js";
import type { SortableTag } from "../tag-filtering.js";
import type {
  TagMatchModeValue,
  TagSortValue,
} from "../../types/preferences.js";

function visibility(
  selectedTagIDs: number[],
  urlsWithTagIDs: { urlId: number; tagIDs: number[] }[],
  mode: TagMatchModeValue = "all",
) {
  return computeURLVisibility({ selectedTagIDs, urlsWithTagIDs, mode });
}

describe("computeURLVisibility", () => {
  describe.each<TagMatchModeValue>(["all", "any"])(
    "empty selections (%s)",
    (mode) => {
      it("returns all visible when no tags are selected", () => {
        const urls = [
          { urlId: 1, tagIDs: [10, 20] },
          { urlId: 2, tagIDs: [] },
        ];
        expect(visibility([], urls, mode)).toEqual([
          { urlId: 1, visible: true },
          { urlId: 2, visible: true },
        ]);
      });

      it("returns empty array when URL list is empty", () => {
        expect(visibility([1, 2], [], mode)).toEqual([]);
      });
    },
  );

  describe("AND filtering logic (mode all)", () => {
    it("marks URL visible when it has the single selected tag", () => {
      expect(visibility([10], [{ urlId: 1, tagIDs: [10, 20] }])).toEqual([
        { urlId: 1, visible: true },
      ]);
    });

    it("marks URL hidden when it is missing the selected tag", () => {
      expect(visibility([99], [{ urlId: 1, tagIDs: [10, 20] }])).toEqual([
        { urlId: 1, visible: false },
      ]);
    });

    it("marks URL visible only when it has ALL selected tags (AND logic)", () => {
      const urls = [{ urlId: 1, tagIDs: [10, 20] }];
      expect(visibility([10, 20], urls)).toEqual([{ urlId: 1, visible: true }]);
      expect(visibility([10, 99], urls)).toEqual([
        { urlId: 1, visible: false },
      ]);
    });

    it("handles a URL with no tags when tags are selected", () => {
      expect(visibility([10], [{ urlId: 1, tagIDs: [] }])).toEqual([
        { urlId: 1, visible: false },
      ]);
    });
  });

  describe("OR filtering logic (mode any)", () => {
    it("shows a URL carrying the single selected tag", () => {
      expect(visibility([10], [{ urlId: 1, tagIDs: [10, 20] }], "any")).toEqual(
        [{ urlId: 1, visible: true }],
      );
    });

    it("hides a URL carrying none of the selected tags", () => {
      expect(visibility([99], [{ urlId: 1, tagIDs: [10, 20] }], "any")).toEqual(
        [{ urlId: 1, visible: false }],
      );
    });

    it("shows a URL carrying at least one of several selected tags", () => {
      const urls = [{ urlId: 1, tagIDs: [10, 20] }];
      expect(visibility([10, 99], urls, "any")).toEqual([
        { urlId: 1, visible: true },
      ]);
      expect(visibility([98, 99], urls, "any")).toEqual([
        { urlId: 1, visible: false },
      ]);
    });

    it("hides an untagged URL when tags are selected", () => {
      expect(visibility([10], [{ urlId: 1, tagIDs: [] }], "any")).toEqual([
        { urlId: 1, visible: false },
      ]);
    });
  });

  describe("multiple URLs", () => {
    const urls = [
      { urlId: 1, tagIDs: [10, 20] },
      { urlId: 2, tagIDs: [20] },
      { urlId: 3, tagIDs: [] },
    ];

    it("returns correct visibility for each URL independently (all)", () => {
      expect(visibility([10, 20], urls)).toEqual([
        { urlId: 1, visible: true },
        { urlId: 2, visible: false },
        { urlId: 3, visible: false },
      ]);
    });

    it("returns correct visibility for each URL independently (any)", () => {
      expect(visibility([10, 20], urls, "any")).toEqual([
        { urlId: 1, visible: true },
        { urlId: 2, visible: true },
        { urlId: 3, visible: false },
      ]);
    });
  });
});

describe("computeVisibleTagCounts", () => {
  it("returns zero counts for all tags when URL list is empty", () => {
    const counts = computeVisibleTagCounts([], [1, 2, 3]);
    expect(counts.get("1")).toBe(0);
    expect(counts.get("2")).toBe(0);
    expect(counts.get("3")).toBe(0);
  });

  it("counts each tag correctly across visible URLs", () => {
    const visibleURLTagIDsList = [["1", "2"], ["2", "3"], ["1"]];
    const counts = computeVisibleTagCounts(visibleURLTagIDsList, [1, 2, 3]);
    expect(counts.get("1")).toBe(2);
    expect(counts.get("2")).toBe(2);
    expect(counts.get("3")).toBe(1);
  });

  it("keeps count at 0 for tags not on any visible URL", () => {
    const counts = computeVisibleTagCounts([["1"]], [1, 2]);
    expect(counts.get("2")).toBe(0);
  });

  it("returns a Map with string keys for all provided tag IDs", () => {
    const counts = computeVisibleTagCounts([], [10, 20]);
    expect(counts).toBeInstanceOf(Map);
    expect(counts.has("10")).toBe(true);
    expect(counts.has("20")).toBe(true);
  });
});

describe("sortTagsByCount", () => {
  it("returns empty array for empty input", () => {
    expect(sortTagsByCount([])).toEqual([]);
  });

  it("sorts tags descending by visibleCount", () => {
    const tags = [
      { id: 1, visibleCount: 1 },
      { id: 2, visibleCount: 5 },
      { id: 3, visibleCount: 3 },
    ];
    const result = sortTagsByCount(tags);
    expect(result.map((tag) => tag.id)).toEqual([2, 3, 1]);
  });

  it("does not mutate the original array", () => {
    const tags = [
      { id: 1, visibleCount: 1 },
      { id: 2, visibleCount: 5 },
    ];
    sortTagsByCount(tags);
    expect(tags[0].id).toBe(1);
  });

  it("handles tags with equal counts without error", () => {
    const tags = [
      { id: 1, visibleCount: 3 },
      { id: 2, visibleCount: 3 },
    ];
    const result = sortTagsByCount(tags);
    expect(result).toHaveLength(2);
    expect(result.every((tag) => tag.visibleCount === 3)).toBe(true);
  });

  it("keeps the input order for equal counts (stable, no tie-break)", () => {
    const tags = [
      { id: 9, visibleCount: 3 },
      { id: 1, visibleCount: 3 },
      { id: 5, visibleCount: 3 },
    ];
    expect(sortTagsByCount(tags).map((tag) => tag.id)).toEqual([9, 1, 5]);
  });
});

describe("compareTags", () => {
  function tag(partial: Partial<SortableTag> & { id: number }): SortableTag {
    return { name: `tag${partial.id}`, total: 0, inView: 0, ...partial };
  }

  function sortedIDs(tags: SortableTag[], sort: TagSortValue): number[] {
    return [...tags]
      .sort((left, right) => compareTags({ left, right, sort }))
      .map((item) => item.id);
  }

  it("most_used orders by total descending", () => {
    const tags = [
      tag({ id: 1, name: "a", total: 1 }),
      tag({ id: 2, name: "b", total: 9 }),
      tag({ id: 3, name: "c", total: 4 }),
    ];
    expect(sortedIDs(tags, "most_used")).toEqual([2, 3, 1]);
  });

  it("most_used breaks ties by name then id", () => {
    const tags = [
      tag({ id: 1, name: "b", total: 2 }),
      tag({ id: 2, name: "a", total: 2 }),
      tag({ id: 3, name: "a", total: 2 }),
    ];
    expect(sortedIDs(tags, "most_used")).toEqual([2, 3, 1]);
  });

  it("name_az orders alphabetically", () => {
    const tags = [
      tag({ id: 1, name: "pear" }),
      tag({ id: 2, name: "apple" }),
      tag({ id: 3, name: "mango" }),
    ];
    expect(sortedIDs(tags, "name_az")).toEqual([2, 3, 1]);
  });

  it("name_az ignores case, falling back to id for case-only differences", () => {
    const tags = [
      tag({ id: 7, name: "Zebra" }),
      tag({ id: 5, name: "apple" }),
      tag({ id: 3, name: "Apple" }),
    ];
    expect(sortedIDs(tags, "name_az")).toEqual([3, 5, 7]);
  });

  it("newest orders by id descending", () => {
    const tags = [tag({ id: 2 }), tag({ id: 9 }), tag({ id: 5 })];
    expect(sortedIDs(tags, "newest")).toEqual([9, 5, 2]);
  });

  it("oldest orders by id ascending", () => {
    const tags = [tag({ id: 2 }), tag({ id: 9 }), tag({ id: 5 })];
    expect(sortedIDs(tags, "oldest")).toEqual([2, 5, 9]);
  });

  it("most_in_view orders by inView descending with name then id ties", () => {
    const tags = [
      tag({ id: 1, name: "b", inView: 3 }),
      tag({ id: 2, name: "a", inView: 3 }),
      tag({ id: 3, name: "c", inView: 8 }),
    ];
    expect(sortedIDs(tags, "most_in_view")).toEqual([3, 2, 1]);
  });

  it("is independent of the input order", () => {
    const tags = [
      tag({ id: 1, name: "a", total: 2 }),
      tag({ id: 2, name: "a", total: 2 }),
      tag({ id: 3, name: "b", total: 2 }),
    ];
    expect(sortedIDs([...tags].reverse(), "most_used")).toEqual(
      sortedIDs(tags, "most_used"),
    );
  });
});
