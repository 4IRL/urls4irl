import {
  COLLAPSED_TAGS_STYLE_VALUES,
  MEMBER_SORT_VALUES,
  TAG_COUNT_STYLE_VALUES,
  TAG_MATCH_MODE_VALUES,
  TAG_SORT_VALUES,
  isCollapsedTagsStyleValue,
  isMemberSortValue,
  isTagCountStyleValue,
  isTagMatchModeValue,
  isTagSortValue,
} from "../preferences.js";

describe("isMemberSortValue", () => {
  it.each(MEMBER_SORT_VALUES)("accepts %s", (value) => {
    expect(isMemberSortValue(value)).toBe(true);
  });

  it("rejects an unknown string", () => {
    expect(isMemberSortValue("newest_created")).toBe(false);
  });

  it.each([undefined, null, 1, {}, ["name_az"]])(
    "rejects non-string %p",
    (value) => {
      expect(isMemberSortValue(value)).toBe(false);
    },
  );
});

describe.each([
  ["isTagSortValue", isTagSortValue, TAG_SORT_VALUES],
  ["isTagMatchModeValue", isTagMatchModeValue, TAG_MATCH_MODE_VALUES],
  ["isTagCountStyleValue", isTagCountStyleValue, TAG_COUNT_STYLE_VALUES],
  [
    "isCollapsedTagsStyleValue",
    isCollapsedTagsStyleValue,
    COLLAPSED_TAGS_STYLE_VALUES,
  ],
])("%s", (_name, guard, values) => {
  it.each(values)("accepts %s", (value) => {
    expect(guard(value)).toBe(true);
  });

  it.each(["bogus", "", "ALL"])("rejects unknown string %p", (value) => {
    expect(guard(value)).toBe(false);
  });

  it.each([undefined, null, 1, true, {}, ["all"]])(
    "rejects non-string %p",
    (value) => {
      expect(guard(value)).toBe(false);
    },
  );
});
