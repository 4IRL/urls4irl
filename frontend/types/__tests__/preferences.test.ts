import { MEMBER_SORT_VALUES, isMemberSortValue } from "../preferences.js";

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
