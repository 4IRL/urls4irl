import { dedupe, removeIds, toggleId } from "../multi-select.js";

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
