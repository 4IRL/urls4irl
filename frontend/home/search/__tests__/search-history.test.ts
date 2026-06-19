import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CROSS_UTUB_SEARCH_CLOSE_TRIGGER } from "../../../types/metrics-dim-values.js";

import type { MatchedField } from "../../../types/search.js";
import type { SearchHistoryEntry } from "../search-history.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../render.js", () => ({
  renderSearchResults: vi.fn(),
}));

vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ utubs: [{ id: 1 }], activeUTubID: null })),
  setState: vi.fn(),
}));

vi.mock("../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  setMobileUIWhenUTubSelectedOrURLNavSelected: vi.fn(),
  setMobileUIWhenUTubNotSelectedOrUTubDeleted: vi.fn(),
}));

vi.mock("../../utubs/search.js", () => ({
  resetUTubSearch: vi.fn(),
}));

vi.mock("../field-controls.js", () => ({
  initFieldControls: vi.fn(),
  setFieldControls: vi.fn(),
  getSelectedFields: vi.fn(() => ["url", "title", "tag"]),
}));

const STORAGE_KEY = "u4i:crossSearchHistory";
const DEFAULT_FIELDS: MatchedField[] = ["url", "title", "tag"];
const KNOWN_NOW = 1_700_000_000_000;

const $ = window.jQuery;

const SEARCH_MODE_HTML = `
  <button id="toCrossUtubSearch" class="hidden">
    <span id="crossSearchTriggerOpenIcon"></span>
    <span id="crossSearchTriggerCloseIcon" class="hidden"></span>
  </button>
  <button id="navReturnHome" class="hidden"></button>
  <div id="leftPanel" class="panel"></div>
  <div id="crossUtubSearchMode" class="cross-search-hidden">
    <div id="crossUtubSearchInputWrap"><input id="crossUtubSearchInput" type="search" /><button id="crossUtubSearchClear" class="hidden"></button></div>
    <button id="crossUtubSearchSubmit" disabled><span class="crossSearchSubmitIcon"></span><span class="crossSearchRefreshIcon hidden"></span></button>
    <div id="crossUtubSearchFieldControls"></div>
    <span id="crossUtubSearchAnnouncement"></span>
    <div id="crossUtubSearchResults"></div>
    <p id="crossUtubSearchNoResults" class="hidden"></p>
    <p id="crossUtubSearchShortQuery" class="hidden"></p>
  </div>
`;

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

function seedHistory(entries: SearchHistoryEntry[]): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
}

