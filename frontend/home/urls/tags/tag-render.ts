import type { UtubTag } from "../../../types/url.js";

import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { mergeAppliedTagsIntoStore } from "./combobox-state.js";
import { createTagBadgeInURL } from "./tags.js";
import { isTagInUTubTagDeck } from "../../tags/utils.js";
import { reapplyTagFilter } from "../../tags/search.js";
import { buildTagFilterInDeck } from "../../tags/tags.js";
import { updateTagFilterCount, TagCountOperation } from "../cards/filtering.js";

/**
 * Renders a set of applied tags onto a URL card and syncs the tag deck.
 *
 * Shared by `submitStagedTagsSuccess` (existing-URL batch apply) and
 * `createURLSuccess` (atomic create-with-tags) so both flows render badges and
 * deck filters identically. Co-located here to avoid a circular import:
 * `combobox.ts` must not import from `create.ts`/`cards.ts`.
 *
 * The body runs in a fixed order: the in-deck snapshot is taken BEFORE
 * `mergeAppliedTagsIntoStore`, otherwise every applied tag (including brand-new
 * ones the merge appends to the store) would report as already in-deck and its
 * deck filter would never be built.
 *
 * This helper is render-only: it does NOT re-evaluate URL visibility
 * (`updateURLsAndTagSubheaderWhenTagSelected`). That responsibility stays with
 * `createURLSuccess`, so the existing batch-apply flow is unaffected.
 */
export function renderAppliedTagsForUrl({
  appliedTags,
  utubUrlTagIDs,
  urlCard,
  utubID,
}: {
  appliedTags: UtubTag[];
  utubUrlTagIDs: number[];
  urlCard: JQuery;
  utubID: number;
}): void {
  // Snapshot which applied tags already existed in the deck BEFORE merging the
  // response into the store (the merge appends brand-new tags to the store,
  // which would otherwise flip the new-vs-existing routing below).
  const tagIdsAlreadyInDeck = new Set(
    appliedTags
      .filter((appliedTag) => isTagInUTubTagDeck(appliedTag.id))
      .map((appliedTag) => appliedTag.id),
  );

  mergeAppliedTagsIntoStore({ appliedTags });

  const tagsContainer = urlCard.find(".urlTagsContainer");
  urlCard.attr("data-utub-url-tag-ids", utubUrlTagIDs.join(","));

  let builtNewDeckFilter = false;
  appliedTags.forEach((appliedTag) => {
    tagsContainer.append(
      createTagBadgeInURL(appliedTag.id, appliedTag.tagString, urlCard, utubID),
    );

    if (!tagIdsAlreadyInDeck.has(appliedTag.id)) {
      const newTag = buildTagFilterInDeck(
        utubID,
        appliedTag.id,
        appliedTag.tagString,
        appliedTag.tagApplied,
      );
      if (
        $(".tagFilter.selected").length ===
        APP_CONFIG.constants.TAGS_MAX_ON_URLS
      ) {
        newTag.addClass("disabled").off(".tagFilterSelected");
      }
      $("#listTags").append(newTag);
      reapplyTagFilter();
      builtNewDeckFilter = true;
    } else {
      updateTagFilterCount(
        appliedTag.id,
        appliedTag.tagApplied,
        TagCountOperation.INCREMENT,
      );
    }
  });

  if (appliedTags.length > 0) {
    $("#unselectAllTagFilters").showClassNormal();
  }

  if (builtNewDeckFilter) {
    $("#utubTagBtnUpdateAllOpen").showClassNormal();
  }
}
