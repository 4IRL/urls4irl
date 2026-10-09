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
