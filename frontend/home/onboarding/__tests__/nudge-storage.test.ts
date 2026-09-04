import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const STORAGE_KEY = "u4i:onboardingSeen";

// Map-backed localStorage stub, copied from `search-history.test.ts` so the
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

describe("nudge-storage — seen-once persistence helpers", () => {
  beforeEach(() => {
    installStorageStub();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("(a) hasSeenTip returns false for a tip that has never been seen", async () => {
    const { hasSeenTip } = await import("../nudge-storage.js");

    expect(hasSeenTip("createUtub")).toBe(false);
  });

  it("(b) markTipSeen persists a tip so hasSeenTip returns true, preserving other tips", async () => {
    const { hasSeenTip, markTipSeen } = await import("../nudge-storage.js");

    markTipSeen("createUtub");
    expect(hasSeenTip("createUtub")).toBe(true);

    // Marking a second tip must not clobber the first.
    markTipSeen("addUrl");
    expect(hasSeenTip("addUrl")).toBe(true);
    expect(hasSeenTip("createUtub")).toBe(true);
  });

  it("(c) hasSeenTip returns false (and does not throw) when the stored value is malformed JSON", async () => {
    const { hasSeenTip } = await import("../nudge-storage.js");

    window.localStorage.setItem(STORAGE_KEY, "{not-valid-json");

    expect(() => hasSeenTip("createUtub")).not.toThrow();
    expect(hasSeenTip("createUtub")).toBe(false);
  });

  it("(c2) hasSeenTip returns false for parse-valid but structurally invalid values", async () => {
    const { hasSeenTip } = await import("../nudge-storage.js");

    // An array is valid JSON but not the expected object shape.
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(["createUtub"]));
    expect(hasSeenTip("createUtub")).toBe(false);

    // A bare JSON string is valid JSON but not an object.
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify("createUtub"));
    expect(hasSeenTip("createUtub")).toBe(false);

    // `null` parses successfully but must not be indexed.
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(null));
    expect(hasSeenTip("createUtub")).toBe(false);
  });

  it("(d) markTipSeen does not throw when setItem throws QuotaExceededError", async () => {
    const { markTipSeen } = await import("../nudge-storage.js");
    vi.stubGlobal("localStorage", {
      getItem: () => null,
      setItem: () => {
        throw new DOMException("quota", "QuotaExceededError");
      },
      removeItem: () => {},
    });

    expect(() => markTipSeen("createUtub")).not.toThrow();
  });

  it("(e) _resetOnboardingStorageForTests clears persisted seen state", async () => {
    const { hasSeenTip, markTipSeen, _resetOnboardingStorageForTests } =
      await import("../nudge-storage.js");

    markTipSeen("createUtub");
    expect(hasSeenTip("createUtub")).toBe(true);

    _resetOnboardingStorageForTests();
    expect(hasSeenTip("createUtub")).toBe(false);
  });
});
