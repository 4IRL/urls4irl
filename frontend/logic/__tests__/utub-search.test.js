import { filterUTubsByName } from "../utub-search.js";

describe("filterUTubsByName", () => {
  const utubs = [
    { id: 1, name: "Work Links" },
    { id: 2, name: "Personal" },
    { id: 3, name: "Work Projects" },
    { id: 4, name: "Shopping" },
  ];

  it("returns empty array when search term matches all names", () => {
    // Empty string is a substring of everything -- nothing is hidden
    expect(filterUTubsByName(utubs, "")).toEqual([]);
  });

  it("returns IDs of UTubs that do NOT contain the search term", () => {
    const hidden = filterUTubsByName(utubs, "work");
    expect(hidden).toEqual([2, 4]);
  });

  it("is case-insensitive (caller lowercases term; function lowercases name)", () => {
    const hidden = filterUTubsByName(utubs, "personal");
    expect(hidden).not.toContain(2);
  });

  it("returns all IDs when no name matches the search term", () => {
    const hidden = filterUTubsByName(utubs, "zzznomatch");
    expect(hidden).toEqual([1, 2, 3, 4]);
  });

  it("returns empty array for empty UTub list", () => {
    expect(filterUTubsByName([], "work")).toEqual([]);
  });

  it("matches partial substrings", () => {
    const hidden = filterUTubsByName(utubs, "shop");
    expect(hidden).not.toContain(4);
    expect(hidden).toContain(1);
    expect(hidden).toContain(2);
    expect(hidden).toContain(3);
  });

  it("returns only the ID, not the full UTub object", () => {
    const result = filterUTubsByName([{ id: 99, name: "nomatch" }], "xyz");
    expect(result).toEqual([99]);
  });
});
