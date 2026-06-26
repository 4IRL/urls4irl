import { getState, setState } from "../../../store/app-store.js";
import type { Schema, SuccessResponse } from "../../../types/api-helpers.d.ts";
import type { UtubTag } from "../../../types/url.js";

export type AddTagsRequest = Schema<"AddTagsRequest">;
export type UrlTagsModifiedResponse = SuccessResponse<"createUtubUrlTags">;
export type UrlTagError = Schema<"ErrorResponse_URLTagErrorCodes">;

/**
 * Returns the UTub tags whose label matches the query (case-insensitive
 * substring), excluding any tag already applied to the URL or already staged
 * as a chip.
 */
export function filterTagSuggestions({
  query,
  appliedTagIds,
  stagedTagStrings,
}: {
  query: string;
  appliedTagIds: number[];
  stagedTagStrings: string[];
}): UtubTag[] {
  const normalizedQuery = query.trim().toLowerCase();
  const appliedIdSet = new Set(appliedTagIds);
  const stagedSet = new Set(
    stagedTagStrings.map((stagedString) => stagedString.toLowerCase()),
  );

  return getState().tags.filter((tag) => {
    if (appliedIdSet.has(tag.id)) return false;
    if (stagedSet.has(tag.tagString.toLowerCase())) return false;
    return tag.tagString.toLowerCase().includes(normalizedQuery);
  });
}

/**
 * True when the query exactly matches an existing UTub tag string
 * (case-insensitive, after trim). Used to suppress the "Create tag" option.
 */
export function hasExactTagMatch({ query }: { query: string }): boolean {
  const normalizedQuery = query.trim().toLowerCase();
  if (normalizedQuery.length === 0) return false;
  return getState().tags.some(
    (tag) => tag.tagString.toLowerCase() === normalizedQuery,
  );
}

/**
 * Upserts the newly-applied tags into `getState().tags`: existing tags (matched
 * by `id`) have their `tagApplied` count refreshed, brand-new tags are appended.
 * Single-responsibility — only touches the `tags` store slice; the URL's
 * `utubUrlTagIDs` slice is updated separately by the submit success handler.
 */
export function mergeAppliedTagsIntoStore({
  appliedTags,
}: {
  appliedTags: UtubTag[];
}): void {
  const mergedTags = [...getState().tags];

  appliedTags.forEach((appliedTag) => {
    const existingIndex = mergedTags.findIndex(
      (tag) => tag.id === appliedTag.id,
    );
    if (existingIndex === -1) {
      mergedTags.push(appliedTag);
    } else {
      mergedTags[existingIndex] = {
        ...mergedTags[existingIndex],
        tagApplied: appliedTag.tagApplied,
      };
    }
  });

  setState({ tags: mergedTags });
}
