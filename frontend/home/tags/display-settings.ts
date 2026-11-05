import {
  resolveTagDisplaySettings,
  type TagDisplayPreferences,
} from "../../logic/tag-display-settings.js";
import { getState } from "../../store/app-store.js";

/**
 * The member's resolved tag display settings: the per-UTub override when one is
 * set, otherwise the account default. Every reader goes through here.
 */
export function effectiveTagDisplaySettings(): TagDisplayPreferences {
  const { preferences, memberSettings } = getState();
  return resolveTagDisplaySettings({
    preferences,
    tagsOverride: memberSettings?.tags,
  });
}
