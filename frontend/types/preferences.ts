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
export type ViewModeValue = "list" | "compact" | "cards";
export type SortOrderValue = "newest" | "oldest" | "title_az";
export type DensityValue = "comfortable" | "compact";
export type DateFormatValue = "iso" | "us" | "eu";
