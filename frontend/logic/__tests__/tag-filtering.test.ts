import {
  computeURLVisibility,
  computeVisibleTagCounts,
  sortTagsByCount,
} from "../tag-filtering.js";

describe("computeURLVisibility", () => {
  describe("empty selections", () => {
    it("returns all visible when no tags are selected", () => {
      const urls = [
        { urlId: 1, tagIDs: [10, 20] },
        { urlId: 2, tagIDs: [] },
      ];
      const result = computeURLVisibility([], urls);
      expect(result).toEqual([
        { urlId: 1, visible: true },
        { urlId: 2, visible: true },
      ]);
    });

    it("returns empty array when URL list is empty", () => {
      expect(computeURLVisibility([1, 2], [])).toEqual([]);
    });
  });

  describe("AND filtering logic", () => {
    it("marks URL visible when it has the single selected tag", () => {
      const result = computeURLVisibility(
        [10],
        [{ urlId: 1, tagIDs: [10, 20] }],
      );
      expect(result).toEqual([{ urlId: 1, visible: true }]);
    });

    it("marks URL hidden when it is missing the selected tag", () => {
      const result = computeURLVisibility(
        [99],
        [{ urlId: 1, tagIDs: [10, 20] }],
      );
      expect(result).toEqual([{ urlId: 1, visible: false }]);
    });

    it("marks URL visible only when it has ALL selected tags (AND logic)", () => {
      const urls = [{ urlId: 1, tagIDs: [10, 20] }];
      expect(computeURLVisibility([10, 20], urls)).toEqual([
        { urlId: 1, visible: true },
      ]);
      expect(computeURLVisibility([10, 99], urls)).toEqual([
        { urlId: 1, visible: false },
      ]);
    });

    it("handles a URL with no tags when tags are selected", () => {
      const result = computeURLVisibility([10], [{ urlId: 1, tagIDs: [] }]);
      expect(result).toEqual([{ urlId: 1, visible: false }]);
    });
  });

  describe("multiple URLs", () => {
    it("returns correct visibility for each URL independently", () => {
      const urls = [
        { urlId: 1, tagIDs: [10, 20] },
        { urlId: 2, tagIDs: [20] },
        { urlId: 3, tagIDs: [] },
      ];
      const result = computeURLVisibility([10, 20], urls);
      expect(result).toEqual([
        { urlId: 1, visible: true },
        { urlId: 2, visible: false },
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
    expect(result.map((t) => t.id)).toEqual([2, 3, 1]);
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
    expect(result.every((t) => t.visibleCount === 3)).toBe(true);
  });
});
