import { $ } from "../../lib/globals.js";

import type { SearchHit, SearchUtubGroup } from "../../types/search.js";

// Renders the cross-UTub search results into #crossUtubSearchResults as grouped,
// read-only cards. Each group is a section headed by its source UTub name; each
// hit is a dedicated read-only card (NOT a reusable .urlRow) carrying the
// data-utub-id / data-utub-url-id attributes the click-to-navigate step reads.
// Matched fields (title/url/tag) receive the .crossSearchMatched emphasis class.
export function renderSearchResults({
  results,
}: {
  results: SearchUtubGroup[];
}): void {
  const resultsContainer = $("#crossUtubSearchResults");

  // Recent-search history (rendered when the input is empty) lives inside the
  // same container; drop it before painting result groups.
  $("#crossUtubSearchHistoryList").remove();

  resultsContainer.empty();

  results.forEach((group) => {
    const groupSection = $(document.createElement("section")).addClass(
      "crossSearchGroup",
    );

    $(document.createElement("h2"))
      .addClass("crossSearchGroupHeading")
      .text(group.utubName)
      .appendTo(groupSection);

    group.urls.forEach((hit) => {
      buildSearchHitCard({ hit, utubID: group.utubID }).appendTo(groupSection);
    });

    groupSection.appendTo(resultsContainer);
  });
}

function buildSearchHitCard({
  hit,
  utubID,
}: {
  hit: SearchHit;
  utubID: number;
}): JQuery<HTMLElement> {
  const matchedFields = hit.matchedFields;

  const card = $(document.createElement("div"))
    .addClass("crossSearchHitCard")
    .attr({
      "data-utub-id": utubID,
      "data-utub-url-id": hit.utubUrlID,
    });

  const title = $(document.createElement("div"))
    .addClass("crossSearchTitle")
    .text(hit.urlTitle);
  if (matchedFields.includes("title")) {
    title.addClass("crossSearchMatched");
  }
  title.appendTo(card);

  const urlLink = $(document.createElement("a"))
    .addClass("crossSearchUrl")
    .text(hit.urlString);
  // Only attach a live href for http(s) — mirrors the trust gate in
  // urls/cards/access.ts (accessLink) so a non-http(s) value (e.g. javascript:)
  // can never become a one-click navigation vector. The url text is always
  // shown via .text() (escaped) regardless.
  if (/^https?:\/\//i.test(hit.urlString)) {
    urlLink.attr("href", hit.urlString);
  }
  if (matchedFields.includes("url")) {
    urlLink.addClass("crossSearchMatched");
  }
  urlLink.appendTo(card);

  if (hit.urlTags.length > 0) {
    const tagWrap = $(document.createElement("div")).addClass(
      "crossSearchTags",
    );
    const tagMatched = matchedFields.includes("tag");

    hit.urlTags.forEach((tag) => {
      const tagBadge = $(document.createElement("span"))
        .addClass("crossSearchTag")
        .text(tag.tagString);
      if (tagMatched) {
        tagBadge.addClass("crossSearchMatched");
      }
      tagBadge.appendTo(tagWrap);
    });

    tagWrap.appendTo(card);
  }

  return card;
}
