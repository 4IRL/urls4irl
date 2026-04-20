import { filterURLsBySearchTerm } from "../url-search.js";

describe("filterURLsBySearchTerm", () => {
  const urls = [
    { id: 1, title: "Google Search", urlString: "https://google.com" },
    { id: 2, title: "GitHub Repos", urlString: "https://github.com" },
    { id: 3, title: "Stack Overflow", urlString: "https://stackoverflow.com" },
    { id: 4, title: "Reddit Front Page", urlString: "https://reddit.com" },
  ];

  it("returns empty array when search term is empty", () => {
    expect(filterURLsBySearchTerm(urls, "")).toEqual([]);
  });

  it("returns IDs of URLs whose title does NOT match the search term", () => {
    const hidden = filterURLsBySearchTerm(urls, "google");
    // "Google Search" title matches -- only ID 1 is NOT hidden
    expect(hidden).toEqual([2, 3, 4]);
  });

  it("returns IDs of URLs whose urlString does NOT match the search term", () => {
    const hidden = filterURLsBySearchTerm(urls, "stackoverflow");
    // "https://stackoverflow.com" matches -- only ID 3 is NOT hidden
    expect(hidden).toEqual([1, 2, 4]);
  });

  it("returns only IDs that match neither title nor urlString", () => {
    // "git" matches GitHub title AND github.com urlString (ID 2)
    // "reddit" matches Reddit title (ID 4) AND reddit.com urlString (ID 4)
    // Use a term that hits title on one URL and urlString on another
    const hidden = filterURLsBySearchTerm(
      [
        { id: 10, title: "My Bookmarks", urlString: "https://example.com" },
        { id: 20, title: "Dev Tools", urlString: "https://devtools.org" },
        { id: 30, title: "Example Site", urlString: "https://other.org" },
      ],
      "example",
    );
    // ID 10 matches via urlString, ID 30 matches via title -- both visible
    expect(hidden).toEqual([20]);
  });

  it("is case-insensitive", () => {
    const hidden = filterURLsBySearchTerm(urls, "GOOGLE");
    // Should still match "Google Search" title and "google.com" urlString
    expect(hidden).toEqual([2, 3, 4]);
  });

  it("returns all IDs when no URL matches the search term", () => {
    const hidden = filterURLsBySearchTerm(urls, "zzznomatch");
    expect(hidden).toEqual([1, 2, 3, 4]);
  });

  it("returns empty array for empty URL list", () => {
    expect(filterURLsBySearchTerm([], "anything")).toEqual([]);
  });

  it("matches partial substrings", () => {
    const hidden = filterURLsBySearchTerm(urls, "goo");
    // "goo" matches "Google Search" (title) and "google.com" (urlString) for ID 1
    expect(hidden).not.toContain(1);
    expect(hidden).toContain(2);
    expect(hidden).toContain(3);
    expect(hidden).toContain(4);
  });
});
