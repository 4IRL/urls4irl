import { filterTagsByName } from "../tag-search.js";

describe("filterTagsByName", () => {
  const tags = [
    { id: 1, name: "Work Links" },
    { id: 2, name: "Personal" },
    { id: 3, name: "Work Projects" },
    { id: 4, name: "Shopping" },
  ];

  it("returns empty array when search term matches all names", () => {
    // Empty string is a substring of everything -- nothing is hidden
    expect(filterTagsByName(tags, "")).toEqual([]);
  });

  it("returns IDs of tags that do NOT contain the search term", () => {
    const hidden = filterTagsByName(tags, "work");
    expect(hidden).toEqual([2, 4]);
  });

  it("is case-insensitive (caller lowercases term; function lowercases name)", () => {
    const hidden = filterTagsByName(tags, "personal");
    expect(hidden).not.toContain(2);
  });

  it("returns all IDs when no name matches the search term", () => {
    const hidden = filterTagsByName(tags, "zzznomatch");
    expect(hidden).toEqual([1, 2, 3, 4]);
  });

  it("returns empty array for empty tag list", () => {
    expect(filterTagsByName([], "work")).toEqual([]);
  });

  it("matches partial substrings", () => {
    const hidden = filterTagsByName(tags, "shop");
    expect(hidden).not.toContain(4);
    expect(hidden).toContain(1);
    expect(hidden).toContain(2);
    expect(hidden).toContain(3);
  });

  it("returns only the ID, not the full tag object", () => {
    const result = filterTagsByName([{ id: 99, name: "nomatch" }], "xyz");
    expect(result).toEqual([99]);
  });
});
