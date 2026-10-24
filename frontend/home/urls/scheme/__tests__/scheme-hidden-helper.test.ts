import { APP_CONFIG } from "../../../../lib/config.js";
import { getInputValue } from "../../../../lib/globals.js";
import { setState } from "../../../../store/app-store.js";
import {
  EMPTY_UTUB_SETTINGS,
  type ResolvedUtubSettings,
} from "../../../../types/settings.js";
import { isSchemeSelectorHidden } from "../scheme-default.js";
import { mountSchemeSelector } from "../scheme-selector.js";
import type { SchemeSelectorHandle } from "../scheme-selector.js";
import { handleSchemePrefixInput } from "../scheme-prefix-handler.js";
import { composeURL } from "../scheme-utils.js";
import {
  UPDATE_SCHEME_CONTAINER_SELECTOR,
  syncUpdateInputFromHref,
} from "../update-input-scheme.js";

vi.mock("../../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  isCoarsePointer: vi.fn(() => false),
}));

const $ = window.jQuery;

const HELPER = ".urlSchemeHelper";
const TOGGLE = ".urlSchemeToggle";
const ANNOUNCE = ".urlSchemeAnnounce";

function setUrlsSettings({ urls }: { urls: Record<string, unknown> }): void {
  setState({
    settings: {
      ...EMPTY_UTUB_SETTINGS,
      urls,
    } as unknown as ResolvedUtubSettings,
  });
}

function hideSelector({ scheme = "https" }: { scheme?: string } = {}): void {
  setUrlsSettings({
    urls: { default_url_scheme: scheme, hide_scheme_selector: true },
  });
}

