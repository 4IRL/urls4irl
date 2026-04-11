import { diffIDLists } from "../deck-diffing.js";

describe("diffIDLists", () => {
  it("returns empty result for two empty lists", () => {
    expect(diffIDLists([], [])).toEqual({
      toRemove: [],
      toAdd: [],
      toUpdate: [],
    });
  });

  it("returns only additions when old list is empty", () => {
    expect(diffIDLists([], [1, 2, 3])).toEqual({
      toRemove: [],
      toAdd: [1, 2, 3],
      toUpdate: [],
    });
  });

  it("returns only removals when new list is empty", () => {
    expect(diffIDLists([1, 2, 3], [])).toEqual({
      toRemove: [1, 2, 3],
      toAdd: [],
      toUpdate: [],
    });
  });

  it("returns only updates when old and new lists are identical", () => {
    expect(diffIDLists([1, 2, 3], [1, 2, 3])).toEqual({
      toRemove: [],
      toAdd: [],
      toUpdate: [1, 2, 3],
    });
  });

  it("correctly categorises additions, removals, and updates together", () => {
    const result = diffIDLists([1, 2, 3], [2, 3, 4]);
    expect(result.toRemove).toEqual([1]);
    expect(result.toAdd).toEqual([4]);
    expect(result.toUpdate).toEqual([2, 3]);
  });

  it("handles disjoint old and new lists (no overlap)", () => {
    expect(diffIDLists([1, 2], [3, 4])).toEqual({
      toRemove: [1, 2],
      toAdd: [3, 4],
      toUpdate: [],
    });
  });

  it("does not mutate the input arrays", () => {
    const old = [1, 2];
    const next = [2, 3];
    diffIDLists(old, next);
    expect(old).toEqual([1, 2]);
    expect(next).toEqual([2, 3]);
  });
});
