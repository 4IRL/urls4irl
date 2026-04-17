import {
  currentTagDeckIDs,
  isATagSelected,
  isTagInUTubTagDeck,
} from "../utils.js";
import { resetStore, setState } from "../../../store/app-store.js";

describe("currentTagDeckIDs", () => {
  beforeEach(() => {
    resetStore();
  });

  it("returns an empty array when the store holds no tags", () => {
    expect(currentTagDeckIDs()).toEqual([]);
  });

  it("returns the IDs of every tag in the store, preserving order", () => {
    setState({
      tags: [
        { id: 1, tagString: "alpha", tagApplied: 0 },
        { id: 7, tagString: "bravo", tagApplied: 0 },
        { id: 3, tagString: "charlie", tagApplied: 0 },
      ],
    });
    expect(currentTagDeckIDs()).toEqual([1, 7, 3]);
  });
});

describe("isTagInUTubTagDeck", () => {
  beforeEach(() => {
    resetStore();
  });

  it("returns false when the store has no tags", () => {
    expect(isTagInUTubTagDeck(1)).toBe(false);
  });

  it("returns true when the queried tag ID exists in the store", () => {
    setState({
      tags: [
        { id: 1, tagString: "alpha", tagApplied: 0 },
        { id: 2, tagString: "bravo", tagApplied: 0 },
      ],
    });
    expect(isTagInUTubTagDeck(2)).toBe(true);
  });

  it("returns false when the queried tag ID is absent from the store", () => {
    setState({
      tags: [{ id: 1, tagString: "alpha", tagApplied: 0 }],
    });
    expect(isTagInUTubTagDeck(999)).toBe(false);
  });
});

describe("isATagSelected", () => {
  beforeEach(() => {
    resetStore();
  });

  it("returns false when selectedTagIDs is empty", () => {
    expect(isATagSelected()).toBe(false);
  });

  it("returns true when at least one tag is selected", () => {
    setState({ selectedTagIDs: [5] });
    expect(isATagSelected()).toBe(true);
  });

  it("returns true when multiple tags are selected", () => {
    setState({ selectedTagIDs: [1, 2, 3] });
    expect(isATagSelected()).toBe(true);
  });
});
