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
    renderSearchResults({ results: buildFixture() });

    const groups = $("#crossUtubSearchResults").find(".crossSearchGroup");
    expect(groups.length).toBe(2);

    const headings = $("#crossUtubSearchResults").find(
      ".crossSearchGroupHeading",
    );
    expect(headings.eq(0).text()).toBe("Recipes");
    expect(headings.eq(1).text()).toBe("Travel");
  });

  it("renders one card per hit within each group, in array order", () => {
    renderSearchResults({ results: buildFixture() });

    const firstGroupCards = $("#crossUtubSearchResults")
      .find(".crossSearchGroup")
      .eq(1)
      .find(".crossSearchHitCard");
    expect(firstGroupCards.length).toBe(2);
    expect(firstGroupCards.eq(0).attr("data-utub-url-id")).toBe("20");
    expect(firstGroupCards.eq(1).attr("data-utub-url-id")).toBe("21");
  });

  it("applies the match-highlight class only to the fields named in matchedFields", () => {
    renderSearchResults({ results: buildFixture() });

    const firstCard = $("#crossUtubSearchResults")
      .find(".crossSearchGroup")
      .eq(0)
      .find(".crossSearchHitCard")
      .eq(0);

    expect(
      firstCard.find(".crossSearchTitle").hasClass("crossSearchMatched"),
    ).toBe(true);
    expect(
      firstCard.find(".crossSearchUrl").hasClass("crossSearchMatched"),
    ).toBe(true);
    expect(
      firstCard.find(".crossSearchTag").hasClass("crossSearchMatched"),
    ).toBe(false);
  });

  it("removes a pre-existing #crossUtubSearchHistoryList before rendering groups", () => {
    $("#crossUtubSearchResults").append(
      `<section id="crossUtubSearchHistoryList"></section>`,
    );
    expect($("#crossUtubSearchHistoryList").length).toBe(1);

    renderSearchResults({ results: buildFixture() });

    expect($("#crossUtubSearchHistoryList").length).toBe(0);
  });
});
