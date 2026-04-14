import { modifyURLStringForDisplay } from "../url-string.js";

describe("modifyURLStringForDisplay", () => {
  it("strips https:// prefix", () => {
    expect(modifyURLStringForDisplay("https://example.com")).toBe(
      "example.com",
    );
  });

  it("strips http:// prefix", () => {
    expect(modifyURLStringForDisplay("http://example.com")).toBe("example.com");
  });

  it("strips www. prefix alone", () => {
    expect(modifyURLStringForDisplay("www.example.com")).toBe("example.com");
  });

  it("strips https://www. combined prefix", () => {
    expect(modifyURLStringForDisplay("https://www.example.com")).toBe(
      "example.com",
    );
  });

  it("strips http://www. combined prefix", () => {
    expect(modifyURLStringForDisplay("http://www.example.com")).toBe(
      "example.com",
    );
  });

  it("preserves path after stripping https://", () => {
    expect(modifyURLStringForDisplay("https://example.com/path/to/page")).toBe(
      "example.com/path/to/page",
    );
  });

  it("preserves path after stripping https://www.", () => {
    expect(modifyURLStringForDisplay("https://www.example.com/path")).toBe(
      "example.com/path",
    );
  });

  it("does not strip non-http protocols", () => {
    expect(modifyURLStringForDisplay("ftp://example.com")).toBe(
      "ftp://example.com",
    );
  });

  it("returns string unchanged when no recognisable prefix is present", () => {
    expect(modifyURLStringForDisplay("example.com")).toBe("example.com");
  });

  it("returns empty string for empty input", () => {
    expect(modifyURLStringForDisplay("")).toBe("");
  });
});
