import { $ } from "../../lib/globals.js";

import type { SearchHit, SearchUtubGroup } from "../../types/search.js";

// Renders the cross-UTub search results into #crossUtubSearchResults as grouped,
// read-only cards. Each group is a section headed by its source UTub name; each
// hit is a dedicated read-only card (NOT a reusable .urlRow) carrying the
// data-utub-id / data-utub-url-id attributes the click-to-navigate step reads.
// Within each matched field, the exact substring that matched `query` is wrapped
// in a <mark class="crossSearchMatch"> (the backend matches case-insensitive
// substrings, so the term is always locatable in the field text).
export function renderSearchResults({
  results,
  query,
}: {
  results: SearchUtubGroup[];
  query: string;
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
      buildSearchHitCard({ hit, utubID: group.utubID, query }).appendTo(
        groupSection,
      );
    });

    groupSection.appendTo(resultsContainer);
  });
}

// Appends `text` to `element`, wrapping each case-insensitive occurrence of
// `query` in a <mark class="crossSearchMatch">. Non-matching segments are plain
// text nodes so user-supplied content stays escaped (never set via innerHTML).
// Falls back to plain text when the query is empty or not present in the text.
function appendHighlighted({
  element,
  text,
  query,
}: {
  element: JQuery<HTMLElement>;
  text: string;
  query: string;
}): void {
  const lowerText = text.toLowerCase();
  const lowerQuery = query.toLowerCase();
  if (query.length === 0 || !lowerText.includes(lowerQuery)) {
    element.text(text);
    return;
  }

  let cursor = 0;
  let matchIndex = lowerText.indexOf(lowerQuery, cursor);
  while (matchIndex !== -1) {
    if (matchIndex > cursor) {
      element.append(document.createTextNode(text.slice(cursor, matchIndex)));
    }
    const matchEnd = matchIndex + query.length;
    $(document.createElement("mark"))
      .addClass("crossSearchMatch")
      .text(text.slice(matchIndex, matchEnd))
      .appendTo(element);
    cursor = matchEnd;
    matchIndex = lowerText.indexOf(lowerQuery, cursor);
  }
  if (cursor < text.length) {
    element.append(document.createTextNode(text.slice(cursor)));
  }
}

function buildSearchHitCard({
  hit,
  utubID,
  query,
}: {
  hit: SearchHit;
  utubID: number;
  query: string;
}): JQuery<HTMLElement> {
  const matchedFields = hit.matchedFields;

  const card = $(document.createElement("div"))
    .addClass("crossSearchHitCard")
    .attr({
      "data-utub-id": utubID,
      "data-utub-url-id": hit.utubUrlID,
    });

  const title = $(document.createElement("div")).addClass("crossSearchTitle");
  if (matchedFields.includes("title")) {
    appendHighlighted({ element: title, text: hit.urlTitle, query });
  } else {
    title.text(hit.urlTitle);
  }
  title.appendTo(card);

  const urlLink = $(document.createElement("a")).addClass("crossSearchUrl");
  if (matchedFields.includes("url")) {
    appendHighlighted({ element: urlLink, text: hit.urlString, query });
  } else {
    urlLink.text(hit.urlString);
  }
  // Only attach a live href for http(s) — mirrors the trust gate in
  // urls/cards/access.ts (accessLink) so a non-http(s) value (e.g. javascript:)
  // can never become a one-click navigation vector. The url text is always
  // shown via .text()/text nodes (escaped) regardless.
  if (/^https?:\/\//i.test(hit.urlString)) {
    urlLink.attr("href", hit.urlString);
  }
  urlLink.appendTo(card);

  if (hit.urlTags.length > 0) {
    const tagWrap = $(document.createElement("div")).addClass(
      "crossSearchTags",
    );
    // Only highlight within tags when the tag field matched; appendHighlighted
    // then marks exactly the tags that contain the term (others stay plain).
    const tagMatched = matchedFields.includes("tag");

    hit.urlTags.forEach((tag) => {
      const tagBadge = $(document.createElement("span")).addClass(
        "crossSearchTag",
      );
      if (tagMatched) {
        appendHighlighted({ element: tagBadge, text: tag.tagString, query });
      } else {
        tagBadge.text(tag.tagString);
      }
      tagBadge.appendTo(tagWrap);
    });

    tagWrap.appendTo(card);
  }

  return card;
}