function flushTimers(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

// Create-form shape: the selector mounts first, the prefix handler binds after
// it (production order), so the selector's own input listener runs first.
function createSetup(): {
  urlInput: JQuery<HTMLElement>;
  getHandle: () => SchemeSelectorHandle;
  type: (value: string) => void;
  remount: () => void;
} {
  document.body.innerHTML = `
    <div class="text-input-container" id="inputContainer">
      <div class="text-input-inner-container">
        <input class="text-input" type="text" id="urlInput"
               aria-describedby="existingId" />
      </div>
      <span class="text-input-error-message" id="urlInput-error"></span>
    </div>`;
  const urlInput = $("#urlInput");
  let handle: SchemeSelectorHandle;
  function mount(): void {
    handle = mountSchemeSelector({
      inputContainer: $("#inputContainer"),
      urlInput,
      idPrefix: "create",
      hidden: isSchemeSelectorHidden(),
      onChange: vi.fn(),
    });
    urlInput.off("input.test").on("input.test", () => {
      handleSchemePrefixInput({
        input: urlInput,
        selector: handle,
        onChange: vi.fn(),
      });
    });
  }
  mount();
  return {
    urlInput,
    getHandle: () => handle,
    type(value) {
      urlInput.val(value);
      urlInput.trigger("input");
    },
    remount: mount,
  };
}

function helperText(): string {
  return $(HELPER).text();
}

function describedBy(): string[] {
  return ($("#urlInput").attr("aria-describedby") ?? "")
    .split(/\s+/)
    .filter((token) => token !== "");
}

afterEach(() => {
  setState({ settings: null });
  document.body.innerHTML = "";
});

describe("hidden selector helper (create shape)", () => {
  it("hides the toggle with the .hidden class and marks the row", () => {
    hideSelector();
    createSetup();
    expect($(TOGGLE).hasClass("hidden")).toBe(true);
    expect($(TOGGLE).attr("hidden")).toBeUndefined();
    expect($(".urlSchemeInputRow").hasClass("urlSchemeHidden")).toBe(true);
    expect($(HELPER).length).toBe(1);
  });

  it("places the helper after the row and before the error element", () => {
    hideSelector();
    createSetup();
    const row = $(".urlSchemeInputRow");
    expect(row.next().is(HELPER)).toBe(true);
    expect($(HELPER).nextAll("#urlInput-error").length).toBe(1);
  });

  it("is described by the helper while it has text, keeping existing ids", () => {
    hideSelector();
    const { type } = createSetup();
    expect(describedBy()).toEqual(["existingId", "createSchemeHelper"]);
    type("foo://x");
    expect(helperText()).toBe("");
    expect(describedBy()).toEqual(["existingId"]);
    type("example.com");
    expect(describedBy()).toEqual(["existingId", "createSchemeHelper"]);
  });

  it("is a plain paragraph, not a live region", () => {
    hideSelector();
    createSetup();
    expect($(HELPER).is("p")).toBe(true);
    expect($(HELPER).attr("aria-live")).toBeUndefined();
  });

  it("shows no helper and no class when shown (default)", () => {
    createSetup();
    expect($(HELPER).length).toBe(0);
    expect($(TOGGLE).hasClass("hidden")).toBe(false);
    expect($(".urlSchemeInputRow").hasClass("urlSchemeHidden")).toBe(false);
    expect(describedBy()).toEqual(["existingId"]);
  });

  it("is not hidden when the default is not https", () => {
    setUrlsSettings({
      urls: { default_url_scheme: "ssh", hide_scheme_selector: true },
    });
    createSetup();
    expect($(HELPER).length).toBe(0);
  });

  it("names a bare host", () => {
    hideSelector();
    const { type } = createSetup();
    type("example.com");
    expect(helperText()).toBe("Will be saved as https://example.com");
    expect($(HELPER).find("strong").text()).toBe("https://");
  });

  it("reflects a stripped leading // and trimmed whitespace", () => {
    hideSelector();
    const { type } = createSetup();
    type("  //example.com ");
    expect(helperText()).toBe("Will be saved as https://example.com");
  });

  it("shows https://example.com after typing the scheme on https (unchanged scheme, text split)", () => {
    hideSelector();
    const { type, getHandle, urlInput } = createSetup();
    type("https://example.com");
    expect(getInputValue(urlInput)).toBe("example.com");
    expect(getHandle().getScheme()).toBe("https");
    expect(helperText()).toBe("Will be saved as https://example.com");
  });

  it("shows http:// for a dev host", () => {
    hideSelector();
    const { type } = createSetup();
    type("localhost:3000");
    expect(helperText()).toBe("Will be saved as http://localhost:3000");
  });

  it("follows a typed http:// prefix and submits it as is", () => {
    hideSelector();
    const { type, getHandle, urlInput } = createSetup();
    type("http://example.com");
    expect(helperText()).toBe("Will be saved as http://example.com");
    expect(
      composeURL({
        scheme: getHandle().getScheme(),
        text: getInputValue(urlInput),
      }),
    ).toBe("http://example.com");
  });

  it("follows a pasted mailto: and submits it as is", () => {
    hideSelector();
    const { type, getHandle, urlInput } = createSetup();
    type("mailto:x@y");
    expect(helperText()).toBe("Will be saved as mailto:x@y");
    expect(
      composeURL({
        scheme: getHandle().getScheme(),
        text: getInputValue(urlInput),
      }),
    ).toBe("mailto:x@y");
  });

  it("omits the Will-be-saved line for an unsupported scheme", () => {
    hideSelector();
    const { type } = createSetup();
    type("foo://x");
    expect(helperText()).toBe("");
    type("https:/example.com");
    expect(helperText()).toBe("");
  });

  it("shows the neutral line naming the scheme plus the hint for empty input only", () => {
    hideSelector();
    const { type } = createSetup();
    expect(helperText()).toBe(
      `${APP_CONFIG.strings.URL_SCHEME_HELPER_DEFAULT} https:// ${APP_CONFIG.strings.URL_SCHEME_HELPER_TYPE_HINT}`,
    );
    type("example.com");
    expect(helperText()).not.toContain(
      APP_CONFIG.strings.URL_SCHEME_HELPER_TYPE_HINT,
    );
  });

  it("builds the helper from text nodes, never markup", () => {
    hideSelector();
    const { type } = createSetup();
    type("<img src=x onerror=alert(1)>.com");
    expect($(HELPER).find("img").length).toBe(0);
    expect(helperText()).toContain("<img src=x onerror=alert(1)>.com");
  });
});

describe("hidden recovery", () => {
  it("restores the snapshotted default when the field is cleared", async () => {
    hideSelector();
    const { type, getHandle, urlInput } = createSetup();
    type("mailto:x@y");
    expect(getHandle().getScheme()).toBe("mailto");
    expect(getHandle().isExplicit()).toBe(true);

    type("");
    expect(getHandle().getScheme()).toBe("https");
    expect(getHandle().isExplicit()).toBe(false);
    expect(helperText()).toContain("https://");

    type("https://example.com");
    expect(getHandle().getScheme()).toBe("https");
    expect(getInputValue(urlInput)).toBe("example.com");
    expect(
      composeURL({
        scheme: getHandle().getScheme(),
        text: getInputValue(urlInput),
      }),
    ).toBe("https://example.com");
    await flushTimers();
  });

  it("announces the restored scheme only when it changed", async () => {
    hideSelector();
    const { type } = createSetup();
    type("mailto:x@y");
    await flushTimers();
    type("");
    await flushTimers();
    expect($(ANNOUNCE).text()).toBe("Scheme set to https");

    $(ANNOUNCE).text("");
    type("example.com");
    type("");
    await flushTimers();
    expect($(ANNOUNCE).text()).toBe("");
  });

  it("leaves a shown selector untouched when the field is cleared", () => {
    const { type, getHandle } = createSetup();
    type("mailto:x@y");
    type("");
    expect(getHandle().getScheme()).toBe("mailto");
    expect(getHandle().isExplicit()).toBe(true);
    getHandle().restoreDefaultScheme();
    expect(getHandle().getScheme()).toBe("mailto");
  });

  it("keeps mailto on a select-all paste that never passes through empty (documented limit)", () => {
    hideSelector();
    const { type, getHandle } = createSetup();
    type("mailto:x@y");
    type("https://example.com");
    expect(getHandle().getScheme()).toBe("mailto");
  });
});

describe("lifecycle", () => {
  it("leaves no helper or describedby token after destroy and a shown remount", () => {
    hideSelector();
    const { getHandle, remount } = createSetup();
    expect($(HELPER).length).toBe(1);
    getHandle().destroy();
    expect($(HELPER).length).toBe(0);
    expect(describedBy()).toEqual(["existingId"]);

    setUrlsSettings({ urls: {} });
    remount();
    expect($(HELPER).length).toBe(0);
    expect($("[id$='SchemeHelper']").length).toBe(0);
    expect(describedBy()).toEqual(["existingId"]);
  });

  it("keeps at most one helper id across a hidden remount", () => {
    hideSelector();
    const { remount } = createSetup();
    remount();
    expect($(HELPER).length).toBe(1);
    expect(
      describedBy().filter((token) => token === "createSchemeHelper"),
    ).toHaveLength(1);
  });

  it("stops re-rendering on input after destroy", () => {
    hideSelector();
    const { getHandle, urlInput } = createSetup();
    const detached = $(HELPER);
    getHandle().destroy();
    urlInput.val("example.com");
    urlInput.trigger("input");
    expect(detached.text()).not.toContain("example.com");
  });
});

describe("reset", () => {
  it("makes the helper follow reset()", () => {
    hideSelector();
    const { getHandle } = createSetup();
    getHandle().setScheme({ scheme: "http", explicit: true });
    expect(helperText()).toContain("http://");
    getHandle().reset();
    expect(helperText()).toContain("https://");
  });
});

// Edit shape: a card-like DOM with a stored href, the selector mounted over it
// and synced from the href exactly as mountUpdateSchemeSelector does.
describe("hidden selector on the edit shape", () => {
  let urlCard: JQuery<HTMLElement>;
  let handle: SchemeSelectorHandle;
  let urlInput: JQuery<HTMLElement>;

  function editSetup({ href }: { href: string }): void {
    document.body.innerHTML = `
      <div id="card">
        <a class="urlString" href="${href}"></a>
        <div class="updateUrlStringWrap">
          <div class="text-input-container">
            <div class="text-input-inner-container">
              <input class="text-input urlStringUpdate" type="text" />
            </div>
            <span class="text-input-error-message urlStringUpdate-error"></span>
          </div>
        </div>
      </div>`;
    urlCard = $("#card");
    urlInput = urlCard.find("input.urlStringUpdate");
    handle = mountSchemeSelector({
      inputContainer: urlCard.find(UPDATE_SCHEME_CONTAINER_SELECTOR),
      urlInput,
      idPrefix: "update-7",
      hidden: isSchemeSelectorHidden(),
      onChange: vi.fn(),
    });
    syncUpdateInputFromHref({ urlCard, selector: handle });
    handle.refreshHelper();
    urlInput.on("input", () => {
      handleSchemePrefixInput({
        input: urlInput,
        selector: handle,
        onChange: vi.fn(),
      });
    });
  }

  function typeEdit(value: string): void {
    urlInput.val(value);
    urlInput.trigger("input");
  }

  it("renders the stored non-default scheme right after mount and stays byte-identical", () => {
    hideSelector();
    editSetup({ href: "ftp://files.example.com/a" });
    expect($(HELPER).text()).toBe("Will be saved as ftp://files.example.com/a");
    expect(handle.getScheme()).toBe("ftp");
    expect(
      composeURL({ scheme: handle.getScheme(), text: getInputValue(urlInput) }),
    ).toBe("ftp://files.example.com/a");
  });

  it("types an https:// prefix on an https edit and splits it", () => {
    hideSelector();
    editSetup({ href: "https://old.example.com" });
    typeEdit("https://new.example.com");
    expect(getInputValue(urlInput)).toBe("new.example.com");
    expect($(HELPER).text()).toBe("Will be saved as https://new.example.com");
  });

  it("shows no helper line for a legacy href with no recognised scheme", () => {
    hideSelector();
    editSetup({ href: "foo://legacy" });
    expect($(HELPER).text()).toBe("");
    expect(urlInput.attr("aria-describedby") ?? "").not.toContain(
      "SchemeHelper",
    );
    expect(getInputValue(urlInput)).toBe("foo://legacy");
    expect(
      composeURL({ scheme: handle.getScheme(), text: getInputValue(urlInput) }),
    ).toBe("foo://legacy");
  });

  it("falls back to the default (not the stored scheme) when the field is cleared", () => {
    hideSelector();
    editSetup({ href: "ftp://x" });
    typeEdit("");
    expect(handle.getScheme()).toBe("https");
    expect($(HELPER).text()).toContain("https://");
    expect($(HELPER).text()).not.toContain("ftp://");
  });

  it("restores the pinned app default for a legacy edit, not the UTub default", () => {
    // The UTub default is https here, so the app default is the same value:
    // pin the check on the handle's own snapshot instead.
    hideSelector();
    editSetup({ href: "foo://legacy" });
    expect(handle.getDefaultScheme()).toBe(
      APP_CONFIG.constants.URL_DEFAULT_SCHEME,
    );
    handle.setScheme({ scheme: "mailto", explicit: true });
    typeEdit("");
    expect(handle.getScheme()).toBe(APP_CONFIG.constants.URL_DEFAULT_SCHEME);
  });

  it("leaves no helper behind after destroy and a shown remount", () => {
    hideSelector();
    editSetup({ href: "ftp://x" });
    handle.destroy();
    expect($(HELPER).length).toBe(0);
    expect(urlInput.attr("aria-describedby")).toBeUndefined();

    setUrlsSettings({ urls: {} });
    handle = mountSchemeSelector({
      inputContainer: urlCard.find(UPDATE_SCHEME_CONTAINER_SELECTOR),
      urlInput,
      idPrefix: "update-7",
      hidden: isSchemeSelectorHidden(),
      onChange: vi.fn(),
    });
    expect($(HELPER).length).toBe(0);
    expect(urlInput.attr("aria-describedby")).toBeUndefined();
  });
});
