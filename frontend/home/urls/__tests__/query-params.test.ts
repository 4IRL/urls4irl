import {
  parseQuerySegments,
  buildTrimmedUrl,
  isAutoStrippedParam,
  previewStoredUrl,
  type ParsedQuery,
} from "../query-params.js";

function parseOrFail(urlString: string): ParsedQuery {
  const parsed = parseQuerySegments(urlString);
  if (!parsed) throw new Error(`expected ${urlString} to parse`);
  return parsed;
}

function trim(urlString: string, dropped: number[]): string {
  return buildTrimmedUrl({
    original: urlString,
    parsed: parseOrFail(urlString),
    droppedIndexes: new Set(dropped),
  });
}

describe("parseQuerySegments", () => {
  describe("urls without a usable query", () => {
    it("reports no query and zero segments", () => {
      const parsed = parseOrFail("https://a.com/p");
      expect(parsed.hadQuery).toBe(false);
      expect(parsed.segments).toHaveLength(0);
    });

    it("reports a bare ? as hadQuery with zero segments", () => {
      const parsed = parseOrFail("https://a.com?");
      expect(parsed.hadQuery).toBe(true);
      expect(parsed.segments).toHaveLength(0);
    });

    it("returns null when the url cannot be parsed", () => {
      expect(parseQuerySegments("http://")).toBeNull();
      expect(parseQuerySegments("")).toBeNull();
    });
  });

  describe("segment splitting", () => {
    it("parses a single param", () => {
      const parsed = parseOrFail("https://a.com/p?x=1");
      expect(parsed.segments).toEqual([
        {
          index: 0,
          raw: "x=1",
          name: "x",
          isAutoStripped: false,
        },
      ]);
    });

    it("produces one segment per occurrence of a repeated key", () => {
      const parsed = parseOrFail("https://a.com/p?q=1&q=2");
      expect(parsed.segments.map((segment) => segment.index)).toEqual([0, 1]);
      expect(parsed.segments.map((segment) => segment.raw)).toEqual([
        "q=1",
        "q=2",
      ]);
    });

    it("keeps an empty value's raw text and name", () => {
      const [segment] = parseOrFail("https://a.com/p?a=").segments;
      expect(segment.raw).toBe("a=");
      expect(segment.name).toBe("a");
    });

    it("uses the whole segment as the name when there is no =", () => {
      const [first, second] = parseOrFail("https://a.com/p?a&b=1").segments;
      expect(first.name).toBe("a");
      expect(second.name).toBe("b");
    });

    it("preserves empty segments from a double ampersand", () => {
      const parsed = parseOrFail("https://a.com/p?a=1&&b=2");
      expect(parsed.segments.map((segment) => segment.raw)).toEqual([
        "a=1",
        "",
        "b=2",
      ]);
    });

    it("splits only on the first = so values keep later = signs", () => {
      const [segment] = parseOrFail("https://a.com/p?t=a=b").segments;
      expect(segment.name).toBe("t");
      expect(segment.raw).toBe("t=a=b");
    });

    it("defaults isAutoStripped to false", () => {
      const parsed = parseOrFail("https://a.com/p?utm_source=x&a=1");
      expect(parsed.segments.every((segment) => !segment.isAutoStripped)).toBe(
        true,
      );
    });
  });

  describe("byte-for-byte preservation", () => {
    it("keeps percent-encoding untouched", () => {
      const [segment] = parseOrFail("https://a.com/p?q=hello%20world").segments;
      expect(segment.raw).toBe("q=hello%20world");
    });

    it("keeps a literal :// inside a value", () => {
      const [segment] = parseOrFail(
        "https://a.com/p?next=https://a.com/b",
      ).segments;
      expect(segment.raw).toBe("next=https://a.com/b");
    });

    it("does not lowercase names", () => {
      const parsed = parseOrFail("https://a.com/p?Id=1&iD=2");
      expect(parsed.segments.map((segment) => segment.name)).toEqual([
        "Id",
        "iD",
      ]);
    });
  });

  describe("fragment, scheme and beforeQuery", () => {
    it("captures the fragment", () => {
      const parsed = parseOrFail("https://a.com/p?a=1#sec");
      expect(parsed.fragment).toBe("#sec");
      expect(parsed.segments).toHaveLength(1);
    });

    it("has an empty fragment when none exists", () => {
      expect(parseOrFail("https://a.com/p?a=1").fragment).toBe("");
    });

    it("treats a ? inside the fragment as part of the fragment", () => {
      const parsed = parseOrFail("https://a.com/p#frag?x=1");
      expect(parsed.hadQuery).toBe(false);
      expect(parsed.fragment).toBe("#frag?x=1");
    });

    it("carries scheme, host, port and path in beforeQuery", () => {
      const parsed = parseOrFail("https://a.com:8080/p/42?x=1&y=2");
      expect(parsed.beforeQuery).toBe("https://a.com:8080/p/42");
      expect(parsed.scheme).toBe("https");
    });

    it("keeps a mixed-case scheme and host as typed; scheme comes from the URL API", () => {
      const parsed = parseOrFail("HTTPS://A.com/Path?x=1");
      expect(parsed.scheme).toBe("https");
      expect(parsed.beforeQuery).toBe("HTTPS://A.com/Path");
    });

    it("leaves userinfo, dot-segments and spaces untouched", () => {
      expect(
        parseOrFail("https://user:pw@a.com/a/../b/./c?x=1").beforeQuery,
      ).toBe("https://user:pw@a.com/a/../b/./c");
      expect(parseOrFail("https://a.com/a b/c?x=1").beforeQuery).toBe(
        "https://a.com/a b/c",
      );
      expect(parseOrFail("https://a.com\\p?x=1").beforeQuery).toBe(
        "https://a.com\\p",
      );
    });

    it("stops beforeQuery at a # that precedes any ?", () => {
      expect(parseOrFail("https://a.com/p#frag?x=1").beforeQuery).toBe(
        "https://a.com/p",
      );
    });

    it("recognizes an uppercase scheme with no path as having a protocol", () => {
      const parsed = parseOrFail("HTTP://a.com?x=1");
      expect(parsed.scheme).toBe("http");
      expect(parsed.segments).toHaveLength(1);
    });

    it("prepends https when no protocol is present", () => {
      const parsed = parseOrFail("a.com/p?x=1");
      expect(parsed.scheme).toBe("https");
      expect(parsed.beforeQuery).toBe("https://a.com/p");
    });

    it("falls back to the textual prefix for non-special schemes", () => {
      const parsed = parseOrFail("mailto:a@b.com?subject=hi");
      expect(parsed.scheme).toBe("mailto");
      expect(parsed.beforeQuery).toBe("mailto:a@b.com");
    });
  });
});

