/**
 * Hand-written panel-settings types. The generated `UtubSettings` schema marks
 * every panel section optional; the client always holds the resolved shape with
 * all four sections present.
 */
import type { Schema } from "./api-helpers.d.ts";

export type PanelId = "utubs" | "members" | "tags" | "urls";
export type SettingsScope = "utub" | "user";

export type UtubSettings = Schema<"UtubSettings">;
export type ResolvedUtubSettings = Required<UtubSettings>;

/** Resolved shape for a UTub with no stored settings. Copy it, never mutate it. */
export const EMPTY_UTUB_SETTINGS: ResolvedUtubSettings = Object.freeze({
  utubs: {},
  members: {},
  tags: {},
  urls: {},
});

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
