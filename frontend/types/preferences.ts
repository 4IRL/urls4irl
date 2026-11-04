/**
 * Hand-written literal-union type aliases for each user-preference enum's
 * `.value` strings.
 *
 * The generated OpenAPI types (`api.d.ts`) widen every enum-backed Pydantic
 * field to plain `string` (confirmed against the existing `memberRole`/`role`
 * fields, both Python `Enum` columns that render as bare `string`), so
 * `Schema<...>` alone can never give a controller a narrow, exhaustively
 * checkable preference type. These aliases are the single source of that
 * narrowing and must stay in lockstep with the Python enums in
 * `backend/models/user_preferences.py`.
 */

export type ThemeValue = "light" | "dark" | "system";
export type ViewModeValue = "list" | "title_line" | "url_line" | "cards";
export type SortOrderValue = "newest" | "oldest" | "title_az";
export type DensityValue = "comfortable" | "compact";
export type DateFormatValue = "iso" | "us" | "eu";
export type UtubSortValue =
  | "recent_activity"
  | "last_opened"
  | "name_az"
  | "newest_created"
  | "oldest_created";

export const UTUB_SORT_VALUES: readonly UtubSortValue[] = [
  "recent_activity",
  "last_opened",
  "name_az",
  "newest_created",
  "oldest_created",
];

export type MemberSortValue = "name_az" | "role_then_name" | "recently_joined";

export const MEMBER_SORT_VALUES: readonly MemberSortValue[] = [
  "name_az",
  "role_then_name",
  "recently_joined",
];

export type TagSortValue =
  | "most_in_view"
  | "most_used"
  | "name_az"
  | "newest"
  | "oldest";

export const TAG_SORT_VALUES: readonly TagSortValue[] = [
  "most_in_view",
  "most_used",
  "name_az",
  "newest",
  "oldest",
];

export type TagMatchModeValue = "all" | "any";

export const TAG_MATCH_MODE_VALUES: readonly TagMatchModeValue[] = [
  "all",
  "any",
];

export type TagCountStyleValue = "in_view_total" | "total_only" | "hidden";

export const TAG_COUNT_STYLE_VALUES: readonly TagCountStyleValue[] = [
  "in_view_total",
  "total_only",
  "hidden",
];

export type CollapsedTagsStyleValue = "one_line" | "all";

export const COLLAPSED_TAGS_STYLE_VALUES: readonly CollapsedTagsStyleValue[] = [
  "one_line",
  "all",
];

export function isTagSortValue(value: unknown): value is TagSortValue {
  return TAG_SORT_VALUES.some((candidate) => candidate === value);
}

export function isTagMatchModeValue(
  value: unknown,
): value is TagMatchModeValue {
  return TAG_MATCH_MODE_VALUES.some((candidate) => candidate === value);
}

export function isTagCountStyleValue(
  value: unknown,
): value is TagCountStyleValue {
  return TAG_COUNT_STYLE_VALUES.some((candidate) => candidate === value);
}

export function isCollapsedTagsStyleValue(
  value: unknown,
): value is CollapsedTagsStyleValue {
  return COLLAPSED_TAGS_STYLE_VALUES.some((candidate) => candidate === value);
}

export function isMemberSortValue(value: unknown): value is MemberSortValue {
  return MEMBER_SORT_VALUES.some((candidate) => candidate === value);
}

export function isUtubSortValue(value: unknown): value is UtubSortValue {
  return UTUB_SORT_VALUES.some((candidate) => candidate === value);
}