describe("search-history — persistence helpers", () => {
  beforeEach(() => {
    installStorageStub();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("(a) pushSearchHistory persists an entry that getSearchHistory returns", async () => {
    const { pushSearchHistory, getSearchHistory } = await import(
      "../search-history.js"
    );

    expect(getSearchHistory()).toHaveLength(0);

    pushSearchHistory({ query: "alpha", fields: DEFAULT_FIELDS });

    const history = getSearchHistory();
    expect(history).toHaveLength(1);
    expect(history[0].query).toBe("alpha");
    expect(history[0].fields).toEqual(DEFAULT_FIELDS);
    expect(typeof history[0].ts).toBe("number");
  });

  it("(b) re-pushing the same query+fields dedupes (length stays 1, ts refreshed)", async () => {
    const { pushSearchHistory, getSearchHistory } = await import(
      "../search-history.js"
    );
    const nowSpy = vi.spyOn(Date, "now");

    nowSpy.mockReturnValue(1000);
    pushSearchHistory({ query: "alpha", fields: DEFAULT_FIELDS });
    nowSpy.mockReturnValue(5000);
    pushSearchHistory({ query: "alpha", fields: DEFAULT_FIELDS });

    const history = getSearchHistory();
    expect(history).toHaveLength(1);
    expect(history[0].ts).toBe(5000);

    nowSpy.mockRestore();
  });

  it("(b2) re-pushing the same query with different fields dedupes to one entry, keeping the latest fields", async () => {
    const { pushSearchHistory, getSearchHistory } = await import(
      "../search-history.js"
    );
    const nowSpy = vi.spyOn(Date, "now");

    nowSpy.mockReturnValue(1000);
    pushSearchHistory({ query: "alpha", fields: ["title"] });
    // Same query text, different field selection — must refresh the single
    // existing entry rather than add a near-duplicate row.
    nowSpy.mockReturnValue(5000);
    pushSearchHistory({ query: "alpha", fields: ["url"] });

    const history = getSearchHistory();
    expect(history).toHaveLength(1);
    expect(history[0].query).toBe("alpha");
    expect(history[0].ts).toBe(5000);
    expect(history[0].fields).toEqual(["url"]);

    nowSpy.mockRestore();
  });

  it("(b3) a typing chain whose fields change mid-stream still collapses to one entry", async () => {
    const { pushSearchHistory, getSearchHistory } = await import(
      "../search-history.js"
    );
    const nowSpy = vi.spyOn(Date, "now");

    nowSpy.mockReturnValue(1000);
    pushSearchHistory({ query: "reh", fields: ["title"] });
    // Prefix extension within the collapse window but with a different field
    // selection — fields are not part of identity, so it still collapses.
    nowSpy.mockReturnValue(1300);
    pushSearchHistory({ query: "rehre", fields: ["url"] });

    const history = getSearchHistory();
    expect(history).toHaveLength(1);
    expect(history[0].query).toBe("rehre");
    expect(history[0].fields).toEqual(["url"]);

    nowSpy.mockRestore();
  });

  it("(c) pushing 9 distinct entries prunes to the cap of 8", async () => {
    const { pushSearchHistory, getSearchHistory } = await import(
      "../search-history.js"
    );

    for (let index = 0; index < 9; index += 1) {
      pushSearchHistory({ query: `q${index}`, fields: DEFAULT_FIELDS });
    }

    const history = getSearchHistory();
    expect(history).toHaveLength(8);
    expect(history[0].query).toBe("q8");
    expect(history.some((entry) => entry.query === "q0")).toBe(false);
  });

  it("(j) an incremental typing chain collapses into a single entry", async () => {
    const { pushSearchHistory, getSearchHistory } = await import(
      "../search-history.js"
    );
    const nowSpy = vi.spyOn(Date, "now");

    // Each debounced keystroke pushes; the chain must leave only the final query.
    ["reh", "rehr", "rehre", "rehreh"].forEach((query, index) => {
      nowSpy.mockReturnValue(1000 + index * 300);
      pushSearchHistory({ query, fields: DEFAULT_FIELDS });
    });

    const history = getSearchHistory();
    expect(history).toHaveLength(1);
    expect(history[0].query).toBe("rehreh");

    nowSpy.mockRestore();
  });

  it("(k) backspacing collapses, and a non-prefix query starts a new entry", async () => {
    const { pushSearchHistory, getSearchHistory } = await import(
      "../search-history.js"
    );
    const nowSpy = vi.spyOn(Date, "now");

    nowSpy.mockReturnValue(1000);
    pushSearchHistory({ query: "rehreh", fields: DEFAULT_FIELDS });
    nowSpy.mockReturnValue(1300);
    pushSearchHistory({ query: "rehre", fields: DEFAULT_FIELDS });
    // Still one entry (backspacing is a prefix relation).
    expect(getSearchHistory()).toHaveLength(1);
    expect(getSearchHistory()[0].query).toBe("rehre");

    // A fresh, unrelated query appends a second entry.
    nowSpy.mockReturnValue(1600);
    pushSearchHistory({ query: "apple", fields: DEFAULT_FIELDS });
    const history = getSearchHistory();
    expect(history).toHaveLength(2);
    expect(history[0].query).toBe("apple");
    expect(history[1].query).toBe("rehre");

    nowSpy.mockRestore();
  });

  it("(l) a prefix-extension after the collapse window is a separate entry", async () => {
    const { pushSearchHistory, getSearchHistory } = await import(
      "../search-history.js"
    );
    const nowSpy = vi.spyOn(Date, "now");

    nowSpy.mockReturnValue(1000);
    pushSearchHistory({ query: "cat", fields: DEFAULT_FIELDS });
    // Same prefix relation, but ~6 minutes later — a separate search session.
    nowSpy.mockReturnValue(1000 + 6 * 60 * 1000);
    pushSearchHistory({ query: "category", fields: DEFAULT_FIELDS });

    const history = getSearchHistory();
    expect(history).toHaveLength(2);
    expect(history[0].query).toBe("category");
    expect(history[1].query).toBe("cat");

    nowSpy.mockRestore();
  });

  it("(h) pushSearchHistory does not throw when setItem throws QuotaExceededError", async () => {
    const { pushSearchHistory } = await import("../search-history.js");
    vi.stubGlobal("localStorage", {
      getItem: () => null,
      setItem: () => {
        throw new DOMException("quota", "QuotaExceededError");
      },
      removeItem: () => {},
    });

    expect(() =>
      pushSearchHistory({ query: "alpha", fields: DEFAULT_FIELDS }),
    ).not.toThrow();
  });

  it("(i) getSearchHistory returns [] for parse-valid but structurally invalid JSON", async () => {
    const { getSearchHistory } = await import("../search-history.js");

    window.localStorage.setItem(STORAGE_KEY, JSON.stringify("not-an-array"));
    expect(getSearchHistory()).toEqual([]);

    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify([{ ts: "not-a-number" }]),
    );
    expect(getSearchHistory()).toEqual([]);
  });
});

describe("search-history — render + re-run inside the overlay", () => {
  beforeEach(async () => {
    installStorageStub();
    document.body.innerHTML = SEARCH_MODE_HTML;
    // The module keeps search-mode state at module scope; reset it between
    // tests so enterCrossUtubSearchMode() does not early-return as already-open.
    const { exitCrossUtubSearchMode } = await import("../cross-utub-search.js");
    exitCrossUtubSearchMode({
      trigger: CROSS_UTUB_SEARCH_CLOSE_TRIGGER.ESCAPE_KEY,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    document.body.innerHTML = "";
  });

  it("(d) enterCrossUtubSearchMode renders one item per entry with a re-run row and a delete button", async () => {
    const nowSpy = vi.spyOn(Date, "now").mockReturnValue(KNOWN_NOW);
    seedHistory([
      {
        query: "recent",
        fields: ["url"],
        ts: KNOWN_NOW - 60_000,
      },
      {
        query: "older",
        fields: ["title", "tag"],
        ts: KNOWN_NOW - 2 * 24 * 60 * 60 * 1000,
      },
    ]);

    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();

    const historyList = $("#crossUtubSearchHistoryList");
    expect(historyList.length).toBe(1);
    // One item per seeded entry, each with a re-run row and a delete button.
    expect(historyList.find(".crossSearchHistoryItem").length).toBe(2);
    expect(historyList.find(".crossSearchHistoryRow").length).toBe(2);
    expect(historyList.find(".crossSearchHistoryDelete").length).toBe(2);
    expect(historyList.find(".crossSearchHistoryRow").first().text()).toContain(
      "recent",
    );
    // The badges / time / stale markers were removed from each row.
    expect(historyList.find(".crossSearchHistoryStale").length).toBe(0);
    expect(historyList.find(".crossSearchHistoryTime").length).toBe(0);
    expect(historyList.find(".crossSearchHistoryField").length).toBe(0);

    nowSpy.mockRestore();
  });

  it("(d2) clicking a row's delete button removes just that entry; deleting the last removes the list", async () => {
    vi.spyOn(Date, "now").mockReturnValue(KNOWN_NOW);
    seedHistory([
      { query: "first", fields: ["url"], ts: KNOWN_NOW - 1000 },
      { query: "second", fields: ["title"], ts: KNOWN_NOW - 2000 },
    ]);

    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    const { getSearchHistory } = await import("../search-history.js");
    initCrossUtubSearch();
    enterCrossUtubSearchMode();

    expect($(".crossSearchHistoryItem").length).toBe(2);

    // Delete the first row's entry — only "second" survives in storage + DOM.
    $(".crossSearchHistoryItem")
      .first()
      .find(".crossSearchHistoryDelete")
      .trigger("click");

    expect($(".crossSearchHistoryItem").length).toBe(1);
    const afterFirstDelete = getSearchHistory();
    expect(afterFirstDelete).toHaveLength(1);
    expect(afterFirstDelete[0].query).toBe("second");
    expect($("#crossUtubSearchHistoryList").length).toBe(1);

    // Delete the last remaining entry — storage empties and the list is removed.
    $(".crossSearchHistoryItem")
      .first()
      .find(".crossSearchHistoryDelete")
      .trigger("click");

    expect(getSearchHistory()).toHaveLength(0);
    expect($(".crossSearchHistoryItem").length).toBe(0);
    expect($("#crossUtubSearchHistoryList").length).toBe(0);
  });

  it("(e) clicking a history row fills the input and re-runs the saved search", async () => {
    vi.spyOn(Date, "now").mockReturnValue(KNOWN_NOW);
    seedHistory([
      { query: "myquery", fields: ["title"], ts: KNOWN_NOW - 1000 },
    ]);
    const { ajaxCall } = await import("../../../lib/ajax.js");
    (ajaxCall as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      done: vi.fn().mockReturnThis(),
      fail: vi.fn().mockReturnThis(),
    });

    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();

    const { setFieldControls } = await import("../field-controls.js");

    const row = $(".crossSearchHistoryRow").first();
    expect(row.attr("aria-label")).toContain("myquery");
    row.trigger("click");

    expect($("#crossUtubSearchInput").val()).toBe("myquery");
    // The re-run fills the input, so the clear (×) button must reappear.
    expect($("#crossUtubSearchClear").hasClass("hidden")).toBe(false);
    expect(setFieldControls).toHaveBeenCalledWith({ fields: ["title"] });
    expect(ajaxCall).toHaveBeenCalled();
    const calledUrl = (ajaxCall as unknown as ReturnType<typeof vi.fn>).mock
      .calls[0][1] as string;
    expect(calledUrl).toContain("q=myquery");
  });

  it("(f) clicking the clear button clears history and removes the list", async () => {
    vi.spyOn(Date, "now").mockReturnValue(KNOWN_NOW);
    seedHistory([{ query: "alpha", fields: ["url"], ts: KNOWN_NOW - 1000 }]);

    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    const { getSearchHistory } = await import("../search-history.js");
    initCrossUtubSearch();
    enterCrossUtubSearchMode();

    expect($("#crossUtubSearchHistoryList").length).toBe(1);
    $("#crossUtubSearchHistoryClear").trigger("click");

    expect($("#crossUtubSearchHistoryList").length).toBe(0);
    expect(getSearchHistory()).toHaveLength(0);
  });

  it("(g) clearing the input after a search re-renders the history list", async () => {
    vi.useFakeTimers();
    vi.spyOn(Date, "now").mockReturnValue(KNOWN_NOW);
    seedHistory([{ query: "alpha", fields: ["url"], ts: KNOWN_NOW - 1000 }]);
    const { ajaxCall } = await import("../../../lib/ajax.js");
    (ajaxCall as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      done: vi.fn().mockReturnThis(),
      fail: vi.fn().mockReturnThis(),
    });

    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();

    const input = $("#crossUtubSearchInput");
    input.val("zzz").trigger("input");
    vi.advanceTimersByTime(300);

    expect($("#crossUtubSearchHistoryList").length).toBe(0);

    input.val("").trigger("input");
    expect($("#crossUtubSearchHistoryList").length).toBe(1);

    vi.useRealTimers();
  });
});
