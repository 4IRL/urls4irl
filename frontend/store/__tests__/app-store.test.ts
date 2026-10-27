import {
  getState,
  setState,
  resetStore,
  subscribe,
  type StoreListener,
} from "../app-store.js";
import {
  EMPTY_MEMBER_SETTINGS,
  EMPTY_UTUB_SETTINGS,
} from "../../types/settings.js";

const { mockLog } = vi.hoisted(() => ({ mockLog: vi.fn() }));
vi.mock("../../lib/debug.js", () => ({ debug: () => mockLog }));

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
    expect(state.multiSelectMode).toBe(false);
    expect(state.selectedURLCardIDs).toEqual([]);
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

describe("settings slice defaults", () => {
  it("starts with null settings and settingsVersion 0, restored by resetStore", () => {
    expect(getState().settings).toBeNull();
    expect(getState().settingsVersion).toBe(0);

    setState({ settings: EMPTY_UTUB_SETTINGS, settingsVersion: 4 });
    resetStore();

    expect(getState().settings).toBeNull();
    expect(getState().settingsVersion).toBe(0);
  });
});

describe("memberSettings slice", () => {
  const MEMBER = {
    urls: { ...EMPTY_MEMBER_SETTINGS.urls, hide_copy_button: true },
  };

  it("starts null with version 0, restored by resetStore", () => {
    expect(getState().memberSettings).toBeNull();
    expect(getState().memberSettingsVersion).toBe(0);

    setState({ memberSettings: MEMBER, memberSettingsVersion: 3 });
    resetStore();

    expect(getState().memberSettings).toBeNull();
    expect(getState().memberSettingsVersion).toBe(0);
  });

  it("is nulled when the active UTub changes without a replacement", () => {
    setState({ activeUTubID: 1, memberSettings: MEMBER });
    const listener = vi.fn();
    const dispose = subscribe(listener);

    setState({ activeUTubID: 2 });
    dispose();

    expect(getState().memberSettings).toBeNull();
    expect(listener).toHaveBeenCalledWith(
      expect.arrayContaining(["activeUTubID", "memberSettings"]),
    );
  });

  it("keeps a replacement supplied in the same setState as the UTub change", () => {
    setState({ activeUTubID: 1, memberSettings: MEMBER });
    const next = {
      urls: { ...EMPTY_MEMBER_SETTINGS.urls, sort: "oldest" as const },
    };

    setState({ activeUTubID: 2, memberSettings: next });

    expect(getState().memberSettings).toBe(next);
  });

  it("is untouched when the same UTub id is set again", () => {
    setState({ activeUTubID: 1, memberSettings: MEMBER });
    setState({ activeUTubID: 1 });
    expect(getState().memberSettings).toBe(MEMBER);
  });
});

describe("subscribe", () => {
  const disposers: Array<() => void> = [];

  function track(listener: StoreListener): () => void {
    const dispose = subscribe(listener);
    disposers.push(dispose);
    return dispose;
  }

  afterEach(() => {
    disposers.splice(0).forEach((dispose) => dispose());
  });

  it("notifies only the keys whose value changed by reference", () => {
    const listener = vi.fn();
    track(listener);
    setState({ activeUTubName: "A" });
    setState({ activeUTubName: "A", isCoCreator: true });

    expect(listener).toHaveBeenNthCalledWith(1, ["activeUTubName"]);
    expect(listener).toHaveBeenNthCalledWith(2, ["isCoCreator"]);
  });

  it("does not notify when nothing changed", () => {
    const listener = vi.fn();
    track(listener);
    setState({ activeUTubName: null });
    setState({});

    expect(listener).not.toHaveBeenCalled();
  });

  it("stops notifying after dispose", () => {
    const listener = vi.fn();
    const dispose = track(listener);
    dispose();
    setState({ isCoCreator: true });

    expect(listener).not.toHaveBeenCalled();
  });

  it("a throwing listener neither aborts setState nor later listeners, and is logged", () => {
    const later = vi.fn();
    track(() => {
      throw new Error("boom");
    });
    track(later);

    expect(() => setState({ isCoCreator: true })).not.toThrow();

    expect(getState().isCoCreator).toBe(true);
    expect(later).toHaveBeenCalledWith(["isCoCreator"]);
    expect(mockLog).toHaveBeenCalledWith(
      "store listener threw",
      expect.any(Error),
    );
  });

  it("delivers a nested setState's notification after the outer one completes", () => {
    const order: string[] = [];
    track((keys) => {
      order.push(`first:${keys.join(",")}`);
      if (keys.includes("activeUTubName")) {
        setState({ isCoCreator: true });
        order.push("first-after-nested-setState");
      }
    });
    track((keys) => {
      order.push(`second:${keys.join(",")}`);
    });

    setState({ activeUTubName: "A" });

    expect(getState().isCoCreator).toBe(true);
    expect(order).toEqual([
      "first:activeUTubName",
      "first-after-nested-setState",
      "second:activeUTubName",
      "first:isCoCreator",
      "second:isCoCreator",
    ]);
  });
});

