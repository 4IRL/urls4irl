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

  let sliceStart = 0;
  let matchIndex = lowerText.indexOf(lowerQuery, sliceStart);
  while (matchIndex !== -1) {
    if (matchIndex > sliceStart) {
      element.append(
        document.createTextNode(text.slice(sliceStart, matchIndex)),
      );
    }
    const matchEnd = matchIndex + query.length;
    $(document.createElement("mark"))
      .addClass("crossSearchMatch")
      .text(text.slice(matchIndex, matchEnd))
      .appendTo(element);
    sliceStart = matchEnd;
    matchIndex = lowerText.indexOf(lowerQuery, sliceStart);
  }
  if (sliceStart < text.length) {
    element.append(document.createTextNode(text.slice(sliceStart)));
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
  // shown via .text()/text nodes (escaped) regardless. The click handling that
  // opens the link, stops propagation to the card's navigate handler, and
  // records the access metric lives in cross-utub-search.ts (delegated on
  // .crossSearchUrl), keeping this renderer pure.
  if (/^https?:\/\//i.test(hit.urlString)) {
    urlLink
      .attr("href", hit.urlString)
      .attr("target", "_blank")
      .attr("rel", "noopener noreferrer");

    // Top-right go-to affordance, mirroring the regular URL deck's corner icon.
    // Only emitted for openable http(s) URLs (same gate as the live href above).
    // The renderer stays pure: the click — which opens the link, stops the
    // card's navigate handler, and records the access metric — is delegated on
    // .crossSearchGoTo in cross-utub-search.ts. The SVG below is a static
    // literal, so `.html()` is safe (no user content), matching how the history
    // trash button is built.
    $(document.createElement("a"))
      .addClass("crossSearchGoTo")
      .attr("href", hit.urlString)
      .attr("target", "_blank")
      .attr("rel", "noopener noreferrer")
      .attr("aria-label", "Open this URL in a new tab")
      .html(
        '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="currentColor" class="bi bi-arrow-up-right-square-fill" viewBox="0 0 16 16"><path d="M14 0a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V2a2 2 0 0 1 2-2zM5.904 10.803 10 6.707v2.768a.5.5 0 0 0 1 0V5.5a.5.5 0 0 0-.5-.5H6.525a.5.5 0 1 0 0 1h2.768l-4.096 4.096a.5.5 0 0 0 .707.707"/></svg>',
      )
      .appendTo(card);
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
