import {
  dedupe,
  removeIds,
  symmetricToggle,
  toggleId,
} from "../multi-select.js";

describe("toggleId", () => {
  it("adds an id that is not present", () => {
    expect(toggleId([1, 2], 3)).toEqual([1, 2, 3]);
  });

  it("removes an id that is already present", () => {
    expect(toggleId([1, 2, 3], 2)).toEqual([1, 3]);
  });

  it("returns a new array and does not mutate the input", () => {
    const input = [1, 2];
    const result = toggleId(input, 3);
    expect(result).not.toBe(input);
    expect(input).toEqual([1, 2]);
  });

  it("adds to an empty selection", () => {
    expect(toggleId([], 1)).toEqual([1]);
  });

  it("toggles a zero id off (numeric-equality contract)", () => {
    expect(toggleId([0], 0)).toEqual([]);
  });
});

describe("removeIds", () => {
  it("removes the given ids, ignoring ids not present", () => {
    expect(removeIds([1, 2, 3], [2, 4])).toEqual([1, 3]);
  });

  it("returns a new array and does not mutate the input", () => {
    const input = [1, 2, 3];
    const result = removeIds(input, [2]);
    expect(result).not.toBe(input);
    expect(input).toEqual([1, 2, 3]);
  });

  it("returns a fresh passthrough array when nothing is removed", () => {
    const input = [1, 2];
    const result = removeIds(input, []);
    expect(result).toEqual([1, 2]);
    expect(result).not.toBe(input);
  });

  it("returns an empty array when removing from an empty selection", () => {
    expect(removeIds([], [1])).toEqual([]);
  });
});

describe("dedupe", () => {
  it("removes duplicate ids, preserving first-seen order", () => {
    expect(dedupe([1, 1, 2])).toEqual([1, 2]);
  });

  it("returns a new array and does not mutate the input", () => {
    const input = [1, 1, 2];
    const result = dedupe(input);
    expect(result).not.toBe(input);
    expect(input).toEqual([1, 1, 2]);
  });

  it("returns an empty array for an empty input", () => {
    expect(dedupe([])).toEqual([]);
  });
});

describe("symmetricToggle", () => {
  it("adds visible ids not selected and removes visible ids already selected", () => {
    // current [1] with visible {1,2,3}: 1 flips off, 2 and 3 flip on.
    expect(symmetricToggle([1], new Set([1, 2, 3]))).toEqual([2, 3]);
  });

  it("preserves selected ids not in the toggle set (hidden-but-selected survivors)", () => {
    // 99 is hidden (not in the visible set) and stays selected; 1 flips off,
    // 2 flips on.
    expect(symmetricToggle([1, 99], new Set([1, 2]))).toEqual([99, 2]);
  });

  it("selects all when nothing is currently selected", () => {
    expect(symmetricToggle([], new Set([1, 2, 3]))).toEqual([1, 2, 3]);
  });

  it("deselects the whole visible set when all are selected", () => {
    expect(symmetricToggle([1, 2, 3], new Set([1, 2, 3]))).toEqual([]);
  });

  it("is a no-op on the visible axis for an empty toggle set (only survivors remain)", () => {
    expect(symmetricToggle([1, 2], new Set())).toEqual([1, 2]);
  });

  it("returns a new array and does not mutate the inputs", () => {
    const current = [1, 2];
    const toggle = new Set([2, 3]);
    const result = symmetricToggle(current, toggle);
    expect(result).not.toBe(current);
    expect(current).toEqual([1, 2]);
    expect([...toggle]).toEqual([2, 3]);
  });
});
