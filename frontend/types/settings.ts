/**
 * Hand-written panel-settings types. The generated `UtubSettings` schema marks
 * every panel section optional; the client always holds the resolved shape with
 * all four sections present.
 */
import type { Schema } from "./api-helpers.d.ts";
import type {
  DensityValue,
  SortOrderValue,
  ViewModeValue,
} from "./preferences.js";

export type PanelId = "utubs" | "members" | "tags" | "urls";
export type SettingsScope = "utub" | "user";

export type UtubSettings = Schema<"UtubSettings">;
export type ResolvedUtubSettings = Required<UtubSettings>;

/** Resolved shape for a UTub with no stored settings. Copy it, never mutate it. */
export const EMPTY_UTUB_SETTINGS: ResolvedUtubSettings = Object.freeze({
  utubs: {},
  members: {},
  tags: {},
  urls: {
    default_url_scheme: "https",
    hide_scheme_selector: false,
    allow_short_links: true,
  },
});

export type MemberSettings = Schema<"UtubMemberSettings">;

type MemberUrlsSettings = Schema<"MemberUrlsSettings">;

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

export interface ResolvedMemberSettings {
  urls: ResolvedMemberUrlsSettings;
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
});

/** Copies a (possibly partial or absent) payload into the resolved shape. */
export function resolveMemberSettings(
  raw: MemberSettings | undefined | null,
): ResolvedMemberSettings {
  const urls: Partial<MemberUrlsSettings> | undefined = raw?.urls;
  return {
    urls: { ...EMPTY_MEMBER_SETTINGS.urls, ...urls },
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