describe("no-UTub settings invariant", () => {
  const populated = { ...EMPTY_UTUB_SETTINGS, utubs: { sample: 1 } } as never;

  it.each([
    ["null (removal / openTrash / leave)", null],
    ["a different id (switch)", 9],
  ])(
    "nulls settings and notifies it when activeUTubID becomes %s",
    (_n, id) => {
      setState({ activeUTubID: 1, settings: populated });
      const listener = vi.fn();
      const dispose = subscribe(listener);

      setState({ activeUTubID: id });

      expect(getState().settings).toBeNull();
      expect(listener).toHaveBeenCalledWith(["activeUTubID", "settings"]);
      dispose();
    },
  );

  it("does not notify settings when they were already null", () => {
    setState({ activeUTubID: 1 });
    const listener = vi.fn();
    const dispose = subscribe(listener);

    setState({ activeUTubID: null });

    expect(listener).toHaveBeenCalledWith(["activeUTubID"]);
    dispose();
  });

  it("leaves settings alone for a same-id setState", () => {
    setState({ activeUTubID: 1, settings: populated });

    setState({ activeUTubID: 1, activeUTubName: "x" });

    expect(getState().settings).toBe(populated);
  });

  it("keeps settings the caller passes in the same setState", () => {
    setState({ activeUTubID: 1, settings: EMPTY_UTUB_SETTINGS });

    setState({ activeUTubID: 2, settings: populated });

    expect(getState().settings).toBe(populated);
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
          shortLinkExpiresAt: null,
          canRevokeShortLink: false,
          addedAt: "2024-01-01T00:00:00+00:00",
          addedByUserID: 1,
        },
        {
          utubUrlID: 2,
          urlString: "http://b.com",
          urlTitle: "B",
          utubUrlTagIDs: [],
          canDelete: false,
          shortLinkExpiresAt: null,
          canRevokeShortLink: false,
          addedAt: "2024-01-02T00:00:00+00:00",
          addedByUserID: 1,
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
      multiSelectMode: true,
      selectedURLCardIDs: [1, 2],
      urls: [
        {
          utubUrlID: 1,
          urlString: "http://example.com",
          utubUrlTagIDs: [],
          urlTitle: "Example",
          canDelete: false,
          shortLinkExpiresAt: null,
          canRevokeShortLink: false,
          addedAt: "2024-01-01T00:00:00+00:00",
          addedByUserID: 1,
        },
      ],
    });
    resetStore();
    const state = getState();
    expect(state.activeUTubID).toBeNull();
    expect(state.activeUTubName).toBeNull();
    expect(state.isCurrentUserOwner).toBe(false);
    expect(state.selectedTagIDs).toEqual([]);
    expect(state.multiSelectMode).toBe(false);
    expect(state.selectedURLCardIDs).toEqual([]);
    expect(state.urls).toEqual([]);
  });
});
