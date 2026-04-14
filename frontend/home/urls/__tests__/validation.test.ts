import { isValidURL, generateURLObj } from "../validation.js";

describe("isValidURL", () => {
  describe("returns false for non-string or empty inputs", () => {
    it("returns false for empty string", () => {
      expect(isValidURL("")).toBe(false);
    });

    it("returns false for null", () => {
      expect(isValidURL(null)).toBe(false);
    });

    it("returns false for undefined", () => {
      expect(isValidURL(undefined)).toBe(false);
    });

    it("returns false for a number", () => {
      expect(isValidURL(42)).toBe(false);
    });

    it("returns false for whitespace-only string", () => {
      expect(isValidURL("   ")).toBe(false);
    });
  });

  describe("returns true for valid URLs", () => {
    it("accepts https:// URL", () => {
      expect(isValidURL("https://example.com")).toBe(true);
    });

    it("accepts http:// URL", () => {
      expect(isValidURL("http://example.com")).toBe(true);
    });

    it("accepts URL without protocol (adds https://)", () => {
      expect(isValidURL("example.com")).toBe(true);
    });

    it("accepts URL with a path", () => {
      expect(isValidURL("https://example.com/path/to/page")).toBe(true);
    });

    it("accepts URL with query params", () => {
      expect(isValidURL("https://example.com?foo=bar")).toBe(true);
    });

    it("normalises uppercase protocol before validating", () => {
      expect(isValidURL("HTTPS://EXAMPLE.COM")).toBe(true);
    });
  });

  describe("blocks dangerous protocol vectors", () => {
    it("rejects javascript: protocol", () => {
      expect(isValidURL("javascript:alert(1)")).toBe(false);
    });

    it("rejects data: protocol", () => {
      expect(isValidURL("data:text/html,<script>alert(1)</script>")).toBe(
        false,
      );
    });

    it("rejects vbscript: protocol", () => {
      expect(isValidURL("vbscript:MsgBox(1)")).toBe(false);
    });

    it("rejects JAVASCRIPT: (uppercase) after normalisation", () => {
      expect(isValidURL("JAVASCRIPT:alert(1)")).toBe(false);
    });
  });

  describe("returns false for unparseable strings", () => {
    it("rejects string containing spaces", () => {
      expect(isValidURL("not a url with spaces")).toBe(false);
    });
  });
});

describe("generateURLObj", () => {
  it("returns a URL instance for a valid URL", () => {
    const url = generateURLObj("https://example.com");
    expect(url).toBeInstanceOf(URL);
    expect(url.hostname).toBe("example.com");
  });

  it("returns null for an invalid URL string", () => {
    expect(generateURLObj("not a valid url")).toBeNull();
  });

  it("returns null for an empty string", () => {
    expect(generateURLObj("")).toBeNull();
  });

  it("returns URL with correct protocol for ftp:// input", () => {
    const url = generateURLObj("ftp://files.example.com");
    expect(url).toBeInstanceOf(URL);
    expect(url.protocol).toBe("ftp:");
  });
});
