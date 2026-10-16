import { isCoarsePointer } from "../../../mobile.js";
import {
  bindEditPanelDirtyState,
  isTitleDirty,
  isURLStringDirty,
  syncEditPanelDirtyState,
  unbindEditPanelDirtyState,
} from "../edit-panel-dirty.js";
import {
  TRIM_FLUSH_KEY,
  TRIM_RENDERED_EVENT,
  TrimMode,
  createParamTrimBlock,
} from "../../trim/param-trim-block.js";
import { isConfirmButtonDisabled } from "../../confirm-btn-state.js";
import {
  getSchemeSelector,
  mountSchemeSelector,
  type SchemeSelectorHandle,
} from "../../scheme/scheme-selector.js";
import { splitScheme } from "../../scheme/scheme-utils.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  isCoarsePointer: vi.fn(() => true),
}));

const $ = window.jQuery;

const STORED_URL = "https://example.com/page?keep=1&drop=2";

function mountCard(): JQuery {
  document.body.innerHTML = `
    <div class="urlRow" utuburlid="1">
      <h6 class="urlTitle">My Title</h6>
      <div class="updateUrlTitleWrap">
        <input class="urlTitleUpdate" value="My Title" />
        <button class="urlTitleSubmitBtnUpdate"></button>
      </div>
      <a class="urlString" href="${STORED_URL}">${STORED_URL}</a>
      <div class="updateUrlStringWrap">
        <input class="urlStringUpdate" value="${STORED_URL}" />
        <button class="urlStringSubmitBtnUpdate"></button>
      </div>
      <button class="urlStringSaveBigBtnUpdate"></button>
    </div>
  `;
  const urlCard = $(".urlRow");
  const trimWrap = createParamTrimBlock({ mode: TrimMode.URL, urlCard });
  urlCard.find(".updateUrlStringWrap").append(trimWrap);
  return urlCard;
}

function flushTrim({
  urlCard,
  rawValue,
}: {
  urlCard: JQuery;
  rawValue: string;
}): JQuery {
  const trimWrap = urlCard.find(".urlParamTrimWrap");
  (trimWrap.data(TRIM_FLUSH_KEY) as (value: string) => void)(rawValue);
  return trimWrap;
}

function buttons(urlCard: JQuery): {
  title: JQuery;
  url: JQuery;
  save: JQuery;
} {
  return {
    title: urlCard.find(".urlTitleSubmitBtnUpdate"),
    url: urlCard.find(".urlStringSubmitBtnUpdate"),
    save: urlCard.find(".urlStringSaveBigBtnUpdate"),
  };
}