describe("buildTrimmedUrl", () => {
  it("returns the original byte-for-byte when nothing is dropped", () => {
    const original = "https://a.com/p?q=hello%20world&next=https://a.com/b#s";
    expect(trim(original, [])).toBe(original);
  });

  it("returns a bare-? original unchanged when nothing is dropped", () => {
    expect(trim("https://a.com?", [])).toBe("https://a.com?");
  });

  it("re-emits userinfo, dot-segments and spaces untouched when dropping", () => {
    expect(trim("https://user:pw@a.com/a/../b c?x=1&y=2", [0])).toBe(
      "https://user:pw@a.com/a/../b c?y=2",
    );
  });

  it("keeps a typed mixed-case host and path when dropping", () => {
    expect(trim("HTTPS://A.com/Path?x=1&y=2", [1])).toBe(
      "HTTPS://A.com/Path?x=1",
    );
  });

  it("keeps the path when dropping a param (DD-17)", () => {
    expect(trim("https://a.com/p/42?x=1&y=2", [0])).toBe(
      "https://a.com/p/42?y=2",
    );
  });

  it("drops only the indexed occurrence of a repeated key", () => {
    expect(trim("https://a.com/p?q=1&q=2", [0])).toBe("https://a.com/p?q=2");
    expect(trim("https://a.com/p?q=1&q=2", [1])).toBe("https://a.com/p?q=1");
  });

  it("omits the ? when every segment is dropped", () => {
    expect(trim("https://a.com/p?x=1&y=2", [0, 1])).toBe("https://a.com/p");
  });

  it("preserves the fragment through every trim", () => {
    expect(trim("https://a.com/p?x=1&y=2#sec", [0])).toBe(
      "https://a.com/p?y=2#sec",
    );
    expect(trim("https://a.com/p?x=1#sec", [0])).toBe("https://a.com/p#sec");
  });

  it("does not re-serialize surviving segments", () => {
    expect(
      trim("https://a.com/p?drop=1&q=a%20b&next=https://x.com/y", [0]),
    ).toBe("https://a.com/p?q=a%20b&next=https://x.com/y");
  });

  it("keeps empty segments that survive", () => {
    expect(trim("https://a.com/p?a=1&&b=2", [0])).toBe("https://a.com/p?&b=2");
  });
});

