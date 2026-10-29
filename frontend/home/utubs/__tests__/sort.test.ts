import parityFixture from "../../../../tests/fixtures/utub_sort_parity.json";

import type { UtubSortValue } from "../../../types/preferences.js";
import type { UtubSummaryItem } from "../../../types/utub.js";

import { getState, resetStore, setState } from "../../../store/app-store.js";
import { makeUtubSummaryItem } from "../../../__tests__/helpers/utub-summary.js";
import {
  compareUTubs,
  insertNewUTubRow,
  markUTubOpened,
  reorderAfterRename,
  reorderUTubDeck,
  scrollActiveUTubIntoViewIfHidden,
  scrollUTubRowIntoView,
  syncRowNameAndOrder,
} from "../sort.js";
import { createUTubSelector } from "../selectors.js";

const $ = window.jQuery;

const ALL_SORTS: UtubSortValue[] = [
  "recent_activity",
  "last_opened",
  "name_az",
  "newest_created",
  "oldest_created",
];

type ParityFixture = {
  inputs: Pick<
    UtubSummaryItem,
    "id" | "name" | "createdAt" | "lastUpdated" | "lastOpenedAt"
  >[];
  expected: Record<UtubSortValue, number[]>;
};

function setSort(sort: UtubSortValue): void {
  setState({ preferences: { ...getState().preferences, utubSort: sort } });
}

function rowHTML(utub: UtubSummaryItem, position: number): string {
  return `<span class="UTubSelector" utubid="${utub.id}" position="${position}" tabindex="0"><b class="UTubName">${utub.name}</b></span>`;
}

function seedDeck(utubs: UtubSummaryItem[]): void {
  document.body.innerHTML = `<div id="listUTubs">${utubs
    .map((utub, index) => rowHTML(utub, index))
    .join("")}</div>`;
  setState({ utubs });
}

function domOrder(): number[] {
  return $("#listUTubs > .UTubSelector")
    .map((_, element) => Number($(element).attr("utubid")))
    .get();
}

function storeOrder(): number[] {
  return getState().utubs.map((utub) => utub.id);
}

const scrollIntoView = vi.fn();
let focusSpy: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  resetStore();
  scrollIntoView.mockClear();
  Element.prototype.scrollIntoView = scrollIntoView;
  focusSpy = vi.spyOn(HTMLElement.prototype, "focus");
});

afterEach(() => {
  focusSpy.mockRestore();
});

describe("compareUTubs against the shared parity fixture", () => {
  const fixture = parityFixture as unknown as ParityFixture;
  const items = fixture.inputs.map((input) => makeUtubSummaryItem(input));

  it.each(ALL_SORTS)("orders every input as the server does for %s", (sort) => {
    const sorted = [...items].sort((left, right) =>
      compareUTubs({ left, right, sort }),
    );
    expect(sorted.map((item) => item.id)).toEqual(fixture.expected[sort]);
  });

  it("casefolds names like the server (ss/ß tie by id)", () => {
    const strasse = items.find((item) => item.name === "Strasse")!;
    const sharpS = items.find((item) => item.name === "Straße")!;
    expect(
      compareUTubs({ left: strasse, right: sharpS, sort: "name_az" }),
    ).toBeLessThan(0);
    expect(
      compareUTubs({ left: sharpS, right: strasse, sort: "name_az" }),
    ).toBeGreaterThan(0);
  });

  it("folds a final sigma like casefold (no context-dependent lowercasing)", () => {
    const final = items.find((item) => item.id === 17);
    const alpha = items.find((item) => item.id === 18);
    if (final === undefined || alpha === undefined) throw new Error("fixture");
    // casefold: "ΟΔΟΣ" -> "οδοσ" sorts after "ΟΔΟΑ" -> "οδοα".
    expect(
      compareUTubs({ left: final, right: alpha, sort: "name_az" }),
    ).toBeGreaterThan(0);
    const lowerFinal = makeUtubSummaryItem({ id: 30, name: "οδος" });
    const upperFinal = makeUtubSummaryItem({ id: 31, name: "ΟΔΟΣ" });
    expect(
      compareUTubs({ left: lowerFinal, right: upperFinal, sort: "name_az" }),
    ).toBeLessThan(0);
  });

  it("orders astral characters by code point, not UTF-16 unit", () => {
    const astral = makeUtubSummaryItem({ id: 1, name: "\u{1F600}" });
    const fullWidth = makeUtubSummaryItem({ id: 2, name: "ａ" });
    expect(
      compareUTubs({ left: astral, right: fullWidth, sort: "name_az" }),
    ).toBeGreaterThan(0);
  });
});

