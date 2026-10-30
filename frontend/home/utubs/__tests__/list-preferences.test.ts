import { getState, resetStore } from "../../../store/app-store.js";
import {
  applyListPreference,
  clearAllEdits,
  getPrefsVersion,
  hasOutstandingEdit,
  isLatestEdit,
  latestToken,
  markEdit,
  recordSavedPreference,
  reseedListPreferences,
  resetListPreferenceTracking,
  setReseedListener,
  settleEdit,
  syncDeckOrderToStoreSort,
} from "../list-preferences.js";
import { reorderUTubDeck } from "../sort.js";

vi.mock("../sort.js", () => ({ reorderUTubDeck: vi.fn() }));

const { mockLog } = vi.hoisted(() => ({ mockLog: vi.fn() }));
vi.mock("../../../lib/debug.js", () => ({ debug: () => mockLog }));

const $ = window.jQuery;

const SERVER_PREFS = {
  utubSort: "name_az",
  showRowCounts: true,
  showListTotals: false,
};

beforeEach(() => {
  document.body.innerHTML = `<div id="UTubDeck"></div>`;
  resetStore();
  resetListPreferenceTracking();
  setReseedListener(null);
  vi.mocked(reorderUTubDeck).mockClear();
});

describe("applyListPreference / recordSavedPreference", () => {
  it("writes the store and toggles the matching deck class for each field", () => {
    applyListPreference({ field: "showRowCounts", value: true });
    applyListPreference({ field: "showListTotals", value: false });
    applyListPreference({ field: "utubSort", value: "newest_created" });

    expect(getState().preferences.showRowCounts).toBe(true);
    expect(getState().preferences.showListTotals).toBe(false);
    expect(getState().preferences.utubSort).toBe("newest_created");
    expect($("#UTubDeck").hasClass("showUTubRowCounts")).toBe(true);
    expect($("#UTubDeck").hasClass("hideListTotals")).toBe(true);
    expect($("#UTubDeck").attr("class")).not.toContain("newest_created");
    expect(reorderUTubDeck).not.toHaveBeenCalled();

    applyListPreference({ field: "showRowCounts", value: false });
    applyListPreference({ field: "showListTotals", value: true });
    expect($("#UTubDeck").hasClass("showUTubRowCounts")).toBe(false);
    expect($("#UTubDeck").hasClass("hideListTotals")).toBe(false);
  });

  it("recordSavedPreference writes only the store", () => {
    recordSavedPreference({ field: "showRowCounts", value: true });

    expect(getState().preferences.showRowCounts).toBe(true);
    expect($("#UTubDeck").hasClass("showUTubRowCounts")).toBe(false);
  });
});

describe("edit tokens", () => {
  it("a second markEdit makes the first token stale", () => {
    const first = markEdit("utubSort");
    const second = markEdit("utubSort");

    expect(second).toBeGreaterThan(first);
    expect(latestToken("utubSort")).toBe(second);
    expect(isLatestEdit({ field: "utubSort", token: first })).toBe(false);
    expect(isLatestEdit({ field: "utubSort", token: second })).toBe(true);

    settleEdit({ field: "utubSort", token: first });
    expect(hasOutstandingEdit("utubSort")).toBe(true);
    // A superseded settle keeps the mark but still records the committed save.
    expect(getPrefsVersion()).toBe(1);

    settleEdit({ field: "utubSort", token: second });
    expect(hasOutstandingEdit("utubSort")).toBe(false);
    expect(getPrefsVersion()).toBe(2);
  });

  it("clearAllEdits clears every field", () => {
    markEdit("utubSort");
    markEdit("showRowCounts");
    markEdit("showListTotals");

    clearAllEdits();

    expect(hasOutstandingEdit("utubSort")).toBe(false);
    expect(hasOutstandingEdit("showRowCounts")).toBe(false);
    expect(hasOutstandingEdit("showListTotals")).toBe(false);
  });
});