describe("previewStoredUrl", () => {
  function previewWithAuto({
    original,
    autoIndexes,
    dropped,
  }: {
    original: string;
    autoIndexes: number[];
    dropped: number[];
  }): string {
    const parsed = parseOrFail(original);
    autoIndexes.forEach((autoIndex) => {
      parsed.segments[autoIndex].isAutoStripped = true;
    });
    return previewStoredUrl({
      original,
      parsed,
      droppedIndexes: new Set(dropped),
    });
  }

  it("returns the original when nothing is dropped or auto-stripped", () => {
    const original = "https://a.com/p?a=b%20c";
    expect(previewWithAuto({ original, autoIndexes: [], dropped: [] })).toBe(
      original,
    );
  });

  it("also removes auto-stripped segments", () => {
    expect(
      previewWithAuto({
        original: "https://a.com/p?utm_source=x&a=1&b=2",
        autoIndexes: [0],
        dropped: [2],
      }),
    ).toBe("https://a.com/p?a=1");
  });

  it("omits the ? when only auto-stripped segments existed", () => {
    expect(
      previewWithAuto({
        original: "https://a.com/p?gclid=1#s",
        autoIndexes: [0],
        dropped: [],
      }),
    ).toBe("https://a.com/p#s");
  });
});

describe("isAutoStrippedParam", () => {
  it("matches an exact blocklist name", () => {
    expect(isAutoStrippedParam({ name: "gclid", scheme: "https" })).toBe(true);
  });

  it("matches a prefix", () => {
    expect(isAutoStrippedParam({ name: "utm_source", scheme: "https" })).toBe(
      true,
    );
  });

  it("returns false for a non-tracking name", () => {
    expect(isAutoStrippedParam({ name: "ref", scheme: "https" })).toBe(false);
  });

  it("returns false for a non-web scheme even with a tracking name", () => {
    expect(isAutoStrippedParam({ name: "utm_source", scheme: "mailto" })).toBe(
      false,
    );
  });

  it("matches a percent-encoded name after decoding", () => {
    expect(isAutoStrippedParam({ name: "utm%5Fsource", scheme: "https" })).toBe(
      true,
    );
    expect(isAutoStrippedParam({ name: "%67clid", scheme: "https" })).toBe(
      true,
    );
  });

  it("decodes + to a space like the server, so utm+source is not utm_source", () => {
    expect(isAutoStrippedParam({ name: "utm+source", scheme: "https" })).toBe(
      false,
    );
    expect(isAutoStrippedParam({ name: "utm%2Bsource", scheme: "https" })).toBe(
      false,
    );
  });

  it("falls back to the raw name on a malformed escape instead of throwing", () => {
    expect(isAutoStrippedParam({ name: "100%", scheme: "https" })).toBe(false);
    expect(isAutoStrippedParam({ name: "utm_%zz", scheme: "https" })).toBe(
      true,
    );
  });

  it("matches the name case-insensitively", () => {
    expect(isAutoStrippedParam({ name: "UTM_SOURCE", scheme: "http" })).toBe(
      true,
    );
  });
});
