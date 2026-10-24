import { setState } from "../../../../store/app-store.js";
import {
  EMPTY_UTUB_SETTINGS,
  type ResolvedUtubSettings,
} from "../../../../types/settings.js";
import {
  getEffectiveDefaultScheme,
  isSchemeSelectorHidden,
} from "../scheme-default.js";
import { mountSchemeSelector } from "../scheme-selector.js";
import type { SchemeSelectorHandle } from "../scheme-selector.js";
import { handleSchemePrefixInput } from "../scheme-prefix-handler.js";

vi.mock("../../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  isCoarsePointer: vi.fn(() => false),
}));

const $ = window.jQuery;

function setUrlsSettings({ urls }: { urls: Record<string, unknown> }): void {
  setState({
    settings: {
      ...EMPTY_UTUB_SETTINGS,
      urls,
    } as unknown as ResolvedUtubSettings,
  });
}

afterEach(() => {
  setState({ settings: null });
});

describe("getEffectiveDefaultScheme", () => {
  it("falls back to the app default when the slice is null", () => {
    setState({ settings: null });
    expect(getEffectiveDefaultScheme()).toBe("https");
  });

  it("falls back when the key is missing", () => {
    setUrlsSettings({ urls: {} });
    expect(getEffectiveDefaultScheme()).toBe("https");
  });

  it("returns a whitelisted stored default", () => {
    setUrlsSettings({ urls: { default_url_scheme: "ssh" } });
    expect(getEffectiveDefaultScheme()).toBe("ssh");
  });

  it.each(["gopher", "", 5, null])(
    "falls back for a stored default outside the whitelist: %j",
    (value) => {
      setUrlsSettings({ urls: { default_url_scheme: value } });
      expect(getEffectiveDefaultScheme()).toBe("https");
    },
  );
});

describe("isSchemeSelectorHidden", () => {
  it("is false for a null slice and a missing key", () => {
    setState({ settings: null });
    expect(isSchemeSelectorHidden()).toBe(false);
    setUrlsSettings({ urls: {} });
    expect(isSchemeSelectorHidden()).toBe(false);
  });

  it("is true only with hide true and an https default", () => {
    setUrlsSettings({
      urls: { default_url_scheme: "https", hide_scheme_selector: true },
    });
    expect(isSchemeSelectorHidden()).toBe(true);
  });

  it("is false with hide true and a non-https default", () => {
    setUrlsSettings({
      urls: { default_url_scheme: "ssh", hide_scheme_selector: true },
    });
    expect(isSchemeSelectorHidden()).toBe(false);
  });

  it("is false for a truthy non-true hide flag", () => {
    setUrlsSettings({
      urls: { default_url_scheme: "https", hide_scheme_selector: "true" },
    });
    expect(isSchemeSelectorHidden()).toBe(false);
  });
});

describe("selector and prefix handler with a UTub default", () => {
  let urlInput: JQuery<HTMLElement>;
  let handle: SchemeSelectorHandle;

  function mount(): void {
    handle = mountSchemeSelector({
      inputContainer: $("#inputContainer"),
      urlInput,
      idPrefix: "test",
      onChange: vi.fn(),
    });
  }

  function type(value: string): void {
    urlInput.val(value);
    handleSchemePrefixInput({
      input: urlInput,
      selector: handle,
      onChange: vi.fn(),
    });
  }

  beforeEach(() => {
    document.body.innerHTML = `
      <div class="text-input-container" id="inputContainer">
        <div class="text-input-inner-container">
          <input class="text-input" type="text" id="urlInput" />
        </div>
      </div>`;
    urlInput = $("#urlInput");
  });

  afterEach(() => {
    handle.destroy();
    document.body.innerHTML = "";
  });

  it("starts a newly mounted selector on the UTub default", () => {
    setUrlsSettings({ urls: { default_url_scheme: "ssh" } });
    mount();
    expect(handle.getScheme()).toBe("ssh");
    expect(handle.getDefaultScheme()).toBe("ssh");
    expect(handle.isExplicit()).toBe(false);
    expect($(".urlSchemeToggle").text()).toContain("ssh");
  });

  it("keeps the dev host on http whatever the UTub default", () => {
    setUrlsSettings({ urls: { default_url_scheme: "mailto" } });
    mount();
    type("localhost:3000");
    expect(handle.getScheme()).toBe("http");
    type("example.com");
    expect(handle.getScheme()).toBe("mailto");
  });

  it("does not change an open selector or its prefix handler when the store changes", () => {
    mount();
    setUrlsSettings({ urls: { default_url_scheme: "ssh" } });
    expect(handle.getScheme()).toBe("https");
    type("example.com");
    expect(handle.getScheme()).toBe("https");
    expect(handle.getDefaultScheme()).toBe("https");
  });

  it("re-snapshots on reset", () => {
    mount();
    setUrlsSettings({ urls: { default_url_scheme: "ssh" } });
    expect(handle.getScheme()).toBe("https");

    handle.reset();
    expect(handle.getScheme()).toBe("ssh");
    expect(handle.getDefaultScheme()).toBe("ssh");

    type("example.com");
    expect(handle.getScheme()).toBe("ssh");
  });
});
