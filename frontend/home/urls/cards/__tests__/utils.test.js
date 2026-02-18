import { isEmptyString } from "../utils.js";

describe("isEmptyString", () => {
  describe("returns true for empty or blank inputs", () => {
    it("returns true for null", () => {
      expect(isEmptyString(null)).toBe(true);
    });

    it("returns true for undefined", () => {
      expect(isEmptyString(undefined)).toBe(true);
    });

    it("returns true for empty string", () => {
      expect(isEmptyString("")).toBe(true);
    });

    it("returns true for whitespace-only string", () => {
      expect(isEmptyString("   ")).toBe(true);
    });

    it("returns true for tab character", () => {
      expect(isEmptyString("\t")).toBe(true);
    });

    it("returns true for newline character", () => {
      expect(isEmptyString("\n")).toBe(true);
    });
  });

  describe("returns false for non-empty strings", () => {
    it("returns false for plain text", () => {
      expect(isEmptyString("hello")).toBe(false);
    });

    it("returns false for text with surrounding spaces", () => {
      expect(isEmptyString("  hello  ")).toBe(false);
    });

    it("returns false for single character", () => {
      expect(isEmptyString("a")).toBe(false);
    });
  });
});
