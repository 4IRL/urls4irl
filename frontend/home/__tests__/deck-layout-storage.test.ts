import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const STORAGE_KEY = "u4i:deckLayout";

// Map-backed localStorage stub, copied from `nudge-storage.test.ts` so the
// persistence helpers exercise real read/write behavior against an in-memory
// store rather than the ambient (undefined-in-happy-dom) localStorage.
function installStorageStub(): void {
  const data = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (key: string): string | null => data.get(key) ?? null,
    setItem: (key: string, value: string): void => {
      data.set(key, String(value));
    },
    removeItem: (key: string): void => {
      data.delete(key);
    },
    clear: (): void => {
      data.clear();
    },
    key: (index: number): string | null =>
      Array.from(data.keys())[index] ?? null,
    get length(): number {
      return data.size;
    },
  });
}

describe("deck-layout-storage — Member/Tag deck collapse persistence", () => {
  beforeEach(() => {
    installStorageStub();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("(a) getDeckLayout returns both decks expanded when the key is absent", async () => {
    const { getDeckLayout } = await import("../deck-layout-storage.js");

    expect(getDeckLayout()).toEqual({
      membersMinimized: false,
      tagsMinimized: false,
    });
  });

  it("(b) setDeckMinimizedPreference round-trips the Members field, preserving Tags", async () => {
    const { getDeckLayout, setDeckMinimizedPreference, PERSISTABLE_DECK } =
      await import("../deck-layout-storage.js");

    setDeckMinimizedPreference({
      deck: PERSISTABLE_DECK.MEMBERS,
      minimized: true,
    });
    expect(getDeckLayout()).toEqual({
      membersMinimized: true,
      tagsMinimized: false,
    });

    // A second write must merge rather than clobber the first field.
    setDeckMinimizedPreference({
      deck: PERSISTABLE_DECK.TAGS,
      minimized: true,
    });
    expect(getDeckLayout()).toEqual({
      membersMinimized: true,
      tagsMinimized: true,
    });

    // Expanding one deck must not expand the other.
    setDeckMinimizedPreference({
      deck: PERSISTABLE_DECK.MEMBERS,
      minimized: false,
    });
    expect(getDeckLayout()).toEqual({
      membersMinimized: false,
      tagsMinimized: true,
    });
  });

  it("(b2) setDeckMinimizedPreference round-trips the Tags field on its own", async () => {
    const { getDeckLayout, setDeckMinimizedPreference, PERSISTABLE_DECK } =
      await import("../deck-layout-storage.js");

    setDeckMinimizedPreference({
      deck: PERSISTABLE_DECK.TAGS,
      minimized: true,
    });
    expect(getDeckLayout()).toEqual({
      membersMinimized: false,
      tagsMinimized: true,
    });

    setDeckMinimizedPreference({
      deck: PERSISTABLE_DECK.TAGS,
      minimized: false,
    });
    expect(getDeckLayout()).toEqual({
      membersMinimized: false,
      tagsMinimized: false,
    });
  });

  it("(c) getDeckLayout returns the default (and does not throw) for malformed JSON", async () => {
    const { getDeckLayout } = await import("../deck-layout-storage.js");

    window.localStorage.setItem(STORAGE_KEY, "{not-valid-json");

    expect(() => getDeckLayout()).not.toThrow();
    expect(getDeckLayout()).toEqual({
      membersMinimized: false,
      tagsMinimized: false,
    });
  });

  it("(d) getDeckLayout returns the default for parse-valid but structurally invalid values", async () => {
    const { getDeckLayout } = await import("../deck-layout-storage.js");
    const DEFAULT_LAYOUT = { membersMinimized: false, tagsMinimized: false };

    // An array is valid JSON but not the expected object shape.
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(["x"]));
    expect(getDeckLayout()).toEqual(DEFAULT_LAYOUT);

    // A bare JSON string is valid JSON but not an object.
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify("x"));
    expect(getDeckLayout()).toEqual(DEFAULT_LAYOUT);

    // `null` parses successfully but must not be indexed.
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(null));
    expect(getDeckLayout()).toEqual(DEFAULT_LAYOUT);
  });

  it("(e) getDeckLayout defaults a non-boolean field to expanded, keeping valid siblings", async () => {
    const { getDeckLayout } = await import("../deck-layout-storage.js");

    // A corrupt field must never leave a deck stuck shut.
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ membersMinimized: "yes", tagsMinimized: true }),
    );
    expect(getDeckLayout()).toEqual({
      membersMinimized: false,
      tagsMinimized: true,
    });

    // A missing field falls back to expanded too.
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ membersMinimized: true }),
    );
    expect(getDeckLayout()).toEqual({
      membersMinimized: true,
      tagsMinimized: false,
    });
  });

  it("(f) setDeckMinimizedPreference does not throw when setItem throws QuotaExceededError", async () => {
    const { setDeckMinimizedPreference, PERSISTABLE_DECK } =
      await import("../deck-layout-storage.js");
    const throwingSetItem = vi.fn(() => {
      throw new DOMException("quota", "QuotaExceededError");
    });
    vi.stubGlobal("localStorage", {
      getItem: () => null,
      setItem: throwingSetItem,
      removeItem: () => {},
    });

    expect(() =>
      setDeckMinimizedPreference({
        deck: PERSISTABLE_DECK.MEMBERS,
        minimized: true,
      }),
    ).not.toThrow();
    // Proves the throwing stub was actually consulted, so the swallow is real
    // rather than the assertion passing because no write was attempted.
    expect(throwingSetItem).toHaveBeenCalledTimes(1);
  });

  it("(g) getDeckLayout returns the default when getItem itself throws", async () => {
    const { getDeckLayout } = await import("../deck-layout-storage.js");
    const throwingGetItem = vi.fn(() => {
      throw new DOMException("denied", "SecurityError");
    });
    vi.stubGlobal("localStorage", {
      getItem: throwingGetItem,
      setItem: () => {},
      removeItem: () => {},
    });

    expect(() => getDeckLayout()).not.toThrow();
    expect(getDeckLayout()).toEqual({
      membersMinimized: false,
      tagsMinimized: false,
    });
    // Both calls above must have hit the throwing stub — otherwise the default
    // return proves nothing about the catch branch.
    expect(throwingGetItem).toHaveBeenCalledTimes(2);
  });

  it("(h) _resetDeckLayoutStorageForTests clears the persisted layout", async () => {
    const {
      getDeckLayout,
      setDeckMinimizedPreference,
      _resetDeckLayoutStorageForTests,
      PERSISTABLE_DECK,
    } = await import("../deck-layout-storage.js");

    setDeckMinimizedPreference({
      deck: PERSISTABLE_DECK.TAGS,
      minimized: true,
    });
    expect(getDeckLayout().tagsMinimized).toBe(true);

    _resetDeckLayoutStorageForTests();
    expect(getDeckLayout()).toEqual({
      membersMinimized: false,
      tagsMinimized: false,
    });
  });
});