describe("reorderUTubDeck", () => {
  const first = makeUtubSummaryItem({ id: 1, name: "Charlie" });
  const second = makeUtubSummaryItem({ id: 2, name: "alpha" });
  const third = makeUtubSummaryItem({ id: 3, name: "Bravo" });

  it("reorders store and DOM, keeps .active and .hidden, and restripes", () => {
    seedDeck([first, second, third]);
    $(".UTubSelector[utubid=1]").addClass("active");
    $(".UTubSelector[utubid=3]").addClass("hidden");

    reorderUTubDeck("name_az");

    expect(storeOrder()).toEqual([2, 3, 1]);
    expect(domOrder()).toEqual([2, 3, 1]);
    expect($(".UTubSelector[utubid=1]").hasClass("active")).toBe(true);
    expect($(".UTubSelector[utubid=3]").hasClass("hidden")).toBe(true);
    expect($(".UTubSelector[utubid=2]").hasClass("even")).toBe(true);
    expect($(".UTubSelector[utubid=1]").hasClass("odd")).toBe(true);
    expect($(".UTubSelector[utubid=2]").attr("position")).toBe("0");
    expect($(".UTubSelector[utubid=1]").attr("position")).toBe("2");
  });

  it("re-focuses a focused moved row with preventScroll, and only that row", () => {
    seedDeck([first, second, third]);
    const row = $(".UTubSelector[utubid=1]")[0];
    row.focus();
    focusSpy.mockClear();

    reorderUTubDeck("name_az");

    expect(document.activeElement).toBe(row);
    expect(focusSpy).toHaveBeenCalledTimes(1);
    expect(focusSpy).toHaveBeenCalledWith({ preventScroll: true });
  });

  it("does not focus a row that was not focused", () => {
    seedDeck([first, second, third]);

    reorderUTubDeck("name_az");

    expect(focusSpy).not.toHaveBeenCalled();
  });

  it("keeps the selection indicator class on the active row", () => {
    seedDeck([first, second, third]);
    $(".UTubSelector[utubid=2]").addClass("active");

    reorderUTubDeck("oldest_created");

    expect($("#listUTubs > .UTubSelector.active").attr("utubid")).toBe("2");
  });
});

describe("insertNewUTubRow", () => {
  // Stored server timestamps are hours AHEAD of the new item's client time.
  const future = "2030-01-01T12:00:00.000Z";
  const existing = [
    makeUtubSummaryItem({
      id: 1,
      name: "bravo",
      createdAt: future,
      lastUpdated: future,
      lastOpenedAt: future,
    }),
    makeUtubSummaryItem({
      id: 2,
      name: "delta",
      createdAt: future,
      lastUpdated: future,
      lastOpenedAt: future,
    }),
  ];

  function newRow(utub: UtubSummaryItem): JQuery<HTMLElement> {
    return createUTubSelector({
      utubName: utub.name,
      utubID: utub.id,
      memberRole: "creator",
      isLocked: false,
      index: 0,
      urlCount: 0,
      memberCount: 1,
    });
  }

  function created(name: string): UtubSummaryItem {
    const behind = "2029-12-31T00:00:00.000Z";
    return makeUtubSummaryItem({
      id: 9,
      name,
      createdAt: behind,
      lastUpdated: behind,
      lastOpenedAt: behind,
    });
  }

  it.each(["recent_activity", "last_opened", "newest_created"] as const)(
    "inserts first under %s even when the client clock is behind",
    (sort) => {
      seedDeck(existing);
      const utub = created("zulu");
      insertNewUTubRow({ utub, row: newRow(utub), sort });
      expect(storeOrder()).toEqual([9, 1, 2]);
      expect(domOrder()).toEqual([9, 1, 2]);
      expect($("#listUTubs > .UTubSelector").eq(0).attr("position")).toBe("0");
      expect($("#listUTubs > .UTubSelector").eq(2).attr("position")).toBe("2");
    },
  );

  it("inserts last under oldest_created even when the client clock is ahead", () => {
    seedDeck(existing);
    const utub = created("zulu");
    insertNewUTubRow({ utub, row: newRow(utub), sort: "oldest_created" });
    expect(storeOrder()).toEqual([1, 2, 9]);
    expect(domOrder()).toEqual([1, 2, 9]);
  });

  it("inserts mid-list under name_az", () => {
    seedDeck(existing);
    const utub = created("charlie");
    insertNewUTubRow({ utub, row: newRow(utub), sort: "name_az" });
    expect(storeOrder()).toEqual([1, 9, 2]);
    expect(domOrder()).toEqual([1, 9, 2]);
  });

  it("appends under name_az when it sorts last and restripes", () => {
    seedDeck(existing);
    const utub = created("zulu");
    insertNewUTubRow({ utub, row: newRow(utub), sort: "name_az" });
    expect(domOrder()).toEqual([1, 2, 9]);
    expect($(".UTubSelector[utubid=9]").hasClass("even")).toBe(true);
  });
});

