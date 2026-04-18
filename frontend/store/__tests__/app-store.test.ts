import { getState, setState, resetStore } from "../app-store.js";

beforeEach(() => {
  resetStore();
});

describe("getState", () => {
  it("returns a copy — mutations to the copy do not affect internal state", () => {
    const state = getState();
    state.activeUTubID = 999;
    expect(getState().activeUTubID).toBeNull();
  });

  it("has all expected keys with default values on reset", () => {
    const state = getState();
    expect(state.utubs).toEqual([]);
    expect(state.activeUTubID).toBeNull();
    expect(state.activeUTubName).toBeNull();
    expect(state.activeUTubDescription).toBeNull();
    expect(state.isCurrentUserOwner).toBe(false);
    expect(state.currentUserID).toBeNull();
    expect(state.utubOwnerID).toBeNull();
    expect(state.selectedURLCardID).toBeNull();
    expect(state.selectedTagIDs).toEqual([]);
    expect(state.urls).toEqual([]);
    expect(state.tags).toEqual([]);
    expect(state.members).toEqual([]);
  });
});

describe("setState", () => {
  it("updates only the specified key, leaves all others unchanged", () => {
    setState({ activeUTubID: 5 });
    const state = getState();
    expect(state.activeUTubID).toBe(5);
    expect(state.activeUTubName).toBeNull();
    expect(state.utubs).toEqual([]);
    expect(state.isCurrentUserOwner).toBe(false);
  });

  it("sequential setState calls accumulate correctly without unexpected resets", () => {
    setState({ activeUTubID: 5 });
    setState({ activeUTubName: "My UTub" });
    setState({ isCurrentUserOwner: true });
    const state = getState();
    expect(state.activeUTubID).toBe(5);
    expect(state.activeUTubName).toBe("My UTub");
    expect(state.isCurrentUserOwner).toBe(true);
  });

  it("can update array fields", () => {
    setState({ selectedTagIDs: [1, 2, 3] });
    expect(getState().selectedTagIDs).toEqual([1, 2, 3]);
  });
});

describe("store as data source", () => {
  it("maps urls to {urlId, tagIDs} matching what DOM traversal would return", () => {
    setState({
      urls: [
        {
          utubUrlID: 1,
          urlString: "http://a.com",
          urlTitle: "A",
          utubUrlTagIDs: [10, 20],
          canDelete: true,
        },
        {
          utubUrlID: 2,
          urlString: "http://b.com",
          urlTitle: "B",
          utubUrlTagIDs: [],
          canDelete: false,
        },
      ],
    });
    const result = (
      getState().urls as { utubUrlID: number; utubUrlTagIDs: number[] }[]
    ).map((url) => ({
      urlId: url.utubUrlID,
      tagIDs: url.utubUrlTagIDs,
    }));
    expect(result).toEqual([
      { urlId: 1, tagIDs: [10, 20] },
      { urlId: 2, tagIDs: [] },
    ]);
  });
});

describe("resetStore", () => {
  it("resets all keys to their initial values", () => {
    setState({
      activeUTubID: 42,
      activeUTubName: "Test",
      isCurrentUserOwner: true,
      selectedTagIDs: [1, 2],
      urls: [
        {
          utubUrlID: 1,
          urlString: "http://example.com",
          utubUrlTagIDs: [],
          urlTitle: "Example",
          canDelete: false,
        },
      ],
    });
    resetStore();
    const state = getState();
    expect(state.activeUTubID).toBeNull();
    expect(state.activeUTubName).toBeNull();
    expect(state.isCurrentUserOwner).toBe(false);
    expect(state.selectedTagIDs).toEqual([]);
    expect(state.urls).toEqual([]);
  });
});
