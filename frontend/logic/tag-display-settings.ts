/**
 * Pure resolver for the personal tag display settings. Each setting has an
 * account default (camelCase, `UserPreferences`) and an optional per-UTub
 * override (snake_case wire key, `memberSettings.tags`); a null override means
 * "use my default". Every reader goes through `resolveTagDisplaySettings`.
 */
import type { UserPreferences } from "../store/app-store.js";
import type { ResolvedMemberTagsSettings } from "../types/settings.js";

export type TagDisplayPreferences = Pick<
  UserPreferences,
  | "tagSort"
  | "tagMatchMode"
  | "tagCountStyle"
  | "showTagsOnCollapsed"
  | "collapsedTagsStyle"
  | "tagDropOpensUrl"
>;

export type TagDisplayKey = keyof TagDisplayPreferences;

/** The one map from a default's camelCase name to its override's snake_case key. */
export const TAG_OVERRIDE_KEYS: Readonly<
  Record<TagDisplayKey, keyof ResolvedMemberTagsSettings>
> = Object.freeze({
  tagSort: "tag_sort",
  tagMatchMode: "tag_match_mode",
  tagCountStyle: "tag_count_style",
  showTagsOnCollapsed: "show_tags_on_collapsed",
  collapsedTagsStyle: "collapsed_tags_style",
  tagDropOpensUrl: "tag_drop_opens_url",
});

/** The override if set, otherwise the account default, for all six settings. */
export function resolveTagDisplaySettings({
  preferences,
  tagsOverride,
}: {
  preferences: TagDisplayPreferences;
  tagsOverride: Partial<ResolvedMemberTagsSettings> | null | undefined;
}): TagDisplayPreferences {
  return {
    tagSort: tagsOverride?.tag_sort ?? preferences.tagSort,
    tagMatchMode: tagsOverride?.tag_match_mode ?? preferences.tagMatchMode,
    tagCountStyle: tagsOverride?.tag_count_style ?? preferences.tagCountStyle,
    showTagsOnCollapsed:
      tagsOverride?.show_tags_on_collapsed ?? preferences.showTagsOnCollapsed,
    collapsedTagsStyle:
      tagsOverride?.collapsed_tags_style ?? preferences.collapsedTagsStyle,
    tagDropOpensUrl:
      tagsOverride?.tag_drop_opens_url ?? preferences.tagDropOpensUrl,
  };
}