describe("scrollUTubRowIntoView", () => {
  it("scrolls a visible row with block nearest and never focuses", () => {
    seedDeck([makeUtubSummaryItem({ id: 1 })]);
    scrollUTubRowIntoView({ utubID: 1 });
    expect(scrollIntoView).toHaveBeenCalledWith({
      block: "nearest",
      behavior: "instant",
    });
    expect(focusSpy).not.toHaveBeenCalled();
  });

  it("does nothing for a row hidden by the name filter", () => {
    seedDeck([makeUtubSummaryItem({ id: 1 })]);
    $(".UTubSelector").addClass("hidden");
    scrollUTubRowIntoView({ utubID: 1 });
    expect(scrollIntoView).not.toHaveBeenCalled();
  });
});

describe("scrollActiveUTubIntoViewIfHidden", () => {
  function mockRects({
    rowTop,
    rowBottom,
  }: {
    rowTop: number;
    rowBottom: number;
  }): void {
    const rect = (top: number, bottom: number): DOMRect =>
      ({ top, bottom, left: 0, right: 0, width: 0, height: 0 }) as DOMRect;
    $("#listUTubs")[0].getBoundingClientRect = () => rect(0, 100);
    $(".UTubSelector.active")[0].getBoundingClientRect = () =>
      rect(rowTop, rowBottom);
  }

  it("scrolls when the active row is outside the viewport", () => {
    seedDeck([makeUtubSummaryItem({ id: 1 })]);
    $(".UTubSelector").addClass("active");
    mockRects({ rowTop: 150, rowBottom: 180 });

    scrollActiveUTubIntoViewIfHidden();

    expect(scrollIntoView).toHaveBeenCalledWith({
      block: "nearest",
      behavior: "instant",
    });
    expect(focusSpy).not.toHaveBeenCalled();
  });

  it("does nothing when the active row is visible", () => {
    seedDeck([makeUtubSummaryItem({ id: 1 })]);
    $(".UTubSelector").addClass("active");
    mockRects({ rowTop: 10, rowBottom: 40 });

    scrollActiveUTubIntoViewIfHidden();

    expect(scrollIntoView).not.toHaveBeenCalled();
  });

  it("does nothing when no row is active", () => {
    seedDeck([makeUtubSummaryItem({ id: 1 })]);
    scrollActiveUTubIntoViewIfHidden();
    expect(scrollIntoView).not.toHaveBeenCalled();
  });
});

