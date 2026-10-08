import { describe, expect, it } from "vitest";
import { fillTemplate } from "../string-template.js";

describe("fillTemplate", () => {
  it("replaces every placeholder", () => {
    expect(
      fillTemplate({
        template: "{kept} of {total} kept",
        values: { kept: "1", total: "2" },
      }),
    ).toBe("1 of 2 kept");
  });

  it("leaves an unknown placeholder untouched", () => {
    expect(fillTemplate({ template: "{a} {b}", values: { a: "x" } })).toBe(
      "x {b}",
    );
  });

  it("keeps $-style text in values literal", () => {
    expect(
      fillTemplate({ template: "got {param}", values: { param: "$& $1" } }),
    ).toBe("got $& $1");
  });

  it("does not re-scan substituted values", () => {
    expect(
      fillTemplate({
        template: "{a} {b}",
        values: { a: "{b}", b: "later" },
      }),
    ).toBe("{b} later");
  });
});
