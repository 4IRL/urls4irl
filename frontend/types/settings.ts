/**
 * Hand-written panel-settings types. The generated `UtubSettings` schema marks
 * every panel section optional; the client always holds the resolved shape with
 * all four sections present.
 */
import type { Schema } from "./api-helpers.d.ts";
import type {
  CollapsedTagsStyleValue,
  DensityValue,
  SortOrderValue,
  TagCountStyleValue,
  TagMatchModeValue,
  TagSortValue,
  ViewModeValue,
} from "./preferences.js";

export type PanelId = "utubs" | "members" | "tags" | "urls";
export type SettingsScope = "utub" | "user";

export type UtubSettings = Schema<"UtubSettings">;
export type ResolvedUtubSettings = Required<UtubSettings>;

/** Resolved shape for a UTub with no stored settings. Copy it, never mutate it. */
export const EMPTY_UTUB_SETTINGS: ResolvedUtubSettings = Object.freeze({
  utubs: {},
  members: {
    co_owners_can_remove: false,
    members_can_add: false,
    hide_member_list: false,
  },
  tags: {
    members_can_tag: true,
    members_can_delete_tags: true,
  },
  urls: {
    default_url_scheme: "https",
    hide_scheme_selector: false,
    allow_short_links: true,
  },
});

export type MemberSettings = Schema<"UtubMemberSettings">;

type MemberUrlsSettings = Schema<"MemberUrlsSettings">;
type MemberTagsSettings = Schema<"MemberTagsSettings">;

/** The member's own resolved URLs overrides, with enum values narrowed. */
export interface ResolvedMemberUrlsSettings {
  hide_copy_button: boolean;
  hide_short_link_button: boolean;
  hide_date_added: boolean;
  sort: SortOrderValue | null;
  view_mode: ViewModeValue | null;
  density: DensityValue | null;
  disable_swipe_delete: boolean;
}

/** The member's own resolved Tags overrides. Null means "use my default". */
export interface ResolvedMemberTagsSettings {
  tag_sort: TagSortValue | null;
  tag_match_mode: TagMatchModeValue | null;
  tag_count_style: TagCountStyleValue | null;
  show_tags_on_collapsed: boolean | null;
  collapsed_tags_style: CollapsedTagsStyleValue | null;
  tag_drop_opens_url: boolean | null;
}

export interface ResolvedMemberSettings {
  urls: ResolvedMemberUrlsSettings;
  tags: ResolvedMemberTagsSettings;
}

/** Resolved shape for a member with no overrides. Copy it, never mutate it. */
export const EMPTY_MEMBER_SETTINGS: ResolvedMemberSettings = Object.freeze({
  urls: Object.freeze({
    hide_copy_button: false,
    hide_short_link_button: false,
    hide_date_added: false,
    sort: null,
    view_mode: null,
    density: null,
    disable_swipe_delete: false,
  }),
  tags: Object.freeze({
    tag_sort: null,
    tag_match_mode: null,
    tag_count_style: null,
    show_tags_on_collapsed: null,
    collapsed_tags_style: null,
    tag_drop_opens_url: null,
  }),
});

/** Copies a (possibly partial or absent) payload into the resolved shape. */
export function resolveMemberSettings(
  raw: MemberSettings | undefined | null,
): ResolvedMemberSettings {
  const urls: Partial<MemberUrlsSettings> | undefined = raw?.urls;
  const tags: Partial<MemberTagsSettings> | undefined = raw?.tags;
  return {
    urls: { ...EMPTY_MEMBER_SETTINGS.urls, ...urls },
    tags: { ...EMPTY_MEMBER_SETTINGS.tags, ...tags },
  };
}

/** Copies a (possibly partial or absent) payload into the resolved shape. */
export function resolveUtubSettings(
  settings: UtubSettings | undefined | null,
): ResolvedUtubSettings {
  return {
    utubs: { ...EMPTY_UTUB_SETTINGS.utubs, ...settings?.utubs },
    members: { ...EMPTY_UTUB_SETTINGS.members, ...settings?.members },
    tags: { ...EMPTY_UTUB_SETTINGS.tags, ...settings?.tags },
    urls: { ...EMPTY_UTUB_SETTINGS.urls, ...settings?.urls },
  };
}