describe("reorderAfterRename", () => {
  function renameInStore({ id, name }: { id: number; name: string }): void {
    setState({
      utubs: getState().utubs.map((utub) =>
        utub.id === id ? { ...utub, name } : utub,
      ),
    });
    $(`.UTubSelector[utubid=${id}] .UTubName`).text(name);
  }

  const items = [
    makeUtubSummaryItem({ id: 1, name: "alpha" }),
    makeUtubSummaryItem({ id: 2, name: "bravo" }),
    makeUtubSummaryItem({ id: 3, name: "charlie" }),
  ];

  it("moves the row under name_az, scrolls it, and keeps focus only if it had it", () => {
    seedDeck(items);
    setSort("name_az");
    renameInStore({ id: 1, name: "zulu" });
    const row = $(".UTubSelector[utubid=1]")[0];
    row.focus();
    focusSpy.mockClear();

    reorderAfterRename({ utubID: 1 });

    expect(domOrder()).toEqual([2, 3, 1]);
    expect(scrollIntoView).toHaveBeenCalledTimes(1);
    expect(scrollIntoView).toHaveBeenCalledWith({
      block: "nearest",
      behavior: "instant",
    });
    expect(focusSpy).toHaveBeenCalledTimes(1);
    expect(focusSpy).toHaveBeenCalledWith({ preventScroll: true });
    expect(document.activeElement).toBe(row);
  });

  it("does not focus a moved row that was not focused", () => {
    seedDeck(items);
    setSort("name_az");
    renameInStore({ id: 1, name: "zulu" });

    reorderAfterRename({ utubID: 1 });

    expect(domOrder()).toEqual([2, 3, 1]);
    expect(focusSpy).not.toHaveBeenCalled();
  });

  it("does not scroll when the rename leaves the row in place", () => {
    seedDeck(items);
    setSort("name_az");
    renameInStore({ id: 2, name: "bravo two" });

    reorderAfterRename({ utubID: 2 });

    expect(domOrder()).toEqual([1, 2, 3]);
    expect(scrollIntoView).not.toHaveBeenCalled();
  });

  it.each([
    "recent_activity",
    "last_opened",
    "newest_created",
    "oldest_created",
  ] as const)("does not move the row under %s", (sort) => {
    seedDeck(items);
    setSort(sort);
    renameInStore({ id: 1, name: "zulu" });

    reorderAfterRename({ utubID: 1 });

    expect(domOrder()).toEqual([1, 2, 3]);
    expect(storeOrder()).toEqual([1, 2, 3]);
    expect(scrollIntoView).not.toHaveBeenCalled();
  });
});

describe("syncRowNameAndOrder (stale-data name sync)", () => {
  const items = [
    makeUtubSummaryItem({ id: 1, name: "alpha" }),
    makeUtubSummaryItem({ id: 2, name: "bravo" }),
  ];

  function renameInStore({ id, name }: { id: number; name: string }): void {
    setState({
      utubs: getState().utubs.map((utub) =>
        utub.id === id ? { ...utub, name } : utub,
      ),
    });
  }

  it("updates the text then reorders under name_az, without scrolling", () => {
    seedDeck(items);
    setSort("name_az");
    renameInStore({ id: 1, name: "zulu" });

    syncRowNameAndOrder({ utubID: 1, utubName: "zulu" });

    expect($(".UTubSelector[utubid=1] .UTubName").text()).toBe("zulu");
    expect(domOrder()).toEqual([2, 1]);
    expect(scrollIntoView).not.toHaveBeenCalled();
  });

  it("keeps focus on a focused moved row", () => {
    seedDeck(items);
    setSort("name_az");
    renameInStore({ id: 1, name: "zulu" });
    const row = $(".UTubSelector[utubid=1]")[0];
    row.focus();

    syncRowNameAndOrder({ utubID: 1, utubName: "zulu" });

    expect(document.activeElement).toBe(row);
  });

  it("only updates the text under other sorts", () => {
    seedDeck(items);
    setSort("recent_activity");
    renameInStore({ id: 1, name: "zulu" });

    syncRowNameAndOrder({ utubID: 1, utubName: "zulu" });

    expect($(".UTubSelector[utubid=1] .UTubName").text()).toBe("zulu");
    expect(domOrder()).toEqual([1, 2]);
  });
});

describe("markUTubOpened", () => {
  it("stamps lastOpenedAt on the store without reordering the deck", () => {
    const first = makeUtubSummaryItem({ id: 1, name: "one" });
    const second = makeUtubSummaryItem({ id: 2, name: "two" });
    seedDeck([first, second]);

    markUTubOpened({ utubID: 2 });

    const [storedFirst, storedSecond] = getState().utubs;
    expect(storedFirst.lastOpenedAt).toBeNull();
    expect(storedSecond.lastOpenedAt).not.toBeNull();
    expect(storeOrder()).toEqual([1, 2]);
    expect(domOrder()).toEqual([1, 2]);

    reorderUTubDeck("last_opened");
    expect(storeOrder()).toEqual([2, 1]);
  });

  it("leaves the store untouched for an unknown UTub", () => {
    seedDeck([makeUtubSummaryItem({ id: 1, name: "one" })]);
    markUTubOpened({ utubID: 99 });
    expect(getState().utubs[0].lastOpenedAt).toBeNull();
  });
});
