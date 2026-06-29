import { filterMembersByName } from "../member-search.js";

describe("filterMembersByName", () => {
  const members = [
    { id: 1, name: "alice_owner" },
    { id: 2, name: "bob_dev" },
    { id: 3, name: "carol_design" },
    { id: 4, name: "dave_qa" },
  ];

  it("returns empty array when search term matches all names", () => {
    // Empty string is a substring of everything -- nothing is hidden
    expect(filterMembersByName(members, "")).toEqual([]);
  });

  it("returns IDs of members that do NOT contain the search term", () => {
    const hidden = filterMembersByName(members, "ca");
    expect(hidden).toEqual([1, 2, 4]);
  });

  it("is case-insensitive (caller lowercases term; function lowercases name)", () => {
    const hidden = filterMembersByName(members, "alice");
    expect(hidden).not.toContain(1);
  });

  it("returns all IDs when no name matches the search term", () => {
    const hidden = filterMembersByName(members, "zzznomatch");
    expect(hidden).toEqual([1, 2, 3, 4]);
  });

  it("returns empty array for empty member list", () => {
    expect(filterMembersByName([], "alice")).toEqual([]);
  });

  it("matches partial substrings", () => {
    const hidden = filterMembersByName(members, "dev");
    expect(hidden).not.toContain(2);
    expect(hidden).toContain(1);
    expect(hidden).toContain(3);
    expect(hidden).toContain(4);
  });

  it("returns only the ID, not the full member object", () => {
    const result = filterMembersByName([{ id: 99, name: "nomatch" }], "xyz");
    expect(result).toEqual([99]);
  });
});
