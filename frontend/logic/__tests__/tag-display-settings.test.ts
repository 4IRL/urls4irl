import { describe, expect, it } from "vitest";

import {
  TAG_OVERRIDE_KEYS,
  resolveTagDisplaySettings,
  type TagDisplayKey,
  type TagDisplayPreferences,
} from "../tag-display-settings.js";
import { EMPTY_MEMBER_SETTINGS } from "../../types/settings.js";

const DEFAULTS: TagDisplayPreferences = {
  tagSort: "most_in_view",
  tagMatchMode: "all",
  tagCountStyle: "in_view_total",
  showTagsOnCollapsed: false,
  collapsedTagsStyle: "one_line",
  tagDropOpensUrl: true,
};

describe("resolveTagDisplaySettings", () => {
  it("returns the defaults when every override is null", () => {
    expect(
      resolveTagDisplaySettings({
        preferences: DEFAULTS,
        tagsOverride: EMPTY_MEMBER_SETTINGS.tags,
      }),
    ).toEqual(DEFAULTS);
  });

  it("returns the defaults when there is no override object", () => {
    expect(
      resolveTagDisplaySettings({
        preferences: DEFAULTS,
        tagsOverride: undefined,
      }),
    ).toEqual(DEFAULTS);
    expect(
      resolveTagDisplaySettings({ preferences: DEFAULTS, tagsOverride: null }),
    ).toEqual(DEFAULTS);
  });

  it("override wins for all six keys", () => {
    const resolved = resolveTagDisplaySettings({
      preferences: DEFAULTS,
      tagsOverride: {
        tag_sort: "name_az",
        tag_match_mode: "any",
        tag_count_style: "hidden",
        show_tags_on_collapsed: true,
        collapsed_tags_style: "all",
        tag_drop_opens_url: false,
      },
    });
    expect(resolved).toEqual({
      tagSort: "name_az",
      tagMatchMode: "any",
      tagCountStyle: "hidden",
      showTagsOnCollapsed: true,
      collapsedTagsStyle: "all",
      tagDropOpensUrl: false,
    });
  });

  it("a false boolean override wins over a true default, and null falls through", () => {
    const withFalse = resolveTagDisplaySettings({
      preferences: DEFAULTS,
      tagsOverride: { tag_drop_opens_url: false },
    });
    expect(withFalse.tagDropOpensUrl).toBe(false);
    const withNull = resolveTagDisplaySettings({
      preferences: DEFAULTS,
      tagsOverride: { tag_drop_opens_url: null },
    });
    expect(withNull.tagDropOpensUrl).toBe(true);
  });

  it("a single set override leaves the other five on their defaults", () => {
    const resolved = resolveTagDisplaySettings({
      preferences: DEFAULTS,
      tagsOverride: { ...EMPTY_MEMBER_SETTINGS.tags, tag_sort: "oldest" },
    });
    expect(resolved).toEqual({ ...DEFAULTS, tagSort: "oldest" });
  });
});

describe("TAG_OVERRIDE_KEYS", () => {
  it("covers all six defaults and all six override keys, one to one", () => {
    const defaultKeys: TagDisplayKey[] = Object.keys(DEFAULTS).filter(
      (key): key is TagDisplayKey => key in TAG_OVERRIDE_KEYS,
    );
    expect(defaultKeys).toHaveLength(6);
    expect(Object.keys(TAG_OVERRIDE_KEYS).sort()).toEqual(
      Object.keys(DEFAULTS).sort(),
    );
    const overrideKeys = Object.values(TAG_OVERRIDE_KEYS);
    expect(new Set(overrideKeys).size).toBe(6);
    expect([...overrideKeys].sort()).toEqual(
      Object.keys(EMPTY_MEMBER_SETTINGS.tags).sort(),
    );
  });
});