describe("reseedListPreferences", () => {
  it("applies valid values to the store and deck classes and returns the changed fields", () => {
    const changed = reseedListPreferences({
      preferences: SERVER_PREFS,
      capturedVersion: getPrefsVersion(),
    });

    expect(changed).toEqual(["utubSort", "showRowCounts", "showListTotals"]);
    expect(getState().preferences.utubSort).toBe("name_az");
    expect($("#UTubDeck").hasClass("showUTubRowCounts")).toBe(true);
    expect($("#UTubDeck").hasClass("hideListTotals")).toBe(true);
  });

  it("ignores malformed values and a malformed object (fail closed)", () => {
    reseedListPreferences({
      preferences: {
        utubSort: "bogus",
        showRowCounts: "yes",
        showListTotals: 0,
      },
      capturedVersion: 0,
    });
    reseedListPreferences({ preferences: undefined, capturedVersion: 0 });
    reseedListPreferences({ preferences: "nope", capturedVersion: 0 });

    expect(getState().preferences.utubSort).toBe("recent_activity");
    expect(getState().preferences.showRowCounts).toBe(false);
    expect(getState().preferences.showListTotals).toBe(true);
  });

  it("skips a field with an outstanding edit token", () => {
    markEdit("showRowCounts");

    const changed = reseedListPreferences({
      preferences: SERVER_PREFS,
      capturedVersion: 0,
    });

    expect(changed).toEqual(["utubSort", "showListTotals"]);
    expect(getState().preferences.showRowCounts).toBe(false);
    expect($("#UTubDeck").hasClass("showUTubRowCounts")).toBe(false);
  });

  it("skips a field saved after the request was issued but reseeds fields that did not settle", () => {
    const captured = getPrefsVersion();
    const token = markEdit("utubSort");
    settleEdit({ field: "utubSort", token });

    const stale = reseedListPreferences({
      preferences: SERVER_PREFS,
      capturedVersion: captured,
    });
    expect(stale).toEqual(["showRowCounts", "showListTotals"]);
    expect(getState().preferences.utubSort).toBe("recent_activity");

    const fresh = reseedListPreferences({
      preferences: SERVER_PREFS,
      capturedVersion: getPrefsVersion(),
    });
    expect(fresh).toEqual(["utubSort"]);
    expect(getState().preferences.utubSort).toBe("name_az");
  });

  it("calls the listener with the changed fields only when something changed", () => {
    const listener = vi.fn();
    setReseedListener(listener);

    reseedListPreferences({ preferences: SERVER_PREFS, capturedVersion: 0 });
    expect(listener).toHaveBeenCalledWith([
      "utubSort",
      "showRowCounts",
      "showListTotals",
    ]);

    listener.mockClear();
    reseedListPreferences({ preferences: SERVER_PREFS, capturedVersion: 0 });
    expect(listener).not.toHaveBeenCalled();
  });

  it("catches and logs a throwing listener and still returns", () => {
    const boom = new Error("render boom");
    setReseedListener(() => {
      throw boom;
    });
    mockLog.mockClear();

    expect(() =>
      reseedListPreferences({ preferences: SERVER_PREFS, capturedVersion: 0 }),
    ).not.toThrow();
    expect(getState().preferences.showRowCounts).toBe(true);
    expect(mockLog).toHaveBeenCalledWith("reseed listener threw", boom);
  });
});

describe("syncDeckOrderToStoreSort", () => {
  it("reorders to the store sort when it differs from the response's sort", () => {
    recordSavedPreference({ field: "utubSort", value: "oldest_created" });

    syncDeckOrderToStoreSort({ responseSort: "recent_activity" });

    expect(reorderUTubDeck).toHaveBeenCalledWith("oldest_created");
  });

  it("does nothing when the response sort is missing or invalid", () => {
    recordSavedPreference({ field: "utubSort", value: "oldest_created" });

    syncDeckOrderToStoreSort({ responseSort: undefined });
    syncDeckOrderToStoreSort({ responseSort: "bogus" });

    expect(reorderUTubDeck).not.toHaveBeenCalled();
  });

  it("does nothing when the sorts match", () => {
    syncDeckOrderToStoreSort({ responseSort: "recent_activity" });

    expect(reorderUTubDeck).not.toHaveBeenCalled();
  });
});
