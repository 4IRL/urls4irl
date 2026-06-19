import { renderSearchResults } from "../render.js";

import type { SearchUtubGroup } from "../../../types/search.js";

const $ = window.jQuery;

const RESULTS_HTML = `<div id="crossUtubSearchResults"></div>`;

function buildFixture(): SearchUtubGroup[] {
  return [
    {
      utubID: 1,
      utubName: "Recipes",
      urls: [
        {
          utubUrlID: 10,
          urlString: "https://example.com/pasta",
          urlTitle: "Pasta Night",
          urlTags: [{ utubTagID: 100, tagString: "dinner" }],
          matchedFields: ["title", "url"],
        },
      ],
    },
    {
      utubID: 2,
      utubName: "Travel",
      urls: [
        {
          utubUrlID: 20,
          urlString: "https://example.com/rome",
          urlTitle: "Rome Trip",
          urlTags: [{ utubTagID: 200, tagString: "italy" }],
          matchedFields: ["tag"],
        },
        {
          utubUrlID: 21,
          urlString: "https://example.com/paris",
          urlTitle: "Paris Trip",
          urlTags: [],
          matchedFields: ["title"],
        },
      ],
    },
  ];
}

describe("renderSearchResults", () => {
  beforeEach(() => {
    document.body.innerHTML = RESULTS_HTML;
  });

  it("renders one group section per result entry, in array order, with the utubName heading", () => {
    renderSearchResults({ results: buildFixture(), query: "trip" });

    const groups = $("#crossUtubSearchResults").find(".crossSearchGroup");
    expect(groups.length).toBe(2);

    const headings = $("#crossUtubSearchResults").find(
      ".crossSearchGroupHeading",
    );
    expect(headings.eq(0).text()).toBe("Recipes");
    expect(headings.eq(1).text()).toBe("Travel");
  });

  it("renders one card per hit within each group, in array order", () => {
    renderSearchResults({ results: buildFixture(), query: "trip" });

    const firstGroupCards = $("#crossUtubSearchResults")
      .find(".crossSearchGroup")
      .eq(1)
      .find(".crossSearchHitCard");
    expect(firstGroupCards.length).toBe(2);
    expect(firstGroupCards.eq(0).attr("data-utub-url-id")).toBe("20");
    expect(firstGroupCards.eq(1).attr("data-utub-url-id")).toBe("21");
  });

  it("highlights the matched substring (preserving case) only within matched fields", () => {
    // Title "Pasta Night" and url ".../pasta" both match "pasta"; the tag
    // "dinner" is not in matchedFields, so it stays unhighlighted.
    renderSearchResults({ results: buildFixture(), query: "pasta" });

    const firstCard = $("#crossUtubSearchResults")
      .find(".crossSearchGroup")
      .eq(0)
      .find(".crossSearchHitCard")
      .eq(0);

    const titleMark = firstCard.find(".crossSearchTitle .crossSearchMatch");
    expect(titleMark.length).toBe(1);
    expect(titleMark.text()).toBe("Pasta");
    // The surrounding text is preserved, not just the matched fragment.
    expect(firstCard.find(".crossSearchTitle").text()).toBe("Pasta Night");

    const urlMark = firstCard.find(".crossSearchUrl .crossSearchMatch");
    expect(urlMark.length).toBe(1);
    expect(urlMark.text()).toBe("pasta");

    expect(firstCard.find(".crossSearchTag .crossSearchMatch").length).toBe(0);
  });

  it("highlights the matching substring within a tag when the tag field matched", () => {
    renderSearchResults({ results: buildFixture(), query: "ital" });

    const romeCard = $("#crossUtubSearchResults")
      .find(".crossSearchGroup")
      .eq(1)
      .find(".crossSearchHitCard")
      .eq(0);

    const tagMark = romeCard.find(".crossSearchTag .crossSearchMatch");
    expect(tagMark.length).toBe(1);
    expect(tagMark.text()).toBe("ital");
    expect(romeCard.find(".crossSearchTag").text()).toBe("italy");
  });

  it("removes a pre-existing #crossUtubSearchHistoryList before rendering groups", () => {
    $("#crossUtubSearchResults").append(
      `<section id="crossUtubSearchHistoryList"></section>`,
    );
    expect($("#crossUtubSearchHistoryList").length).toBe(1);

    renderSearchResults({ results: buildFixture(), query: "trip" });

    expect($("#crossUtubSearchHistoryList").length).toBe(0);
  });

  it("the URL link opens in a new tab", () => {
    renderSearchResults({ results: buildFixture(), query: "pasta" });

    const card = $("#crossUtubSearchResults").find(".crossSearchHitCard").eq(0);
    const link = card.find(".crossSearchUrl");
    expect(link.attr("href")).toBe("https://example.com/pasta");
    expect(link.attr("target")).toBe("_blank");
    expect(link.attr("rel")).toContain("noopener");
  });
});
