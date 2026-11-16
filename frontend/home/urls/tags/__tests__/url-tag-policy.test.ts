import { createMockJqXHRChainable } from "../../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall } from "../../../../lib/ajax.js";
import { APP_CONFIG } from "../../../../lib/config.js";
import { handleTaggingRefusal } from "../../../tags/policy-banner.js";
import { isUtubLockedHandled } from "../../../utub-locked.js";
import { createURLTag } from "../create.js";
import { deleteURLTag } from "../delete.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../../../utub-locked.js", () => ({
  isUtubLockedHandled: vi.fn(() => false),
}));

vi.mock("../../../tags/policy-banner.js", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../tags/policy-banner.js")>()),
  handleTaggingRefusal: vi.fn(),
}));

vi.mock("../../cards/loading.js", () => ({
  setTimeoutAndShowURLCardLoadingIcon: vi.fn(() => 1),
  clearTimeoutIDAndHideLoadingIcon: vi.fn(),
}));

vi.mock("../../cards/get.js", () => ({
  getUpdatedURL: vi.fn(() => Promise.resolve()),
  handleRejectFromGetURL: vi.fn(),
}));

vi.mock("../../cards/selection.js", () => ({
  disableClickOnSelectedURLCardToHide: vi.fn(),
  enableClickOnSelectedURLCardToHide: vi.fn(),
}));

vi.mock("../../cards/utils.js", () => ({
  disableEditingURLString: vi.fn(),
  disableEditingURLTitle: vi.fn(),
  enableEditingURLString: vi.fn(),
  enableEditingURLTitle: vi.fn(),
}));

vi.mock("../../mobile.js", () => ({ isMobile: vi.fn(() => false) }));

vi.mock("../../../tags/utils.js", () => ({
  isTagInUTubTagDeck: vi.fn(() => false),
}));

vi.mock("../../../tags/tags.js", () => ({
  syncTagCapState: vi.fn(),
  buildTagFilterInDeck: vi.fn(() => window.jQuery("<div></div>")),
}));

vi.mock("../tags.js", () => ({
  createTagBadgeInURL: vi.fn(() => window.jQuery("<span></span>")),
  disableTagRemovalInURLCard: vi.fn(),
  enableTagRemovalInURLCard: vi.fn(),
  isTagInURL: vi.fn(() => true),
}));

vi.mock("../../cards/short-link-state.js", () => ({
  restoreShortLinkStatus: vi.fn(),
}));

vi.mock("../../cards/options/tag-btn.js", () => ({
  createAddTagIcon: vi.fn(() => window.jQuery("<i></i>")),
}));

vi.mock("../../cards/filtering.js", () => ({
  updateTagFilterCount: vi.fn(),
  TagCountOperation: { INCREMENT: "increment", DECREMENT: "decrement" },
  updateTagFilteringOnURLOrURLTagDeletion: vi.fn(),
}));

vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ urls: [], tags: [] })),
  setState: vi.fn(),
}));

// Keep the real plugins (offAndOnExact, hideClass) that hideAndResetCreateURLTagForm
// chains on; only the tabbable toggles are stubbed.
vi.mock("../../../../lib/jquery-plugins.js", async (importOriginal) => ({
  ...(await importOriginal<
    typeof import("../../../../lib/jquery-plugins.js")
  >()),
  enableTabbableChildElements: vi.fn(),
  disableTabbableChildElements: vi.fn(),
}));

vi.mock("../../../../lib/globals.js", async () => {
  const actual = await vi.importActual<
    typeof import("../../../../lib/globals.js")
  >("../../../../lib/globals.js");
  return {
    ...actual,
    bootstrap: {
      Tooltip: { getInstance: vi.fn(() => null) },
    } as unknown as typeof window.bootstrap,
  };
});

const $ = window.jQuery;
const UTUB_ID = 3;

