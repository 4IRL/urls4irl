import { APP_CONFIG } from "../../../../lib/config.js";
import {
  composeURL,
  hasUnsupportedSchemePrefix,
  isAuthorityScheme,
  isDevHostText,
  splitScheme,
} from "../scheme-utils.js";

describe("splitScheme", () => {
  it.each([
    ["https://example.com/a", { scheme: "https", rest: "example.com/a" }],
    ["HTTP://X.com", { scheme: "http", rest: "X.com" }],
    ["  https://x", { scheme: "https", rest: "x" }],
    ["mailto:a@b.com", { scheme: "mailto", rest: "a@b.com" }],
    ["spotify://track/x", { scheme: "spotify", rest: "//track/x" }],
    ["spotify:track:x", { scheme: "spotify", rest: "track:x" }],
    [
      "https://user:pass@host.com",
      { scheme: "https", rest: "user:pass@host.com" },
    ],
    ["tel:", { scheme: "tel", rest: "" }],
  ])("splits %j", (urlString, expected) => {
    expect(splitScheme({ urlString })).toEqual(expected);
  });

  it.each([
    "ssh:22",
    "ftp:21/x",
    "localhost:3000",
    "example.com:8080/x",
    "foo://x",
    "javascript:alert(1)",
    "data:text/html,x",
    "https:////x",
    "example.com",
    "",
  ])("returns null for %j (lossless-or-null)", (urlString) => {
    expect(splitScheme({ urlString })).toBeNull();
  });
});

describe("isAuthorityScheme", () => {
  it.each([
    ["https", true],
    ["ssh", true],
    ["mailto", false],
    ["spotify", false],
    ["unknown", false],
  ])("%s -> %s", (scheme, expected) => {
    expect(isAuthorityScheme({ scheme })).toBe(expected);
  });
});

describe("composeURL", () => {
  it.each([
    ["https", "example.com", "https://example.com"],
    ["mailto", "a@b.com", "mailto:a@b.com"],
    ["spotify", "//track/x", "spotify://track/x"],
    ["spotify", "track:x", "spotify:track:x"],
    ["https", "//example.com", "https://example.com"],
    ["https", "user:pass@host.com", "https://user:pass@host.com"],
    ["https", "localhost:3000", "https://localhost:3000"],
    ["ssh", "host:22", "ssh://host:22"],
    ["https", "", ""],
    ["https", "   ", ""],
    // Opaque selections keep a full-URL-looking payload instead of dropping
    // the selected scheme.
    ["mailto", "https://x", "mailto:https://x"],
    ["mailto", "foo://x", "mailto:foo://x"],
    ["spotify", "https://example.com/rss", "spotify:https://example.com/rss"],
    // Selected scheme outside the whitelist: text is returned trimmed.
    ["javascript", "alert(1)", "alert(1)"],
  ])("compose {%s, %j} -> %j", (scheme, text, expected) => {
    expect(composeURL({ scheme, text })).toBe(expected);
  });

  it.each([
    ["https", "http://x", "http://x"],
    ["https", "foo://x", "foo://x"],
    ["https", "javascript:alert(1)", "javascript:alert(1)"],
    ["https", "data:text/html,x", "data:text/html,x"],
    ["https", "  http://x ", "http://x"],
    ["https", "JavaScript:alert(1)", "JavaScript:alert(1)"],
    ["https", "  javascript:alert(1)", "javascript:alert(1)"],
    // Malformed whitelisted-scheme text is left for the server to reject.
    ["https", "https:/example.com", "https:/example.com"],
    ["https", "https:////x", "https:////x"],
  ])(
    "authority selection leaves text carrying its own scheme unchanged: {%s, %j}",
    (scheme, text, expected) => {
      expect(composeURL({ scheme, text })).toBe(expected);
    },
  );

  it.each(["javascript:alert(1)@x", "javascript:1"])(
    "never produces a text-leading unsupported scheme for %j under https",
    (text) => {
      const composed = composeURL({ scheme: "https", text });
      expect(composed.startsWith("https://")).toBe(true);
      expect(composed.startsWith("javascript:")).toBe(false);
    },
  );

  describe("round-trip over the whole mock whitelist", () => {
    const schemes = [...APP_CONFIG.constants.URL_SCHEMES];

    it.each(schemes)("%s survives split -> compose", (scheme) => {
      const authorityForm = `${scheme}://host/p?q=1`;
      const authoritySplit = splitScheme({ urlString: authorityForm });
      expect(authoritySplit).not.toBeNull();
      expect(
        composeURL({
          scheme: authoritySplit!.scheme,
          text: authoritySplit!.rest,
        }),
      ).toBe(authorityForm);

      // Opaque-style forms only split (and so round-trip) for opaque schemes;
      // an authority scheme without `//` yields null and is never stripped.
      const opaqueForms = [
        `${scheme}:opaque`,
        `${scheme}:https://example.com/rss`,
        `${scheme}:tel:123`,
      ];
      for (const original of opaqueForms) {
        const split = splitScheme({ urlString: original });
        if (isAuthorityScheme({ scheme })) {
          expect(split).toBeNull();
          continue;
        }
        expect(split).not.toBeNull();
        expect(composeURL({ scheme: split!.scheme, text: split!.rest })).toBe(
          original,
        );
      }
    });
  });
});

describe("hasUnsupportedSchemePrefix", () => {
  it.each(["foo:bar", "foo://x", "javascript:alert(1)", "data:text/html,x"])(
    "true for %j",
    (text) => {
      expect(hasUnsupportedSchemePrefix({ text })).toBe(true);
    },
  );

  it.each([
    "example.com",
    "localhost:8080",
    "example.com:8080/x",
    "user:pass@host.com",
    "https://x",
    "mailto:a@b",
    "",
  ])("false for %j", (text) => {
    expect(hasUnsupportedSchemePrefix({ text })).toBe(false);
  });
});

describe("isDevHostText", () => {
  it.each([
    "localhost",
    "localhost:8080/x",
    "127.0.0.1:5000",
    "0.0.0.0",
    "LOCALHOST:3000",
    "localhost/path",
    "localhost ",
  ])("true for %j", (text) => {
    expect(isDevHostText({ text })).toBe(true);
  });

  it.each(["localhostx.com", "example.com", "", "127x0x0x1"])(
    "false for %j",
    (text) => {
      expect(isDevHostText({ text })).toBe(false);
    },
  );
});
