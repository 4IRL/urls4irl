import { mountSchemeSelector } from "../scheme-selector.js";
import type { SchemeSelectorHandle } from "../scheme-selector.js";
import { handleSchemePrefixInput } from "../scheme-prefix-handler.js";

vi.mock("../../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  isCoarsePointer: vi.fn(() => false),
}));

const $ = window.jQuery;

describe("handleSchemePrefixInput", () => {
  let urlInput: JQuery<HTMLElement>;
  let handle: SchemeSelectorHandle;
  let onChange: ReturnType<typeof vi.fn<() => void>>;

  function type(value: string): void {
    urlInput.val(value);
    handleSchemePrefixInput({ input: urlInput, selector: handle, onChange });
  }

  beforeEach(() => {
    document.body.innerHTML = `
      <div class="text-input-container" id="inputContainer">
        <div class="text-input-inner-container">
          <input class="text-input" type="text" id="urlInput" />
        </div>
      </div>`;
    urlInput = $("#urlInput");
    onChange = vi.fn<() => void>();
    handle = mountSchemeSelector({
      inputContainer: $("#inputContainer"),
      urlInput,
      idPrefix: "test",
      onChange: vi.fn(),
    });
  });

  afterEach(() => {
    handle.destroy();
    document.body.innerHTML = "";
  });

  it("always calls onChange first", () => {
    type("example.com");

    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it("moves a typed scheme prefix into the selector as an explicit choice", () => {
    type("ssh://host/path");

    expect(urlInput.val()).toBe("host/path");
    expect(handle.getScheme()).toBe("ssh");
    expect(handle.isExplicit()).toBe(true);
  });

  it("splits an opaque scheme prefix", () => {
    type("mailto:a@b.com");

    expect(urlInput.val()).toBe("a@b.com");
    expect(handle.getScheme()).toBe("mailto");
    expect(handle.isExplicit()).toBe(true);
  });

  it("keeps a non-explicit selector on the default scheme for ordinary text", () => {
    type("example.com/path");

    expect(urlInput.val()).toBe("example.com/path");
    expect(handle.getScheme()).toBe("https");
    expect(handle.isExplicit()).toBe(false);
  });

  it("moves a non-explicit selector to http for a dev host", () => {
    type("localhost:8080/x");

    expect(handle.getScheme()).toBe("http");
    expect(handle.isExplicit()).toBe(false);
  });

  it("leaves an explicit choice alone when the text has no prefix", () => {
    handle.setScheme({ scheme: "ftp", explicit: true });

    type("localhost:8080/x");

    expect(handle.getScheme()).toBe("ftp");
    expect(handle.isExplicit()).toBe(true);
  });

  it("keeps a prefilled opaque edit intact when a keystroke follows", () => {
    handle.setScheme({ scheme: "feed", explicit: true });
    urlInput.val("https://example.com/rss");

    type("https://example.com/rssx");

    expect(urlInput.val()).toBe("https://example.com/rssx");
    expect(handle.getScheme()).toBe("feed");
    expect(handle.isExplicit()).toBe(true);
  });

  it("leaves a nested whitelisted scheme verbatim after an explicit opaque pick", () => {
    handle.setScheme({ scheme: "mailto", explicit: true });

    type("http://example.com");

    expect(urlInput.val()).toBe("http://example.com");
    expect(handle.getScheme()).toBe("mailto");
  });

  it("still splits a pasted prefix under an explicit authority scheme", () => {
    handle.setScheme({ scheme: "http", explicit: true });

    type("https://example.com");

    expect(urlInput.val()).toBe("example.com");
    expect(handle.getScheme()).toBe("https");
  });

  it("leaves text with an unsupported prefix untouched", () => {
    type("foo://x");

    expect(urlInput.val()).toBe("foo://x");
    expect(handle.isExplicit()).toBe(false);
  });
});