const URL_CARD_HTML = `
  <div class="urlRow" utuburlid="1" urlSelected="true" data-utub-url-tag-ids="7">
    <div class="createUrlTagWrap"></div>
    <button class="urlTagBtnCreate cancel"></button>
    <input class="urlTagCreate" value="newtag" />
    <div class="urlTagCreate-error"></div>
    <div class="urlBtnAccess"></div>
    <div class="urlStringBtnUpdate"></div>
    <div class="urlBtnDelete"></div>
    <div class="urlBtnCopy"></div>
    <div class="urlTagsContainer"></div>
    <span class="tagBadge" data-utub-tag-id="7"></span>
  </div>
  <div id="unselectAllTagFilters"></div>
  <div id="listTags"></div>
  <div id="utubTagBtnUpdateAllOpen"></div>
`;

function failWith(responseJSON: Record<string, unknown>): void {
  const xhr = {
    status: 403,
    responseJSON,
    getResponseHeader: vi.fn(() => "application/json"),
  } as unknown as JQuery.jqXHR;
  vi.mocked(ajaxCall).mockReturnValue(
    createMockJqXHRChainable({
      fail: (callback: unknown) => (callback as (x: unknown) => void)(xhr),
    }),
  );
}

describe("urls/tags refusals — tagging not allowed (errorCode 4)", () => {
  let assignSpy: ReturnType<typeof vi.fn>;
  const originalLocation = window.location;

  beforeEach(() => {
    document.body.innerHTML = URL_CARD_HTML;
    vi.clearAllMocks();
    vi.mocked(isUtubLockedHandled).mockReturnValue(false);
    assignSpy = vi.fn();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...originalLocation, assign: assignSpy },
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: originalLocation,
    });
    document.body.innerHTML = "";
  });

  describe("createURLTagFail", () => {
    it("closes the form, then refuses via the shared handler with Add tag focus", async () => {
      failWith({ errorCode: 4 });
      const urlCard = $(".urlRow");

      await createURLTag($(".urlTagCreate"), urlCard, UTUB_ID);

      expect(urlCard.find(".createUrlTagWrap").hasClass("hidden")).toBe(true);
      const addTagButton = urlCard.find(".urlTagBtnCreate")[0];
      expect(handleTaggingRefusal).toHaveBeenCalledTimes(1);
      expect(handleTaggingRefusal).toHaveBeenCalledWith({
        message: APP_CONFIG.strings.TAG_URLS_NOT_ALLOWED,
        utubID: UTUB_ID,
        focusTarget: addTagButton,
        control: addTagButton,
      });
      expect(assignSpy).not.toHaveBeenCalled();
    });

    it("keeps the error-page redirect for another 403 code", async () => {
      failWith({ errorCode: 99 });

      await createURLTag($(".urlTagCreate"), $(".urlRow"), UTUB_ID);

      expect(handleTaggingRefusal).not.toHaveBeenCalled();
      expect(assignSpy).toHaveBeenCalledWith(APP_CONFIG.routes.errorPage);
    });
  });

  describe("deleteURLTagFail", () => {
    it("refuses with the remove message, keeps the badge and moves no focus", async () => {
      failWith({ errorCode: 4 });
      const urlCard = $(".urlRow");

      await deleteURLTag(7, urlCard.find(".tagBadge"), urlCard, UTUB_ID);

      expect(urlCard.find(".tagBadge").length).toBe(1);
      expect(handleTaggingRefusal).toHaveBeenCalledTimes(1);
      expect(handleTaggingRefusal).toHaveBeenCalledWith({
        message: APP_CONFIG.strings.TAG_REMOVE_NOT_ALLOWED,
        utubID: UTUB_ID,
      });
      expect(assignSpy).not.toHaveBeenCalled();
    });

    it("lets the locked-UTub handler win and skips the refusal", async () => {
      vi.mocked(isUtubLockedHandled).mockReturnValue(true);
      failWith({ errorCode: 8 });

      await deleteURLTag(7, $(".tagBadge"), $(".urlRow"), UTUB_ID);

      expect(handleTaggingRefusal).not.toHaveBeenCalled();
    });

    it("keeps the error-page redirect for another 403 code", async () => {
      failWith({ errorCode: 99 });

      await deleteURLTag(7, $(".tagBadge"), $(".urlRow"), UTUB_ID);

      expect(handleTaggingRefusal).not.toHaveBeenCalled();
      expect(assignSpy).toHaveBeenCalledWith(APP_CONFIG.routes.errorPage);
    });
  });
});
