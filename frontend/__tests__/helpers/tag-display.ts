import type { TagDisplayDefaults } from "../../home/utubs/selectors.js";

/** The six tag display defaults every user starts with (today's behavior). */
export const TAG_DISPLAY_PREFERENCE_DEFAULTS: TagDisplayDefaults = {
  tagSort: "most_in_view",
  tagMatchMode: "all",
  tagCountStyle: "in_view_total",
  showTagsOnCollapsed: false,
  collapsedTagsStyle: "one_line",
  tagDropOpensUrl: true,
};