describe("edit panel dirty state (mobile)", () => {
  beforeEach(() => {
    vi.mocked(isCoarsePointer).mockReturnValue(true);
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  describe("dirty definitions", () => {
    it("title: trimmed input vs stored text", () => {
      const urlCard = mountCard();
      const input = urlCard.find(".urlTitleUpdate");

      expect(isTitleDirty(urlCard)).toBe(false);
      input.val("  My Title  ");
      expect(isTitleDirty(urlCard)).toBe(false);
      input.val("Other");
      expect(isTitleDirty(urlCard)).toBe(true);
      input.val("My Title");
      expect(isTitleDirty(urlCard)).toBe(false);
    });

    it("url: trimmed input vs stored href", () => {
      const urlCard = mountCard();
      const input = urlCard.find(".urlStringUpdate");

      expect(isURLStringDirty(urlCard)).toBe(false);
      input.val(`  ${STORED_URL}  `);
      expect(isURLStringDirty(urlCard)).toBe(false);
      input.val("https://example.com/other");
      expect(isURLStringDirty(urlCard)).toBe(true);
    });

    it("url: dirty when the input carries an auto-stripped param", () => {
      const urlCard = mountCard();
      const autoUrl = "https://example.com/page?utm_source=x";
      urlCard.find(".urlString").attr("href", autoUrl);
      urlCard.find(".urlStringUpdate").val(autoUrl);

      flushTrim({ urlCard, rawValue: autoUrl });

      expect(isURLStringDirty(urlCard)).toBe(true);
    });

    it("url: a dropped chip makes it dirty even though the text is unchanged", () => {
      const urlCard = mountCard();
      const input = urlCard.find(".urlStringUpdate");
      const trimWrap = flushTrim({ urlCard, rawValue: STORED_URL });
      expect(isURLStringDirty(urlCard)).toBe(false);

      trimWrap.find('.urlParamTrimChip[data-index="1"]').trigger("click");

      expect(input.val()).toBe(STORED_URL);
      expect(isURLStringDirty(urlCard)).toBe(true);

      trimWrap.find('.urlParamTrimChip[data-index="1"]').trigger("click");
      expect(isURLStringDirty(urlCard)).toBe(false);
    });
  });

  describe("button state", () => {
    it("starts disabled on open with aria-disabled (never native disabled) and the unchanged class", () => {
      const urlCard = mountCard();

      bindEditPanelDirtyState(urlCard);

      const { title, url, save } = buttons(urlCard);
      [title, url, save].forEach((button) => {
        expect(button.attr("aria-disabled")).toBe("true");
        expect(button.hasClass("unchanged")).toBe(true);
        expect(button.prop("disabled")).toBe(false);
        expect(isConfirmButtonDisabled(button)).toBe(true);
      });
    });

    it("typing enables only the edited field's check, and reverting disables it again", () => {
      const urlCard = mountCard();
      bindEditPanelDirtyState(urlCard);
      const { title, url, save } = buttons(urlCard);

      urlCard.find(".urlTitleUpdate").val("New title").trigger("input");
      expect(title.attr("aria-disabled")).toBeUndefined();
      expect(title.hasClass("unchanged")).toBe(false);
      expect(url.attr("aria-disabled")).toBe("true");
      expect(save.attr("aria-disabled")).toBe("true");

      urlCard.find(".urlTitleUpdate").val("My Title").trigger("input");
      expect(title.attr("aria-disabled")).toBe("true");

      urlCard
        .find(".urlStringUpdate")
        .val("https://example.com/x")
        .trigger("input");
      expect(url.attr("aria-disabled")).toBeUndefined();
      expect(save.attr("aria-disabled")).toBeUndefined();
      expect(title.attr("aria-disabled")).toBe("true");

      urlCard.find(".urlStringUpdate").val(STORED_URL).trigger("input");
      expect(url.attr("aria-disabled")).toBe("true");
      expect(save.attr("aria-disabled")).toBe("true");
    });

    it("re-syncs on the trim block's render event (chip toggle)", () => {
      const urlCard = mountCard();
      const trimWrap = flushTrim({ urlCard, rawValue: STORED_URL });
      bindEditPanelDirtyState(urlCard);
      const { url, save } = buttons(urlCard);
      expect(url.attr("aria-disabled")).toBe("true");

      trimWrap.find('.urlParamTrimChip[data-index="0"]').trigger("click");

      expect(url.attr("aria-disabled")).toBeUndefined();
      expect(save.attr("aria-disabled")).toBeUndefined();
    });

    it("the trim block triggers a non-bubbling custom event on every render", () => {
      const urlCard = mountCard();
      const trimWrap = urlCard.find(".urlParamTrimWrap");
      const onWrap = vi.fn();
      const onCard = vi.fn();
      trimWrap.on(TRIM_RENDERED_EVENT, onWrap);
      urlCard.on(TRIM_RENDERED_EVENT, onCard);

      flushTrim({ urlCard, rawValue: STORED_URL });
      trimWrap.find('.urlParamTrimChip[data-index="0"]').trigger("click");

      expect(onWrap).toHaveBeenCalled();
      expect(onCard).not.toHaveBeenCalled();
    });

    it("keeps an in-flight aria-disabled on a dirty button untouched", () => {
      const urlCard = mountCard();
      bindEditPanelDirtyState(urlCard);
      const { url } = buttons(urlCard);
      urlCard
        .find(".urlStringUpdate")
        .val("https://example.com/x")
        .trigger("input");
      url.attr("aria-disabled", "true");

      syncEditPanelDirtyState(urlCard);

      expect(url.attr("aria-disabled")).toBe("true");
    });

    it("removes the state and stops reacting after unbind (panel close)", () => {
      const urlCard = mountCard();
      bindEditPanelDirtyState(urlCard);

      unbindEditPanelDirtyState(urlCard);

      const { title, url, save } = buttons(urlCard);
      [title, url, save].forEach((button) => {
        expect(button.attr("aria-disabled")).toBeUndefined();
        expect(button.hasClass("unchanged")).toBe(false);
      });
      urlCard
        .find(".urlStringUpdate")
        .val("https://example.com/x")
        .trigger("input");
      syncEditPanelDirtyState(urlCard);
      expect(url.attr("aria-disabled")).toBeUndefined();
    });
  });

  describe("scheme selector", () => {
    // Mounts the real selector the way showUpdateURLStringForm does: the input
    // holds the scheme-less rest and the selector holds the scheme.
    function mountCardWithSelector({ href }: { href: string }): {
      urlCard: JQuery;
      handle: SchemeSelectorHandle;
    } {
      const urlCard = mountCard();
      urlCard.find(".urlString").attr("href", href);
      urlCard.find(".updateUrlStringWrap").prepend(`
        <div class="text-input-container">
          <div class="text-input-inner-container">
            <input class="urlStringUpdate text-input" type="text" />
          </div>
        </div>`);
      urlCard.find("input.urlStringUpdate").not(".text-input").remove();
      const input = urlCard.find("input.urlStringUpdate");
      const handle = mountSchemeSelector({
        inputContainer: urlCard.find(".text-input-container"),
        urlInput: input,
        idPrefix: "dirty-test",
        onChange: () => input.trigger("input.editPanelDirty"),
      });
      const split = splitScheme({ urlString: href });
      if (split) {
        handle.setScheme({ scheme: split.scheme, explicit: true });
        input.val(split.rest);
      } else {
        input.val(href);
      }
      return { urlCard, handle };
    }

    afterEach(() => {
      getSchemeSelector({ container: $(".text-input-container") })?.destroy();
    });

    it("is not dirty on open for a split href", () => {
      const { urlCard } = mountCardWithSelector({
        href: "http://intranet.example.com/wiki",
      });

      expect(isURLStringDirty(urlCard)).toBe(false);
    });

    it("is not dirty on open for an opaque href (mailto:)", () => {
      const { urlCard } = mountCardWithSelector({ href: "mailto:a@b.com" });

      expect(urlCard.find("input.urlStringUpdate").val()).toBe("a@b.com");
      expect(isURLStringDirty(urlCard)).toBe(false);
    });

    it("is not dirty on open for an ssh:// href", () => {
      const { urlCard } = mountCardWithSelector({ href: "ssh://h/p" });

      expect(urlCard.find("input.urlStringUpdate").val()).toBe("h/p");
      expect(isURLStringDirty(urlCard)).toBe(false);
    });

    it("is not dirty with trim chips present, none dropped, and a split href", () => {
      const { urlCard } = mountCardWithSelector({ href: STORED_URL });
      const trimWrap = flushTrim({ urlCard, rawValue: STORED_URL });

      expect(trimWrap.find(".urlParamTrimChip").length).toBe(2);
      expect(urlCard.find("input.urlStringUpdate").val()).toBe(
        "example.com/page?keep=1&drop=2",
      );
      expect(isURLStringDirty(urlCard)).toBe(false);
    });

    it("is not dirty on open for a legacy unsupported href kept whole", () => {
      const { urlCard } = mountCardWithSelector({ href: "foo://x" });

      expect(isURLStringDirty(urlCard)).toBe(false);
    });

    it("is dirty after a scheme-only change and clean again when changed back", () => {
      const { urlCard, handle } = mountCardWithSelector({
        href: "http://intranet.example.com/wiki",
      });

      handle.setScheme({ scheme: "https", explicit: true });
      expect(isURLStringDirty(urlCard)).toBe(true);

      handle.setScheme({ scheme: "http", explicit: true });
      expect(isURLStringDirty(urlCard)).toBe(false);
    });

    it("un-dims all three confirm buttons on a scheme-only change", () => {
      const { urlCard, handle } = mountCardWithSelector({
        href: "http://intranet.example.com/wiki",
      });
      bindEditPanelDirtyState(urlCard);
      const { title, url, save } = buttons(urlCard);
      expect(url.attr("aria-disabled")).toBe("true");

      handle.setScheme({ scheme: "https", explicit: true });
      urlCard.find("input.urlStringUpdate").trigger("input");

      expect(url.attr("aria-disabled")).toBeUndefined();
      expect(save.attr("aria-disabled")).toBeUndefined();
      expect(title.attr("aria-disabled")).toBe("true");
    });

    it("re-dims when the scheme is changed back", () => {
      const { urlCard, handle } = mountCardWithSelector({
        href: "http://intranet.example.com/wiki",
      });
      bindEditPanelDirtyState(urlCard);
      const { url, save } = buttons(urlCard);

      handle.setScheme({ scheme: "https", explicit: true });
      urlCard.find("input.urlStringUpdate").trigger("input");
      handle.setScheme({ scheme: "http", explicit: true });
      urlCard.find("input.urlStringUpdate").trigger("input");

      expect(url.attr("aria-disabled")).toBe("true");
      expect(save.attr("aria-disabled")).toBe("true");
    });

    it("still reports a dropped chip as dirty with a split href", () => {
      const { urlCard } = mountCardWithSelector({
        href: "https://example.com/page?keep=1&drop=2",
      });
      const trimWrap = flushTrim({ urlCard, rawValue: STORED_URL });

      trimWrap.find('.urlParamTrimChip[data-index="1"]').trigger("click");

      expect(isURLStringDirty(urlCard)).toBe(true);
    });
  });

  describe("fine pointer (desktop)", () => {
    it("never binds or disables anything", () => {
      vi.mocked(isCoarsePointer).mockReturnValue(false);
      const urlCard = mountCard();

      bindEditPanelDirtyState(urlCard);
      syncEditPanelDirtyState(urlCard);

      const { title, url, save } = buttons(urlCard);
      [title, url, save].forEach((button) => {
        expect(button.attr("aria-disabled")).toBeUndefined();
        expect(button.hasClass("unchanged")).toBe(false);
      });
    });
  });
});
