import {
  isBackgroundRefreshActive,
  setBackgroundRefreshActive,
} from "../background-refresh-flag.js";

describe("background-refresh-flag", () => {
  afterEach(() => {
    setBackgroundRefreshActive({ active: false });
  });

  it("defaults to inactive", () => {
    expect(isBackgroundRefreshActive()).toBe(false);
  });

  it("is active after being set active", () => {
    setBackgroundRefreshActive({ active: true });
    expect(isBackgroundRefreshActive()).toBe(true);
  });

  it("is inactive again after being cleared", () => {
    setBackgroundRefreshActive({ active: true });
    setBackgroundRefreshActive({ active: false });
    expect(isBackgroundRefreshActive()).toBe(false);
  });

  it("is cleared by a finally block even when the refresh throws", () => {
    const run = () => {
      setBackgroundRefreshActive({ active: true });
      try {
        throw new Error("boom");
      } finally {
        setBackgroundRefreshActive({ active: false });
      }
    };

    expect(run).toThrow("boom");
    expect(isBackgroundRefreshActive()).toBe(false);
  });
});
