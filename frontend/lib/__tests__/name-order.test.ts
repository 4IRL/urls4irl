import { describe, expect, it } from "vitest";

import { compareCodePoints, foldName } from "../name-order.js";

describe("foldName", () => {
  it("lowercases ASCII", () => {
    expect(foldName("AbC")).toBe("abc");
  });

  it("expands sharp s like casefold", () => {
    expect(foldName("Straße")).toBe("strasse");
  });

  it("folds a final sigma to the medial sigma", () => {
    expect(foldName("ΟΔΟΣ")).toBe("οδοσ");
    expect(foldName("οδος")).toBe("οδοσ");
  });

  it("folds astral characters per code point", () => {
    expect(foldName("\u{10400}")).toBe("\u{10428}");
  });
});

describe("compareCodePoints", () => {
  it("returns 0 for equal strings", () => {
    expect(compareCodePoints({ left: "abc", right: "abc" })).toBe(0);
  });

  it("orders by code point", () => {
    expect(compareCodePoints({ left: "a", right: "b" })).toBe(-1);
    expect(compareCodePoints({ left: "b", right: "a" })).toBe(1);
  });

  it("orders astral characters after U+E000-U+FFFF", () => {
    expect(compareCodePoints({ left: "\u{10000}", right: "" })).toBe(1);
    expect(compareCodePoints({ left: "￿", right: "\u{10000}" })).toBe(-1);
  });

  it("orders a proper prefix before the longer string", () => {
    expect(compareCodePoints({ left: "ab", right: "abc" })).toBe(-1);
    expect(compareCodePoints({ left: "abc", right: "ab" })).toBe(1);
    expect(compareCodePoints({ left: "", right: "a" })).toBe(-1);
  });

  it("breaks prefix ties after an astral character", () => {
    expect(compareCodePoints({ left: "\u{10000}", right: "\u{10000}a" })).toBe(
      -1,
    );
  });
});
