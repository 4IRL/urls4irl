import {
  createMockJqXHR,
  createMockJqXHRChainable,
} from "../../../../__tests__/helpers/mock-jquery.js";
import { getUpdatedURL, handleRejectFromGetURL } from "../get.js";
import { APP_CONFIG } from "../../../../lib/config.js";
import {
  TRIM_FLUSH_KEY,
  TRIM_GET_KEY,
  TRIM_SUBMISSION_KEY,
  TRIM_SYNC_KEY,
  TrimMode,
  createParamTrimBlock,
} from "../../trim/param-trim-block.js";
import { ajaxCall, is429Handled } from "../../../../lib/ajax.js";
import {
  clearURLOutcomeBanner,
  showReviveBanner,
  showTrimSavedBanner,
  showURLUpdatedBanner,
} from "../../outcome-banner.js";
import { insertURLCardIntoDeck, removeURLCardFromDeck } from "../card-deck.js";
import { restoreTooltipIfStillTargeted } from "../../../../lib/tooltips.js";
import { checkForStaleDataOn409 } from "../conflict-handler.js";
import {
  updateURL,
  hideAndResetUpdateURLStringForm,
  isURLStringSubmitInFlight,
  showUpdateURLStringForm,
} from "../update-string.js";
import { showUpdateURLTitleForm } from "../update-title.js";
import { createURLStringAndUpdateBlock } from "../url-string.js";
import { createURLTitleAndUpdateBlock } from "../url-title.js";
import { enableClickOnSelectedURLCardToHide } from "../selection.js";
import { isCoarsePointer } from "../../../mobile.js";
import {
  openURLEditPanel,
  closeURLEditPanel,
  resetURLEditPanelState,
} from "../update-url-panel.js";
import { bindEditPanelDirtyState } from "../edit-panel-dirty.js";
import { getState, setState, AppState } from "../../../../store/app-store.js";
import { clearOpenForm, getOpenForm } from "../../../../lib/modal-tracking.js";
import { HOME_FORM } from "../../../../types/metrics-dim-values.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());

const { globalsMock } = await vi.hoisted(async () => {
  const { mockGlobalsWithTooltipInstance } =
    await import("../../../../__tests__/helpers/mock-globals.js");
  return await mockGlobalsWithTooltipInstance();
});

vi.mock("../../../../lib/globals.js", () => globalsMock);

// The restore-on-failure path delegates to lib/tooltips.js's
// restoreTooltipIfStillTargeted, which owns the still-targeted guard (`:hover`
// or `:focus-visible`) and the deferral
// past Bootstrap's fade (covered by lib/__tests__/tooltips.test.ts). Mock it
// here so these tests assert WHICH element each keep-open branch restores.
vi.mock("../../../../lib/tooltips.js", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../../lib/tooltips.js")>()),
  hideTooltip: vi.fn(),
  restoreTooltipIfStillTargeted: vi.fn(),
}));

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../loading.js", () => ({
  setTimeoutAndShowURLCardLoadingIcon: vi.fn(() => 1),
  clearTimeoutIDAndHideLoadingIcon: vi.fn(),
}));

vi.mock("../get.js", () => ({
  getUpdatedURL: vi.fn(() => Promise.resolve()),
  handleRejectFromGetURL: vi.fn(),
}));

vi.mock("../../outcome-banner.js", () => ({
  showTrimSavedBanner: vi.fn(),
  showURLUpdatedBanner: vi.fn(),
  showReviveBanner: vi.fn(),
  clearURLOutcomeBanner: vi.fn(),
}));

vi.mock("../selection.js", () => ({
  disableClickOnSelectedURLCardToHide: vi.fn(),
  enableClickOnSelectedURLCardToHide: vi.fn(),
  deselectAllURLs: vi.fn(),
}));

vi.mock("../card-deck.js", () => ({
  insertURLCardIntoDeck: vi.fn(() => window.jQuery("<div></div>")),
  removeURLCardFromDeck: vi.fn(),
}));

vi.mock("../../empty-state.js", () => ({
  hideURLsEmptyState: vi.fn(),
  showURLsEmptyState: vi.fn(),
}));

vi.mock("../options/edit-string-btn.js", () => ({
  createEditURLIcon: vi.fn(() => window.jQuery("<i></i>")),
  bindURLStringEditClickHandler: vi.fn(),
}));

vi.mock("../update-url-panel.js", () => ({
  openURLEditPanel: vi.fn(),
  closeURLEditPanel: vi.fn(),
  resetURLEditPanelState: vi.fn(),
}));

vi.mock("../../tags/tags.js", () => ({
  disableTagRemovalInURLCard: vi.fn(),
  enableTagRemovalInURLCard: vi.fn(),
}));

vi.mock("../../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  isCoarsePointer: vi.fn(() => false),
}));

// Partial mock: the real form factories (makeTextInput/makeSubmitButton/...) are
// needed to build the URL/title blocks whose real click guards are exercised.
vi.mock("../../../btns-forms.js", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../btns-forms.js")>()),
  highlightInput: vi.fn(),
}));

vi.mock("../conflict-handler.js", () => ({
  checkForStaleDataOn409: vi.fn(),
}));

vi.mock("../access.js", () => ({
  accessLink: vi.fn(),
}));

vi.mock("../copy.js", () => ({
  copyURLString: vi.fn(),
}));

vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ urls: [] })),
  setState: vi.fn(),
}));

const $ = window.jQuery;

const URL_CARD_HTML = `
  <div class="urlRow" utuburlid="1" urlSelected="false">
    <a class="urlString" href="https://example.com">https://example.com</a>
    <div class="updateUrlStringWrap">
      <input class="urlStringUpdate" value="https://example.com" />
      <div class="urlStringUpdate-error"></div>
    </div>
    <div class="urlCardDualLoadingRing"></div>
  </div>
`;

const HIDE_RESET_URL_CARD_HTML = `
  <div class="urlRow" utuburlid="1" urlSelected="false">
    <div class="updateUrlStringWrap hidden"></div>
    <a class="urlString" href="https://ex.com">https://ex.com</a>
    <input class="urlStringUpdate" value="https://ex.com" />
  </div>
`;

const CONCURRENT_EDIT_CARD_HTML = `<div class="urlRow" utuburlid="42" urlSelected="true" filterable="true">
    <a class="urlString" href="https://example.com">https://example.com</a>
    <div class="updateUrlStringWrap hidden"><input class="urlStringUpdate" type="text" value="https://example.com" /></div>
    <div class="updateUrlTitleWrap hidden"></div>
    <button class="urlStringBtnUpdate"></button>
    <button class="urlStringCancelBigBtnUpdate"></button>
    <button class="urlTitleBtnUpdate"></button>
    <button class="urlBtnAccess"></button>
    <button class="urlTagBtnCreate"></button>
    <button class="urlBtnDelete"></button>
    <button class="urlBtnCopy"></button>
    <span class="goToUrlIcon"></span>
</div>`;

describe("hideAndResetUpdateURLStringForm - selection guard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does NOT call enableClickOnSelectedURLCardToHide when card is NOT selected", () => {
    document.body.innerHTML = HIDE_RESET_URL_CARD_HTML;
    const urlCard = $(".urlRow");
    urlCard.attr("urlSelected", "false");

    hideAndResetUpdateURLStringForm({ urlCard });

    expect(enableClickOnSelectedURLCardToHide).not.toHaveBeenCalled();
  });

  it("DOES call enableClickOnSelectedURLCardToHide when card IS selected", () => {
    document.body.innerHTML = HIDE_RESET_URL_CARD_HTML;
    const urlCard = $(".urlRow");
    urlCard.attr("urlSelected", "true");

    hideAndResetUpdateURLStringForm({ urlCard });

    expect(enableClickOnSelectedURLCardToHide).toHaveBeenCalledWith(urlCard);
  });
});

describe("updateURL - client-side validation", () => {
  let urlCard: JQuery, urlStringInput: JQuery;

  beforeEach(() => {
    document.body.innerHTML = URL_CARD_HTML;
    urlCard = $(".urlRow");
    urlStringInput = urlCard.find(".urlStringUpdate");
    vi.clearAllMocks();
  });

  describe("invalid URL schemes are blocked before AJAX", () => {
    it.each([
      ["javascript:alert(1)"],
      ["data:text/html,<h1>x</h1>"],
      ["vbscript:msgbox('x')"],
    ])(
      "blocks '%s' and shows error without calling ajaxCall",
      async (invalidUrl) => {
        urlStringInput.val(invalidUrl);

        await updateURL(urlStringInput, urlCard, 1);

        expect(urlCard.find(".urlStringUpdate-error").hasClass("visible")).toBe(
          true,
        );
        expect(urlCard.find(".urlStringUpdate-error").text()).toBeTruthy();
        expect(urlCard.find(".urlStringUpdate").hasClass("invalid-field")).toBe(
          true,
        );
        expect(ajaxCall).not.toHaveBeenCalled();
      },
    );
  });
});

describe("updateURLSuccess - tag ID mapping regression guard", () => {
  let urlCard: JQuery, urlStringInput: JQuery;

  beforeEach(() => {
    document.body.innerHTML = URL_CARD_HTML;
    urlCard = $(".urlRow");
    urlStringInput = urlCard.find(".urlStringUpdate");
    vi.clearAllMocks();

    vi.mocked(getState).mockReturnValue({
      urls: [
        {
          utubUrlID: 1,
          urlString: "https://example.com",
          urlTitle: "Old Title",
          utubUrlTagIDs: [],
          canDelete: true,
        },
      ],
    } as unknown as AppState);
  });

  it("maps response.URL.urlTags via utubTagID (not legacy tagID) into setState", async () => {
    urlStringInput.val("https://new-example.com");

    const response = {
      URL: {
        utubUrlID: 1,
        urlString: "https://new-example.com",
        urlTitle: "New Title",
        urlTags: [
          { utubTagID: 10, tagString: "t10" },
          { utubTagID: 20, tagString: "t20" },
        ],
      },
    };

    const chainable = createMockJqXHRChainable({
      done: (cb: unknown) =>
        (cb as (...args: unknown[]) => void)(response, "success", {
          status: 200,
        }),
    });
    vi.mocked(ajaxCall).mockReturnValue(chainable);

    await updateURL(urlStringInput, urlCard, 1);

    expect(setState).toHaveBeenCalled();
    const setStateArg = vi.mocked(setState).mock.calls[0][0];
    const updatedUrl = setStateArg.urls!.find(
      (existingUrl) => existingUrl.utubUrlID === 1,
    );
    expect(updatedUrl!.utubUrlTagIDs).toEqual([10, 20]);
  });
});

describe("updateURLSuccess - revive on edit", () => {
  const EDITED_UTUB_URL_ID = 1;
  const REVIVED_UTUB_URL_ID = 55;
  const REVIVED_URL = "https://revived.example.com";
  const UTUB_ID = 7;
  let urlCard: JQuery, urlStringInput: JQuery;

  function revivedResponse({ lostTagCount }: { lostTagCount: number }) {
    return {
      status: "Success",
      revivedFromTrash: true,
      lostTagCount,
      replacedUtubUrlID: EDITED_UTUB_URL_ID,
      appliedTags: [{ id: 4, tagString: "kept", tagApplied: 1 }],
      URL: {
        utubUrlID: REVIVED_UTUB_URL_ID,
        urlString: REVIVED_URL,
        urlTitle: "Edited Title",
        urlTags: [
          { utubTagID: 4, tagString: "kept" },
          { utubTagID: 9, tagString: "trashed-only" },
        ],
      },
    };
  }

  function mockSuccess(response: unknown): void {
    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable({
        done: (cb: unknown) =>
          (cb as (...args: unknown[]) => void)(response, "success", {
            status: 200,
          }),
      }),
    );
  }

  beforeEach(() => {
    document.body.innerHTML = URL_CARD_HTML;
    urlCard = $(".urlRow");
    urlStringInput = urlCard.find(".urlStringUpdate");
    vi.clearAllMocks();
    vi.mocked(ajaxCall).mockReset();
    vi.mocked(is429Handled).mockReturnValue(false);
    vi.mocked(getState).mockReturnValue({
      urls: [
        {
          utubUrlID: EDITED_UTUB_URL_ID,
          urlString: "https://example.com",
          urlTitle: "Edited Title",
          utubUrlTagIDs: [],
          canDelete: true,
          addedAt: "2026-01-02T03:04:05",
          addedByUserID: 3,
        },
      ],
    } as unknown as AppState);
  });

  it("replaces the edited card with the revived one and shows the revive banner (no lost tags)", async () => {
    urlStringInput.val(REVIVED_URL);
    mockSuccess(revivedResponse({ lostTagCount: 0 }));

    await updateURL(urlStringInput, urlCard, UTUB_ID);

    expect(removeURLCardFromDeck).toHaveBeenCalledTimes(1);
    expect(removeURLCardFromDeck).toHaveBeenCalledWith({
      urlCard,
      utubUrlID: EDITED_UTUB_URL_ID,
      animate: false,
    });
    expect(insertURLCardIntoDeck).toHaveBeenCalledTimes(1);
    expect(insertURLCardIntoDeck).toHaveBeenCalledWith({
      newUrl: {
        utubUrlID: REVIVED_UTUB_URL_ID,
        urlString: REVIVED_URL,
        urlTitle: "Edited Title",
        utubUrlTagIDs: [4, 9],
        canDelete: true,
        addedAt: "2026-01-02T03:04:05",
        addedByUserID: 3,
      },
      utubID: UTUB_ID,
      appliedTags: [{ id: 4, tagString: "kept", tagApplied: 1 }],
      announce: false,
    });
    expect(showReviveBanner).toHaveBeenCalledTimes(1);
    expect(showReviveBanner).toHaveBeenCalledWith({
      lostTagCount: 0,
      utubUrlID: REVIVED_UTUB_URL_ID,
    });
    expect(showURLUpdatedBanner).not.toHaveBeenCalled();
    expect(showTrimSavedBanner).not.toHaveBeenCalled();
  });

  it("passes the lost tag count through to the revive banner", async () => {
    urlStringInput.val(REVIVED_URL);
    mockSuccess(revivedResponse({ lostTagCount: 2 }));

    await updateURL(urlStringInput, urlCard, UTUB_ID);

    expect(showReviveBanner).toHaveBeenCalledWith({
      lostTagCount: 2,
      utubUrlID: REVIVED_UTUB_URL_ID,
    });
  });

  it("treats an absent lostTagCount as 0 and still completes the swap", async () => {
    urlStringInput.val(REVIVED_URL);
    const response: Partial<ReturnType<typeof revivedResponse>> =
      revivedResponse({ lostTagCount: 5 });
    delete response.lostTagCount;
    mockSuccess(response);

    await updateURL(urlStringInput, urlCard, UTUB_ID);

    expect(removeURLCardFromDeck).toHaveBeenCalledTimes(1);
    expect(insertURLCardIntoDeck).toHaveBeenCalledTimes(1);
    expect(showReviveBanner).toHaveBeenCalledTimes(1);
    expect(showReviveBanner).toHaveBeenCalledWith({
      lostTagCount: 0,
      utubUrlID: REVIVED_UTUB_URL_ID,
    });
  });

  it("completes the swap with fallback adder fields when the edited card is missing from the store", async () => {
    urlStringInput.val(REVIVED_URL);
    vi.mocked(getState).mockReturnValue({
      urls: [],
    } as unknown as AppState);
    mockSuccess(revivedResponse({ lostTagCount: 1 }));

    await expect(
      updateURL(urlStringInput, urlCard, UTUB_ID),
    ).resolves.not.toThrow();

    expect(removeURLCardFromDeck).toHaveBeenCalledTimes(1);
    expect(insertURLCardIntoDeck).toHaveBeenCalledTimes(1);
    expect(insertURLCardIntoDeck).toHaveBeenCalledWith({
      newUrl: {
        utubUrlID: REVIVED_UTUB_URL_ID,
        urlString: REVIVED_URL,
        urlTitle: "Edited Title",
        utubUrlTagIDs: [4, 9],
        canDelete: true,
        addedAt: expect.any(String),
        addedByUserID: 0,
      },
      utubID: UTUB_ID,
      appliedTags: [{ id: 4, tagString: "kept", tagApplied: 1 }],
      announce: false,
    });
    expect(showReviveBanner).toHaveBeenCalledWith({
      lostTagCount: 1,
      utubUrlID: REVIVED_UTUB_URL_ID,
    });
  });

  it("tears down the edit panel and selection before swapping, and the banner comes last", async () => {
    urlStringInput.val(REVIVED_URL);
    mockSuccess(revivedResponse({ lostTagCount: 1 }));

    await updateURL(urlStringInput, urlCard, UTUB_ID);

    expect(resetURLEditPanelState).toHaveBeenCalledWith(urlCard);
    const resetOrder = vi.mocked(resetURLEditPanelState).mock
      .invocationCallOrder[0];
    const removeOrder = vi.mocked(removeURLCardFromDeck).mock
      .invocationCallOrder[0];
    const insertOrder = vi.mocked(insertURLCardIntoDeck).mock
      .invocationCallOrder[0];
    const bannerOrder = vi.mocked(showReviveBanner).mock.invocationCallOrder[0];
    expect(resetOrder).toBeLessThan(removeOrder);
    expect(removeOrder).toBeLessThan(insertOrder);
    expect(insertOrder).toBeLessThan(bannerOrder);
  });

  it("does not run the in-place update path (no store merge, no form reset)", async () => {
    urlStringInput.val(REVIVED_URL);
    mockSuccess(revivedResponse({ lostTagCount: 0 }));

    await updateURL(urlStringInput, urlCard, UTUB_ID);

    expect(setState).not.toHaveBeenCalled();
    expect(urlCard.find(".urlString").attr("href")).toBe("https://example.com");
  });

  it("folds the revive into the trim banner when query params were dropped", async () => {
    const trimUrl = "https://revived.example.com/p?a=1&b=2";
    document.body.innerHTML = `
      <div class="urlRow" utuburlid="1" urlSelected="true" filterable="true">
        <a class="urlString" href="${trimUrl}">${trimUrl}</a>
        <div class="updateUrlStringWrap hidden">
          <input class="urlStringUpdate" type="text" value="${trimUrl}" />
          <div class="urlStringUpdate-error"></div>
        </div>
        <div class="updateUrlTitleWrap hidden"></div>
        <button class="urlStringBtnUpdate"></button>
      </div>`;
    urlCard = $(".urlRow");
    urlStringInput = urlCard.find(".urlStringUpdate");
    const trimWrap = createParamTrimBlock({ mode: TrimMode.URL, urlCard });
    urlCard.find(".updateUrlStringWrap").append(trimWrap);
    (trimWrap.data(TRIM_FLUSH_KEY) as (rawValue: string) => void)(trimUrl);
    trimWrap.find('.urlParamTrimChip[data-index="0"]').trigger("click");
    mockSuccess(revivedResponse({ lostTagCount: 3 }));

    await updateURL(urlStringInput, urlCard, UTUB_ID);

    expect(showReviveBanner).not.toHaveBeenCalled();
    expect(showTrimSavedBanner).toHaveBeenCalledTimes(1);
    const args = vi.mocked(showTrimSavedBanner).mock.calls[0][0];
    expect(args.trimSubmission.droppedCount).toBe(1);
    expect(args.utubID).toBe(UTUB_ID);
    expect(args.utubUrlID).toBe(REVIVED_UTUB_URL_ID);
    expect(args.revive).toEqual({ lostTagCount: 3 });
  });

  it("keeps the edited card and shows the message in the edit form on a 400 at-tag-limit error", async () => {
    urlStringInput.val(REVIVED_URL);
    const xhr = {
      status: 400,
      responseJSON: {
        status: "Failure",
        message: "Reviving this URL would exceed the UTub's tag limit.",
      },
    } as unknown as JQuery.jqXHR;
    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable({
        fail: (cb: unknown) => (cb as (xhrArg: JQuery.jqXHR) => void)(xhr),
      }),
    );

    await updateURL(urlStringInput, urlCard, UTUB_ID);

    const errorElem = urlCard.find(".urlStringUpdate-error");
    expect(errorElem.hasClass("visible")).toBe(true);
    expect(errorElem.text()).toBe(
      "Reviving this URL would exceed the UTub's tag limit.",
    );
    expect(urlStringInput.hasClass("invalid-field")).toBe(true);
    expect(removeURLCardFromDeck).not.toHaveBeenCalled();
    expect(insertURLCardIntoDeck).not.toHaveBeenCalled();
    expect(showReviveBanner).not.toHaveBeenCalled();
    expect(urlCard.closest("body").length).toBe(1);
  });

  it("keeps the in-place path for a normal edit (revivedFromTrash false)", async () => {
    urlStringInput.val("https://plain-edit.example.com");
    mockSuccess({
      status: "Success",
      revivedFromTrash: false,
      lostTagCount: 0,
      replacedUtubUrlID: null,
      URL: {
        utubUrlID: EDITED_UTUB_URL_ID,
        urlString: "https://plain-edit.example.com",
        urlTitle: "Edited Title",
        urlTags: [],
      },
    });

    await updateURL(urlStringInput, urlCard, UTUB_ID);

    expect(removeURLCardFromDeck).not.toHaveBeenCalled();
    expect(insertURLCardIntoDeck).not.toHaveBeenCalled();
    expect(showReviveBanner).not.toHaveBeenCalled();
    expect(showURLUpdatedBanner).toHaveBeenCalledTimes(1);
    expect(setState).toHaveBeenCalled();
  });
});

describe("updateURL - 409 conflict delegates to checkForStaleDataOn409", () => {
  let urlCard: JQuery, urlStringInput: JQuery;

  beforeEach(() => {
    document.body.innerHTML = URL_CARD_HTML;
    urlCard = $(".urlRow");
    urlStringInput = urlCard.find(".urlStringUpdate");
    vi.clearAllMocks();
  });

  it("calls checkForStaleDataOn409 with utubID when ajaxCall fails with status 409", async () => {
    urlStringInput.val("https://duplicate.example.com");

    const responseJSON = {
      status: "Failure",
      message: "URL already in UTub",
      errorCode: null,
      errors: null,
      details: null,
      urlString: "https://duplicate.example.com",
    };
    const xhr = {
      status: 409,
      responseJSON,
    } as unknown as JQuery.jqXHR;

    const chainable = createMockJqXHRChainable({
      fail: (callback: unknown) =>
        (callback as (xhrArg: JQuery.jqXHR) => void)(xhr),
    });
    vi.mocked(ajaxCall).mockReturnValue(chainable);

    await updateURL(urlStringInput, urlCard, 99);

    expect(checkForStaleDataOn409).toHaveBeenCalledTimes(1);
    expect(checkForStaleDataOn409).toHaveBeenCalledWith(responseJSON, 99);
  });
});

describe("URL string edit keeps the title pencil visible (desktop full toggle)", () => {
  // Desktop full-toggle model: opening the string editor no longer HIDES the
  // title pencil — both triggers stay visible/hoverable at all times (the
  // sibling title wrap starts hidden/closed here, so no mutual close fires).
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("keeps .urlTitleBtnUpdate visible while the string-edit form is open (title pencil never vanishes)", () => {
    document.body.innerHTML = CONCURRENT_EDIT_CARD_HTML;
    const urlCard = $(".urlRow");
    const urlStringBtnUpdate = urlCard.find(".urlStringBtnUpdate");

    showUpdateURLStringForm({ urlCard, urlStringBtnUpdate });

    expect(urlCard.find(".urlTitleBtnUpdate").hasClass("hidden")).toBe(false);

    hideAndResetUpdateURLStringForm({ urlCard });

    expect(urlCard.find(".urlTitleBtnUpdate").hasClass("hidden")).toBe(false);
  });
});

describe("suppressSiblingDisable parameter (consolidated panel)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = CONCURRENT_EDIT_CARD_HTML;
  });

  it("does NOT hide the sibling title pencil when suppressSiblingDisable is true", () => {
    const urlCard = $(".urlRow");
    const urlStringBtnUpdate = urlCard.find(".urlStringBtnUpdate");

    showUpdateURLStringForm({
      urlCard,
      urlStringBtnUpdate,
      suppressSiblingDisable: true,
    });

    expect(urlCard.find(".urlTitleBtnUpdate").hasClass("hidden")).toBe(false);
  });

  it("keeps the sibling title pencil visible when suppressSiblingDisable is omitted (desktop full toggle — pencil never vanishes)", () => {
    const urlCard = $(".urlRow");
    const urlStringBtnUpdate = urlCard.find(".urlStringBtnUpdate");

    showUpdateURLStringForm({ urlCard, urlStringBtnUpdate });

    expect(urlCard.find(".urlTitleBtnUpdate").hasClass("hidden")).toBe(false);
  });

  it("does NOT re-enable the sibling title pencil on close when suppressSiblingDisable is true", () => {
    const urlCard = $(".urlRow");
    urlCard.find(".urlTitleBtnUpdate").addClass("hidden");

    hideAndResetUpdateURLStringForm({ urlCard, suppressSiblingDisable: true });

    expect(urlCard.find(".urlTitleBtnUpdate").hasClass("hidden")).toBe(true);
  });

  it("re-enables the sibling title pencil on close when suppressSiblingDisable is omitted", () => {
    const urlCard = $(".urlRow");
    urlCard.find(".urlTitleBtnUpdate").addClass("hidden");

    hideAndResetUpdateURLStringForm({ urlCard });

    expect(urlCard.find(".urlTitleBtnUpdate").hasClass("hidden")).toBe(false);
  });
});

describe("desktop full toggle — Title and URL editors are mutually exclusive (fine pointer)", () => {
  // Both editors present. Exactly one wrap is open per test so we can assert that
  // opening the closed one CLOSES the open sibling. isCoarsePointer() is false
  // (fine pointer / desktop), so suppressSiblingDisable is never set and the
  // mutual-close path runs.
  const STRING_OPEN_CARD_HTML = `
    <div class="urlRow" utuburlid="1" urlSelected="true" filterable="true">
      <div class="urlTitleAndUpdateIconWrap">
        <span class="urlTitle">My Title</span>
        <button class="urlTitleBtnUpdate hidden"></button>
      </div>
      <div class="updateUrlTitleWrap hidden">
        <input class="urlTitleUpdate" value="My Title" />
      </div>
      <a class="urlString hidden" href="https://example.com">https://example.com</a>
      <div class="updateUrlStringWrap">
        <input class="urlStringUpdate" type="text" value="https://example.com" />
        <div class="urlStringUpdate-error"></div>
      </div>
      <button class="urlStringCancelBigBtnUpdate">Cancel</button>
      <button class="urlBtnAccess hidden"></button>
      <button class="urlTagBtnCreate hidden"></button>
      <button class="urlBtnDelete hidden"></button>
      <button class="urlBtnCopy hidden"></button>
      <span class="goToUrlIcon hidden"></span>
      <div class="tagBadge"></div>
    </div>
  `;

  const TITLE_OPEN_CARD_HTML = `
    <div class="urlRow" utuburlid="1" urlSelected="true" filterable="true">
      <div class="urlTitleAndUpdateIconWrap hidden">
        <span class="urlTitle">My Title</span>
        <button class="urlTitleBtnUpdate"></button>
      </div>
      <div class="updateUrlTitleWrap">
        <input class="urlTitleUpdate" value="My Title" />
      </div>
      <a class="urlString" href="https://example.com">https://example.com</a>
      <div class="updateUrlStringWrap hidden">
        <input class="urlStringUpdate" type="text" value="https://example.com" />
        <div class="urlStringUpdate-error"></div>
      </div>
      <button class="urlStringBtnUpdate"></button>
      <button class="urlBtnAccess"></button>
      <button class="urlTagBtnCreate"></button>
      <button class="urlBtnDelete"></button>
      <button class="urlBtnCopy"></button>
      <span class="goToUrlIcon"></span>
      <div class="tagBadge"></div>
    </div>
  `;

  beforeEach(() => {
    vi.clearAllMocks();
    // Desktop / fine pointer — mutual exclusion is active.
    vi.mocked(isCoarsePointer).mockReturnValue(false);
  });

  it("(a) opening the Title editor closes an open URL-string editor, restores its option buttons, and leaves the edit-URL trigger visible", () => {
    document.body.innerHTML = STRING_OPEN_CARD_HTML;
    const urlCard = $(".urlRow");
    const urlTitleAndIcon = urlCard.find(".urlTitleAndUpdateIconWrap");

    // Precondition: string editor open, title editor closed.
    expect(urlCard.find(".updateUrlStringWrap").hasClass("hidden")).toBe(false);
    expect(urlCard.find(".updateUrlTitleWrap").hasClass("hidden")).toBe(true);

    showUpdateURLTitleForm({
      urlTitleAndShowUpdateIconWrap: urlTitleAndIcon,
      urlCard,
    });

    // String editor closed by the mutual-close; title editor now open.
    expect(urlCard.find(".updateUrlStringWrap").hasClass("hidden")).toBe(true);
    expect(urlCard.find(".updateUrlTitleWrap").hasClass("hidden")).toBe(false);
    // Option buttons restored (the string reset re-showed them).
    expect(urlCard.find(".urlBtnAccess").hasClass("hidden")).toBe(false);
    expect(urlCard.find(".urlBtnCopy").hasClass("hidden")).toBe(false);
    // Edit-URL trigger is present and visible (morphed back from the Cancel bar).
    expect(urlCard.find(".urlStringBtnUpdate").length).toBe(1);
    expect(urlCard.find(".urlStringBtnUpdate").hasClass("hidden")).toBe(false);
    // Never both open.
    const bothOpen =
      !urlCard.find(".updateUrlTitleWrap").hasClass("hidden") &&
      !urlCard.find(".updateUrlStringWrap").hasClass("hidden");
    expect(bothOpen).toBe(false);
  });

  it("(b) opening the URL-string editor closes an open Title editor and keeps the title pencil visible", () => {
    document.body.innerHTML = TITLE_OPEN_CARD_HTML;
    const urlCard = $(".urlRow");
    const urlStringBtnUpdate = urlCard.find(".urlStringBtnUpdate");

    // Precondition: title editor open, string editor closed.
    expect(urlCard.find(".updateUrlTitleWrap").hasClass("hidden")).toBe(false);
    expect(urlCard.find(".updateUrlStringWrap").hasClass("hidden")).toBe(true);

    showUpdateURLStringForm({ urlCard, urlStringBtnUpdate });

    // Title editor closed by the mutual-close; string editor now open.
    expect(urlCard.find(".updateUrlTitleWrap").hasClass("hidden")).toBe(true);
    expect(urlCard.find(".updateUrlStringWrap").hasClass("hidden")).toBe(false);
    // Title pencil restored/visible (enableEditingURLTitle ran on the title reset).
    expect(urlCard.find(".urlTitleBtnUpdate").hasClass("hidden")).toBe(false);
    // Never both open.
    const bothOpen =
      !urlCard.find(".updateUrlTitleWrap").hasClass("hidden") &&
      !urlCard.find(".updateUrlStringWrap").hasClass("hidden");
    expect(bothOpen).toBe(false);
  });

  it("(c) neither the string nor the title mutual-close fires on the mobile panel path (suppressSiblingDisable) — both stay open", () => {
    // Mobile keep-both-open guarantee: with suppressSiblingDisable the sibling is
    // NOT closed, so both editors remain open simultaneously.
    document.body.innerHTML = TITLE_OPEN_CARD_HTML;
    const urlCard = $(".urlRow");
    const urlStringBtnUpdate = urlCard.find(".urlStringBtnUpdate");

    showUpdateURLStringForm({
      urlCard,
      urlStringBtnUpdate,
      suppressSiblingDisable: true,
    });

    // Title editor is NOT closed by the sibling open (mobile keep-both-open).
    expect(urlCard.find(".updateUrlTitleWrap").hasClass("hidden")).toBe(false);
    expect(urlCard.find(".updateUrlStringWrap").hasClass("hidden")).toBe(false);
  });

  it("(d) the title-side mutual-close is suppressed on the mobile panel path (suppressSiblingDisable) — both stay open", () => {
    // Title-side mirror of (c): with suppressSiblingDisable the open URL-string
    // editor is NOT closed when the title editor opens, so both remain open
    // simultaneously. Covers the currently-unreachable title-side guard branch.
    document.body.innerHTML = STRING_OPEN_CARD_HTML;
    const urlCard = $(".urlRow");
    const urlTitleAndIcon = urlCard.find(".urlTitleAndUpdateIconWrap");

    showUpdateURLTitleForm({
      urlTitleAndShowUpdateIconWrap: urlTitleAndIcon,
      urlCard,
      suppressSiblingDisable: true,
    });

    // String editor is NOT closed by the sibling open (mobile keep-both-open).
    expect(urlCard.find(".updateUrlStringWrap").hasClass("hidden")).toBe(false);
    expect(urlCard.find(".updateUrlTitleWrap").hasClass("hidden")).toBe(false);
  });
});

describe("bindURLStringEditClickHandler - mobile vs desktop click target", () => {
  // The real helper lives in edit-string-btn.js (module-mocked above for
  // update-string.ts's own rebind call); pull the real implementation via
  // importActual so its isCoarsePointer() branch can be exercised end-to-end.
  const HELPER_CARD_HTML = `
    <div class="urlRow" utuburlid="1" urlSelected="true" filterable="true">
      <a class="urlString" href="https://example.com">https://example.com</a>
      <div class="updateUrlStringWrap hidden"><input class="urlStringUpdate" type="text" value="https://example.com" /></div>
      <button class="urlStringBtnUpdate"></button>
      <button class="urlTitleBtnUpdate"></button>
      <button class="urlBtnAccess"></button>
      <button class="urlTagBtnCreate"></button>
      <button class="urlBtnDelete"></button>
      <button class="urlBtnCopy"></button>
      <span class="goToUrlIcon"></span>
    </div>
  `;

  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = HELPER_CARD_HTML;
    // Restore the module default explicitly — each test sets its own pointer
    // type, but vi.clearAllMocks does not reset a prior mockReturnValue.
    vi.mocked(isCoarsePointer).mockReturnValue(false);
  });

  it("opens the consolidated panel (openURLEditPanel) on a coarse pointer", async () => {
    vi.mocked(isCoarsePointer).mockReturnValue(true);
    const { bindURLStringEditClickHandler } = await vi.importActual<
      typeof import("../options/edit-string-btn.js")
    >("../options/edit-string-btn.js");

    const urlCard = $(".urlRow");
    const urlStringBtnUpdate = urlCard.find(".urlStringBtnUpdate");
    bindURLStringEditClickHandler({ urlCard, urlStringBtnUpdate });

    urlStringBtnUpdate.trigger("click");

    expect(openURLEditPanel).toHaveBeenCalledWith(urlCard);
    // Desktop single-field open must NOT have run: the button never morphs.
    expect(urlCard.find(".urlStringCancelBigBtnUpdate").length).toBe(0);
  });

  it("opens only the string form (showUpdateURLStringForm) on a fine pointer", async () => {
    vi.mocked(isCoarsePointer).mockReturnValue(false);
    const { bindURLStringEditClickHandler } = await vi.importActual<
      typeof import("../options/edit-string-btn.js")
    >("../options/edit-string-btn.js");

    const urlCard = $(".urlRow");
    const urlStringBtnUpdate = urlCard.find(".urlStringBtnUpdate");
    bindURLStringEditClickHandler({ urlCard, urlStringBtnUpdate });

    urlStringBtnUpdate.trigger("click");

    expect(openURLEditPanel).not.toHaveBeenCalled();
    // Desktop path ran showUpdateURLStringForm, morphing the button to Cancel.
    expect(urlCard.find(".urlStringCancelBigBtnUpdate").text()).toBe("Cancel");
  });
});

describe("panel-aware submit gate — deselect + sibling suppression (mobile consolidated panel)", () => {
  // Card with BOTH edit forms present. The sibling title wrap is left OPEN (no
  // `hidden` class) so, on a coarse pointer, the panel-aware gate suppresses the
  // sibling restore. The title pencil starts hidden so we can assert it STAYS
  // hidden (i.e. enableEditingURLTitle did not fire).
  const PANEL_CARD_HTML = `
    <span class="visually-hidden" id="fieldSavedAnnouncement" aria-live="polite"></span>
    <div class="urlRow" utuburlid="1" urlSelected="true" filterable="true">
      <a class="urlString" href="https://example.com">https://example.com</a>
      <div class="updateUrlStringWrap">
        <input class="urlStringUpdate" type="text" value="https://example.com" />
        <button class="urlStringSubmitBtnUpdate"></button>
        <div class="field-saved-tick-slot"><span class="field-saved-tick opa-0" aria-hidden="true"></span></div>
      </div>
      <div class="updateUrlTitleWrap">
        <input class="urlTitleUpdate" value="My Title" />
        <div class="field-saved-tick-slot"><span class="field-saved-tick opa-0" aria-hidden="true"></span></div>
      </div>
      <button class="urlStringBtnUpdate"></button>
      <button class="urlStringCancelBigBtnUpdate"></button>
      <button class="urlTitleBtnUpdate hidden"></button>
      <button class="urlBtnAccess hidden"></button>
      <button class="urlTagBtnCreate hidden"></button>
      <button class="urlBtnDelete hidden"></button>
      <button class="urlBtnCopy hidden"></button>
      <span class="goToUrlIcon hidden"></span>
      <div class="urlStringUpdate-error"></div>
      <div class="urlCardDualLoadingRing"></div>
    </div>
  `;

  beforeEach(() => {
    document.body.innerHTML = PANEL_CARD_HTML;
    vi.clearAllMocks();
    // Coarse pointer = the mobile consolidated panel is in play.
    vi.mocked(isCoarsePointer).mockReturnValue(true);
  });

  it("value-unchanged skip: keeps the title pencil hidden AND does not re-arm the card deselect handler while the sibling form is open on mobile", async () => {
    const urlCard = $(".urlRow");
    // Input value already equals the href → value-unchanged skip path.
    const urlStringInput = urlCard.find(".urlStringUpdate");

    await updateURL(urlStringInput, urlCard, 1);

    // (a) sibling title pencil stays hidden — enableEditingURLTitle suppressed.
    expect(urlCard.find(".urlTitleBtnUpdate").hasClass("hidden")).toBe(true);
    // (b) card deselect handler is NOT re-armed.
    expect(enableClickOnSelectedURLCardToHide).not.toHaveBeenCalled();
  });

  it("success path: keeps the title pencil hidden AND does not re-arm the card deselect handler while the sibling form is open on mobile", async () => {
    const urlCard = $(".urlRow");
    const urlStringInput = urlCard.find(".urlStringUpdate");
    urlStringInput.val("https://new-example.com");

    const response = {
      URL: {
        utubUrlID: 1,
        urlString: "https://new-example.com",
        urlTitle: "My Title",
        urlTags: [],
      },
    };
    const chainable = createMockJqXHRChainable({
      done: (cb: unknown) =>
        (cb as (...args: unknown[]) => void)(response, "success", {
          status: 200,
        }),
    });
    vi.mocked(ajaxCall).mockReturnValue(chainable);

    await updateURL(urlStringInput, urlCard, 1);

    expect(urlCard.find(".urlTitleBtnUpdate").hasClass("hidden")).toBe(true);
    expect(enableClickOnSelectedURLCardToHide).not.toHaveBeenCalled();
  });

  it("companion — panel closed: performs the normal restore (re-arms deselect, restores the title pencil)", async () => {
    const urlCard = $(".urlRow");
    // Panel is CLOSED — the morphed Cancel bar is hidden (the authoritative
    // panel-open signal), so keepOpen is false and the normal restore runs even
    // on a coarse pointer. Sibling title form also closed so suppressSibling is
    // false too.
    urlCard.find(".urlStringCancelBigBtnUpdate").addClass("hidden");
    urlCard.find(".updateUrlTitleWrap").addClass("hidden");
    const urlStringInput = urlCard.find(".urlStringUpdate");

    await updateURL(urlStringInput, urlCard, 1);

    expect(urlCard.find(".urlTitleBtnUpdate").hasClass("hidden")).toBe(false);
    expect(enableClickOnSelectedURLCardToHide).toHaveBeenCalledWith(urlCard);
  });

  it("panel open: a real string change keeps the wrap open, keeps action buttons hidden, shows the tick, announces, and re-registers the open form", async () => {
    clearOpenForm();
    const urlCard = $(".urlRow");
    const urlStringInput = urlCard.find(".urlStringUpdate");
    urlStringInput.val("https://new-example.com");

    const response = {
      URL: {
        utubUrlID: 1,
        urlString: "https://new-example.com",
        urlTitle: "My Title",
        urlTags: [],
      },
    };
    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable({
        done: (cb: unknown) =>
          (cb as (...args: unknown[]) => void)(response, "success", {
            status: 200,
          }),
        always: (cb: unknown) => (cb as () => void)(),
      }),
    );

    await updateURL(urlStringInput, urlCard, 1);

    // Wrap stays open (keepOpen skipped the collapse).
    expect(urlCard.find(".updateUrlStringWrap").hasClass("hidden")).toBe(false);
    // Cancel bar preserved (panel-open signal intact — not morphed back).
    expect(
      urlCard.find(".urlStringCancelBigBtnUpdate").hasClass("hidden"),
    ).toBe(false);
    // Sibling action buttons stay hidden until the panel closes (keepOpen skips
    // the action-button restore) — the behavior the test name promises.
    expect(urlCard.find(".urlBtnAccess").hasClass("hidden")).toBe(true);
    expect(urlCard.find(".urlTagBtnCreate").hasClass("hidden")).toBe(true);
    expect(urlCard.find(".urlBtnDelete").hasClass("hidden")).toBe(true);
    expect(urlCard.find(".urlBtnCopy").hasClass("hidden")).toBe(true);
    expect(urlCard.find(".goToUrlIcon").hasClass("hidden")).toBe(true);
    // Saved✓ tick shown and shared announcer reflects the field label.
    expect(
      urlCard.find(".updateUrlStringWrap .field-saved-tick").hasClass("opa-1"),
    ).toBe(true);
    expect($("#fieldSavedAnnouncement").text()).toBe("URL Saved");
    expect(getOpenForm()).toBe(HOME_FORM.URL_STRING_EDIT);
  });

  it("panel open: marks the submit control aria-disabled while in flight and clears it (never native disabled) once settled", async () => {
    clearOpenForm();
    const urlCard = $(".urlRow");
    const submitBtn = urlCard.find(".urlStringSubmitBtnUpdate");
    const urlStringInput = urlCard.find(".urlStringUpdate");
    urlStringInput.val("https://new-example.com");

    const response = {
      URL: {
        utubUrlID: 1,
        urlString: "https://new-example.com",
        urlTitle: "My Title",
        urlTags: [],
      },
    };
    let inFlightAtRequest: boolean | undefined;
    let ariaAtRequest: string | undefined;
    vi.mocked(ajaxCall).mockImplementation(() => {
      inFlightAtRequest = isURLStringSubmitInFlight();
      ariaAtRequest = submitBtn.attr("aria-disabled");
      return createMockJqXHRChainable({
        done: (cb: unknown) =>
          (cb as (...args: unknown[]) => void)(response, "success", {
            status: 200,
          }),
        always: (cb: unknown) => (cb as () => void)(),
      });
    });

    await updateURL(urlStringInput, urlCard, 1);

    expect(inFlightAtRequest).toBe(true);
    expect(ariaAtRequest).toBe("true");
    expect(isURLStringSubmitInFlight()).toBe(false);
    expect(submitBtn.attr("aria-disabled")).toBeUndefined();
    expect(submitBtn.prop("disabled")).toBe(false);
  });

  it("fine pointer (desktop): a changed submit collapses the field with no tick", async () => {
    // Desktop: the consolidated panel is never in play, so isCardEditPanelOpen is
    // false and the field collapses on submit (no keep-open, no Saved✓ tick).
    vi.mocked(isCoarsePointer).mockReturnValue(false);
    const urlCard = $(".urlRow");
    const urlStringInput = urlCard.find(".urlStringUpdate");
    urlStringInput.val("https://new-example.com");

    const response = {
      URL: {
        utubUrlID: 1,
        urlString: "https://new-example.com",
        urlTitle: "My Title",
        urlTags: [],
      },
    };
    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable({
        done: (cb: unknown) =>
          (cb as (...args: unknown[]) => void)(response, "success", {
            status: 200,
          }),
        always: (cb: unknown) => (cb as () => void)(),
      }),
    );

    await updateURL(urlStringInput, urlCard, 1);

    // Field collapses (wrap hidden, URL re-shown) and no tick flashes.
    expect(urlCard.find(".updateUrlStringWrap").hasClass("hidden")).toBe(true);
    expect(
      urlCard.find(".updateUrlStringWrap .field-saved-tick").hasClass("opa-1"),
    ).toBe(false);
  });

  it("clears the in-flight guard on a genuine AJAX reject (.fail), never leaving a permanent aria-disabled lockout", async () => {
    const urlCard = $(".urlRow");
    const submitBtn = urlCard.find(".urlStringSubmitBtnUpdate");
    const urlStringInput = urlCard.find(".urlStringUpdate");
    urlStringInput.val("https://new-example.com");

    // Fire the true `.fail()` reject branch (status 0 → benign timeout-error
    // display, no navigation) and settle `.always()`.
    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable({
        fail: (cb: unknown) =>
          (cb as (xhr: JQuery.jqXHR) => void)({
            status: 0,
          } as unknown as JQuery.jqXHR),
        always: (cb: unknown) => (cb as () => void)(),
      }),
    );

    await updateURL(urlStringInput, urlCard, 1);

    expect(isURLStringSubmitInFlight()).toBe(false);
    expect(submitBtn.attr("aria-disabled")).toBeUndefined();
  });
});

describe("updateURL - restores the submit button tooltip on a keep-open failure", () => {
  const RESTORE_URL_CARD_HTML = `
  <div class="urlRow" utuburlid="1" urlSelected="false">
    <a class="urlString" href="https://example.com">https://example.com</a>
    <div class="updateUrlStringWrap">
      <input class="urlStringUpdate" value="https://example.com" />
      <div class="urlStringUpdate-error"></div>
      <button class="urlStringSubmitBtnUpdate"></button>
      <button class="urlStringCancelBtnUpdate"></button>
    </div>
    <div class="urlCardDualLoadingRing"></div>
  </div>
`;

  let urlCard: JQuery;
  let urlStringInput: JQuery;

  beforeEach(() => {
    document.body.innerHTML = RESTORE_URL_CARD_HTML;
    urlCard = $(".urlRow");
    urlStringInput = urlCard.find(".urlStringUpdate");
    urlStringInput.val("https://duplicate.example.com");
    vi.clearAllMocks();
    vi.mocked(is429Handled).mockReturnValue(false);
  });

  function mockFailure(status: number, responseJSON: unknown): void {
    const xhr = { status, responseJSON } as unknown as JQuery.jqXHR;
    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable({
        fail: (callback: unknown) =>
          (callback as (xhrArg: JQuery.jqXHR) => void)(xhr),
      }),
    );
  }

  it("restores this card's submit button on a 400 with field errors", async () => {
    mockFailure(400, { errors: { urlString: ["Invalid URL"] } });
    const submitBtn = urlCard.find(".urlStringSubmitBtnUpdate")[0];

    await updateURL(urlStringInput, urlCard, 99);

    expect(vi.mocked(restoreTooltipIfStillTargeted)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(restoreTooltipIfStillTargeted)).toHaveBeenCalledWith(
      submitBtn,
    );
  });

  it("restores the submit button on a 400 carrying only a message", async () => {
    mockFailure(400, { message: "URL already in UTub" });
    const submitBtn = urlCard.find(".urlStringSubmitBtnUpdate")[0];

    await updateURL(urlStringInput, urlCard, 99);

    expect(vi.mocked(restoreTooltipIfStillTargeted)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(restoreTooltipIfStillTargeted)).toHaveBeenCalledWith(
      submitBtn,
    );
  });

  it("restores the submit button on a 409 stale conflict", async () => {
    mockFailure(409, { message: "URL already in UTub" });
    const submitBtn = urlCard.find(".urlStringSubmitBtnUpdate")[0];

    await updateURL(urlStringInput, urlCard, 99);

    expect(checkForStaleDataOn409).toHaveBeenCalledTimes(1);
    expect(vi.mocked(restoreTooltipIfStillTargeted)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(restoreTooltipIfStillTargeted)).toHaveBeenCalledWith(
      submitBtn,
    );
  });

  it("does not attempt a restore when the failure is swallowed as a handled 429", async () => {
    // A rate-limited response is handled by its own banner and returns before
    // the keep-open branch, so no tooltip restore should be scheduled.
    mockFailure(400, { errors: { urlString: ["Invalid URL"] } });
    vi.mocked(is429Handled).mockReturnValue(true);

    await updateURL(urlStringInput, urlCard, 99);

    expect(vi.mocked(restoreTooltipIfStillTargeted)).not.toHaveBeenCalled();
  });
});

describe("query-parameter trim block in the edit-URL-string flow", () => {
  const TRIM_URL = "https://example.com/p?a=1&b=2&c=3";
  let urlCard: JQuery, urlStringInput: JQuery, trimWrap: JQuery;

  // Mirrors what createUpdateURLStringInput builds: the real block sits inside
  // .updateUrlStringWrap next to the input.
  function buildCard({ href }: { href: string }): void {
    document.body.innerHTML = `
      <div class="urlRow" utuburlid="1" urlSelected="true" filterable="true">
        <a class="urlString" href="${href}">${href}</a>
        <div class="updateUrlStringWrap hidden">
          <input class="urlStringUpdate" type="text" value="${href}" />
          <div class="urlStringUpdate-error"></div>
        </div>
        <div class="updateUrlTitleWrap hidden"></div>
        <button class="urlStringBtnUpdate"></button>
      </div>`;
    urlCard = $(".urlRow");
    urlStringInput = urlCard.find(".urlStringUpdate");
    trimWrap = createParamTrimBlock({ mode: TrimMode.URL, urlCard });
    urlCard.find(".updateUrlStringWrap").append(trimWrap);
  }

  function syncFromInput(value: string): void {
    urlStringInput.val(value);
    (trimWrap.data(TRIM_FLUSH_KEY) as (rawValue: string) => void)(value);
  }

  function dropChip(index: number): void {
    trimWrap.find(`.urlParamTrimChip[data-index="${index}"]`).trigger("click");
  }

  function mockSuccess(urlString: string, status?: string): void {
    const response = {
      ...(status === undefined ? {} : { status }),
      URL: {
        utubUrlID: 1,
        urlString,
        urlTitle: "t",
        urlTags: [],
      },
    };
    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable({
        done: (cb: unknown) =>
          (cb as (...args: unknown[]) => void)(response, "success", {
            status: 200,
          }),
      }),
    );
  }

  function mockConflict(): void {
    const xhr = {
      status: 409,
      responseJSON: { message: "URL already in UTub", urlString: TRIM_URL },
    } as unknown as JQuery.jqXHR;
    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable({
        fail: (cb: unknown) => (cb as (xhrArg: JQuery.jqXHR) => void)(xhr),
      }),
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(ajaxCall).mockReset();
    vi.useFakeTimers();
    vi.mocked(is429Handled).mockReturnValue(false);
    buildCard({ href: "https://example.com" });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the pre-filled value immediately on open, collapsed", () => {
    urlStringInput.val(TRIM_URL);

    showUpdateURLStringForm({
      urlCard,
      urlStringBtnUpdate: urlCard.find(".urlStringBtnUpdate"),
    });

    expect(trimWrap.hasClass("hidden")).toBe(false);
    expect(trimWrap.hasClass("collapsed")).toBe(true);
    expect(trimWrap.find(".urlParamTrimChip").length).toBe(3);
  });

  it("re-collapses and resets the block in place when the form is cancelled", () => {
    syncFromInput(TRIM_URL);
    trimWrap.find(".urlParamTrimHeader").trigger("click");
    dropChip(0);
    expect(trimWrap.hasClass("collapsed")).toBe(false);

    hideAndResetUpdateURLStringForm({ urlCard });

    expect(urlCard.find(".urlParamTrimWrap")[0]).toBe(trimWrap[0]);
    expect(trimWrap.hasClass("hidden")).toBe(true);
    expect(trimWrap.hasClass("collapsed")).toBe(true);
    expect(trimWrap.find(".urlParamTrimHeader").attr("aria-expanded")).toBe(
      "false",
    );
    const getSubmission = trimWrap.data(TRIM_SUBMISSION_KEY) as () => {
      droppedCount: number;
    };
    expect(getSubmission().droppedCount).toBe(0);
  });

  it("cancels a pending debounced re-parse on close", () => {
    const sync = trimWrap.data(TRIM_SYNC_KEY) as (rawValue: string) => void;
    sync(TRIM_URL);

    hideAndResetUpdateURLStringForm({ urlCard });
    vi.advanceTimersByTime(500);

    expect(trimWrap.hasClass("hidden")).toBe(true);
  });

  it("cancels a pending debounced re-parse on keepOpen close", () => {
    const sync = trimWrap.data(TRIM_SYNC_KEY) as (rawValue: string) => void;
    // Stored href has a different query than the stale pending value.
    urlCard.find(".urlString").attr("href", "https://example.com/p?z=1");
    sync(TRIM_URL);

    hideAndResetUpdateURLStringForm({ urlCard, keepOpen: true });
    vi.advanceTimersByTime(500);

    // Rendered from the resynced href (1 chip), not the stale pending value (3).
    expect(trimWrap.find(".urlParamTrimChip").length).toBe(1);
  });

  it("keepOpen retains the block and re-renders it from the resynced value", () => {
    urlCard.find(".urlString").attr("href", TRIM_URL);

    hideAndResetUpdateURLStringForm({ urlCard, keepOpen: true });

    expect(urlCard.find(".urlParamTrimWrap").length).toBe(1);
    expect(trimWrap.hasClass("hidden")).toBe(false);
    expect(trimWrap.hasClass("collapsed")).toBe(true);
  });

  it("submits the typed value byte-for-byte when nothing is dropped", async () => {
    syncFromInput("https://example.com/p?q=hello%20world&next=https://a.com/b");
    mockSuccess("https://example.com/p?q=hello%20world&next=https://a.com/b");

    await updateURL(urlStringInput, urlCard, 1);

    expect(vi.mocked(ajaxCall).mock.calls[0][2]).toEqual({
      urlString: "https://example.com/p?q=hello%20world&next=https://a.com/b",
    });
  });

  it("submits the URL with the dropped parameters removed", async () => {
    syncFromInput(TRIM_URL);
    dropChip(0);
    dropChip(2);
    mockSuccess("https://example.com/p?b=2");

    await updateURL(urlStringInput, urlCard, 1);

    expect(vi.mocked(ajaxCall).mock.calls[0][2]).toEqual({
      urlString: "https://example.com/p?b=2",
    });
  });

  it("trims against the current input when submitting inside the debounce window", async () => {
    syncFromInput("https://example.com/p?a=1&b=2");
    dropChip(0);
    // A further edit that has not been re-parsed yet (debounce pending).
    const newValue = "https://example.com/p?x=9&y=8";
    urlStringInput.val(newValue);
    (trimWrap.data(TRIM_SYNC_KEY) as (rawValue: string) => void)(newValue);
    mockSuccess(newValue);

    await updateURL(urlStringInput, urlCard, 1);

    // The flush re-parsed the new value (clearing the stale drop) before reading.
    expect(vi.mocked(ajaxCall).mock.calls[0][2]).toEqual({
      urlString: newValue,
    });
  });

  it("returns an unparseable value unchanged from the block rather than an empty string", () => {
    const bad = "http://";
    syncFromInput(bad);

    const getTrimmed = trimWrap.data(TRIM_GET_KEY) as () => string;
    expect(getTrimmed()).toBe(bad);
  });

  it("lets submit-time validation reject an invalid value the block passes through", async () => {
    syncFromInput("javascript:alert(1)");

    await updateURL(urlStringInput, urlCard, 1);

    expect(ajaxCall).not.toHaveBeenCalled();
    expect(urlCard.find(".urlStringUpdate-error").hasClass("visible")).toBe(
      true,
    );
  });

  it("stays a client-side no-op when the trimmed value equals the stored href", async () => {
    urlCard.find(".urlString").attr("href", "https://example.com/p?b=2");
    syncFromInput("https://example.com/p?a=1&b=2");
    dropChip(0);

    await updateURL(urlStringInput, urlCard, 1);

    expect(ajaxCall).not.toHaveBeenCalled();
  });

  it("keeps the section expanded when a further edit re-parses", () => {
    syncFromInput(TRIM_URL);
    trimWrap.find(".urlParamTrimHeader").trigger("click");

    syncFromInput("https://example.com/p?a=1&b=2");

    expect(trimWrap.hasClass("collapsed")).toBe(false);
    expect(trimWrap.find(".urlParamTrimHeader").attr("aria-expanded")).toBe(
      "true",
    );
  });

  it("substitutes the trim message and force-expands on a 409 after a drop", async () => {
    syncFromInput(TRIM_URL);
    dropChip(1);
    mockConflict();

    await updateURL(urlStringInput, urlCard, 99);

    expect(urlCard.find(".urlStringUpdate-error").text()).toBe(
      APP_CONFIG.strings.URL_TRIM_CONFLICT,
    );
    expect(trimWrap.hasClass("collapsed")).toBe(false);
    expect(trimWrap.find(".title-caret").hasClass("closed")).toBe(false);
    expect(trimWrap.find(".urlParamTrimHeader").attr("aria-expanded")).toBe(
      "true",
    );
  });

  it("shows the Undo banner with the untrimmed original after a trim-and-save", async () => {
    syncFromInput(TRIM_URL);
    dropChip(0);
    dropChip(2);
    mockSuccess("https://example.com/p?b=2");

    await updateURL(urlStringInput, urlCard, 7);

    expect(showTrimSavedBanner).toHaveBeenCalledTimes(1);
    const args = vi.mocked(showTrimSavedBanner).mock.calls[0][0];
    expect(args.trimSubmission).toEqual({
      originalUrlString: TRIM_URL,
      droppedSegments: ["a=1", "c=3"],
      droppedCount: 2,
    });
    expect(args.utubID).toBe(7);
    expect(args.utubUrlID).toBe(1);
    expect(args.form).toBe("url_string_edit");
    expect(args.urlCard[0]).toBe(urlCard[0]);
    // The trim banner replaces the plain one; both never show together.
    expect(showURLUpdatedBanner).not.toHaveBeenCalled();
  });

  it("shows the plain URL-updated banner, restoring the previous string, when nothing was dropped", async () => {
    const previous = urlCard.find(".urlString").attr("href");
    syncFromInput("https://example.com/p?a=1&b=2");
    mockSuccess("https://example.com/p?a=1&b=2");

    await updateURL(urlStringInput, urlCard, 7);

    expect(showTrimSavedBanner).not.toHaveBeenCalled();
    expect(showURLUpdatedBanner).toHaveBeenCalledTimes(1);
    const args = vi.mocked(showURLUpdatedBanner).mock.calls[0][0];
    expect(args.previousUrlString).toBe(previous);
    expect(args.utubID).toBe(7);
    expect(args.utubUrlID).toBe(1);
    expect(args.urlCard[0]).toBe(urlCard[0]);
  });

  it("captures the stored string from before the save, not the saved one", async () => {
    urlCard.find(".urlString").attr("href", "https://example.com/old");
    syncFromInput("https://example.com/new");
    mockSuccess("https://example.com/new");

    await updateURL(urlStringInput, urlCard, 1);

    expect(
      vi.mocked(showURLUpdatedBanner).mock.calls[0][0].previousUrlString,
    ).toBe("https://example.com/old");
  });

  it("shows no banner and clears a stale one when the server reports no change", async () => {
    syncFromInput("https://example.com/p?a=1&b=2");
    mockSuccess("https://example.com/p?a=1&b=2", "No change");

    await updateURL(urlStringInput, urlCard, 1);

    expect(showTrimSavedBanner).not.toHaveBeenCalled();
    expect(showURLUpdatedBanner).not.toHaveBeenCalled();
    expect(clearURLOutcomeBanner).toHaveBeenCalled();
  });

  it("shows no banner when the edit fails", async () => {
    syncFromInput("https://example.com/p?a=1&b=2");
    mockConflict();

    await updateURL(urlStringInput, urlCard, 99);

    expect(showTrimSavedBanner).not.toHaveBeenCalled();
    expect(showURLUpdatedBanner).not.toHaveBeenCalled();
  });

  it("shows no banner when the trim block is absent", async () => {
    trimWrap.remove();
    urlStringInput.val("https://example.com/p?a=1");
    mockSuccess("https://example.com/p?a=1");

    await updateURL(urlStringInput, urlCard, 1);

    expect(showTrimSavedBanner).not.toHaveBeenCalled();
  });

  it("keeps the server message and collapsed state on a 409 with nothing dropped", async () => {
    syncFromInput(TRIM_URL);
    mockConflict();

    await updateURL(urlStringInput, urlCard, 99);

    expect(urlCard.find(".urlStringUpdate-error").text()).toBe(
      "URL already in UTub",
    );
    expect(trimWrap.hasClass("collapsed")).toBe(true);
  });
});

describe('mobile edit panel "Save URL" button beside Close', () => {
  const CARD_HTML = `
    <div class="urlRow" utuburlid="1" urlSelected="true" filterable="true">
      <a class="urlString" href="https://example.com">https://example.com</a>
      <div class="updateUrlStringWrap hidden">
        <input class="urlStringUpdate" type="text" value="https://example.com" />
        <button class="urlStringSubmitBtnUpdate"></button>
        <div class="urlStringUpdate-error"></div>
      </div>
      <div class="urlOptions">
        <button class="urlStringBtnUpdate fourty-p-width"></button>
        <button class="urlBtnAccess"></button>
      </div>
    </div>
  `;

  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = CARD_HTML;
  });

  function openPanel(): JQuery {
    const urlCard = $(".urlRow");
    showUpdateURLStringForm({
      urlCard,
      urlStringBtnUpdate: urlCard.find(".urlStringBtnUpdate"),
    });
    return urlCard;
  }

  it("mounts a Save URL button right after the Close bar on a coarse pointer", () => {
    vi.mocked(isCoarsePointer).mockReturnValue(true);

    const urlCard = openPanel();

    const saveButton = urlCard.find(".urlStringSaveBigBtnUpdate");
    expect(saveButton.length).toBe(1);
    expect(saveButton.text()).toBe(APP_CONFIG.strings.URL_TRIM_SAVE_URL);
    expect(saveButton.attr("type")).toBe("button");
    expect(saveButton.prev().hasClass("urlStringCancelBigBtnUpdate")).toBe(
      true,
    );
  });

  it("clicking it clicks the URL field's own submit button (same save path)", () => {
    vi.mocked(isCoarsePointer).mockReturnValue(true);
    const urlCard = openPanel();
    const submitClick = vi.fn();
    urlCard.find(".urlStringSubmitBtnUpdate").on("click", submitClick);

    urlCard.find(".urlStringSaveBigBtnUpdate").trigger("click");

    expect(submitClick).toHaveBeenCalledTimes(1);
  });

  it("does not stack a second button when the panel is reopened", () => {
    vi.mocked(isCoarsePointer).mockReturnValue(true);
    const urlCard = openPanel();

    showUpdateURLStringForm({
      urlCard,
      urlStringBtnUpdate: urlCard.find(".urlStringCancelBigBtnUpdate"),
    });

    expect(urlCard.find(".urlStringSaveBigBtnUpdate").length).toBe(1);
  });

  it("removes it when the form closes", () => {
    vi.mocked(isCoarsePointer).mockReturnValue(true);
    const urlCard = openPanel();

    hideAndResetUpdateURLStringForm({ urlCard });

    expect(urlCard.find(".urlStringSaveBigBtnUpdate").length).toBe(0);
  });

  it("keeps it while the form stays open after a save (keepOpen)", () => {
    vi.mocked(isCoarsePointer).mockReturnValue(true);
    const urlCard = openPanel();

    hideAndResetUpdateURLStringForm({ urlCard, keepOpen: true });

    expect(urlCard.find(".urlStringSaveBigBtnUpdate").length).toBe(1);
  });

  it("is never mounted on a fine pointer (desktop has its own inline check and cancel)", () => {
    vi.mocked(isCoarsePointer).mockReturnValue(false);

    const urlCard = openPanel();

    expect(urlCard.find(".urlStringSaveBigBtnUpdate").length).toBe(0);
  });
});

describe("Save URL closes the panel after a successful save when the title is clean", () => {
  // Title and URL blocks come from the real url-title.ts / url-string.ts builders,
  // so the ✓ click handlers (and their disabled guards) are the production ones.
  const CARD_HTML = `
    <div class="urlRow" utuburlid="1" urlSelected="true" filterable="true">
      <div class="urlOptions">
        <button class="urlStringBtnUpdate fourty-p-width"></button>
      </div>
      <div class="urlCardDualLoadingRing"></div>
    </div>
  `;

  const SAVED_RESPONSE = {
    URL: {
      utubUrlID: 1,
      urlString: "https://new-example.com",
      urlTitle: "My Title",
      urlTags: [],
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = CARD_HTML;
    vi.mocked(isCoarsePointer).mockReturnValue(true);
  });

  // Builds the real title/URL blocks, opens the panel and binds the dirty state.
  function openPanel(): { urlCard: JQuery; urlInput: JQuery } {
    const urlCard = $(".urlRow");
    urlCard.append(createURLTitleAndUpdateBlock("My Title", urlCard, 1));
    urlCard.append(
      createURLStringAndUpdateBlock("https://example.com", urlCard, 1),
    );
    const urlInput = urlCard.find(".urlStringUpdate");
    showUpdateURLStringForm({
      urlCard,
      urlStringBtnUpdate: urlCard.find(".urlStringBtnUpdate"),
      suppressSiblingDisable: true,
    });
    bindEditPanelDirtyState(urlCard);
    return { urlCard, urlInput };
  }

  function mockSave({
    outcome,
    status = "Success",
    urlTitle = SAVED_RESPONSE.URL.urlTitle,
  }: {
    outcome: "done" | "fail";
    status?: string;
    urlTitle?: string;
  }): void {
    const response = {
      ...SAVED_RESPONSE,
      URL: { ...SAVED_RESPONSE.URL, urlTitle },
      status,
    };
    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable(
        outcome === "done"
          ? {
              done: (cb: unknown) =>
                (cb as (...args: unknown[]) => void)(response, "success", {
                  status: 200,
                }),
              always: (cb: unknown) => (cb as () => void)(),
            }
          : {
              fail: (cb: unknown) =>
                (cb as (xhr: JQuery.jqXHR) => void)({
                  status: 0,
                } as unknown as JQuery.jqXHR),
              always: (cb: unknown) => (cb as () => void)(),
            },
      ),
    );
  }

  async function flush(): Promise<void> {
    await new Promise((resolve) => setTimeout(resolve, 0));
  }

  it("closes the panel on a successful Save URL when the title has no unsaved edits", async () => {
    const { urlCard, urlInput } = openPanel();
    urlInput.val("https://new-example.com").trigger("input");
    mockSave({ outcome: "done" });

    urlCard.find(".urlStringSaveBigBtnUpdate").trigger("click");
    await flush();

    expect(closeURLEditPanel).toHaveBeenCalledTimes(1);
    expect(closeURLEditPanel).toHaveBeenCalledWith(urlCard);
  });

  it("keeps the panel open when the title has unsaved edits", async () => {
    const { urlCard, urlInput } = openPanel();
    urlCard.find(".urlTitleUpdate").val("Edited title").trigger("input");
    urlInput.val("https://new-example.com").trigger("input");
    mockSave({ outcome: "done" });

    urlCard.find(".urlStringSaveBigBtnUpdate").trigger("click");
    await flush();

    expect(closeURLEditPanel).not.toHaveBeenCalled();
  });

  it("does not close on a failed save and does not leak into a later check save", async () => {
    const { urlCard, urlInput } = openPanel();
    urlInput.val("https://new-example.com").trigger("input");
    mockSave({ outcome: "fail" });

    urlCard.find(".urlStringSaveBigBtnUpdate").trigger("click");
    await flush();
    expect(closeURLEditPanel).not.toHaveBeenCalled();

    // The same still-dirty field saved via the green check must never close.
    mockSave({ outcome: "done" });
    urlCard.find(".urlStringSubmitBtnUpdate").trigger("click");
    await flush();

    expect(closeURLEditPanel).not.toHaveBeenCalled();
  });

  it("does not close when the server reports no change", async () => {
    const { urlCard, urlInput } = openPanel();
    urlInput.val("https://new-example.com").trigger("input");
    mockSave({ outcome: "done", status: "No change" });

    urlCard.find(".urlStringSaveBigBtnUpdate").trigger("click");
    await flush();

    expect(closeURLEditPanel).not.toHaveBeenCalled();
  });

  it("is a no-op while the URL is unchanged: no request and no close", async () => {
    const { urlCard } = openPanel();

    urlCard.find(".urlStringSaveBigBtnUpdate").trigger("click");
    await flush();

    expect(ajaxCall).not.toHaveBeenCalled();
    expect(closeURLEditPanel).not.toHaveBeenCalled();
  });

  // The value is changed WITHOUT firing "input", so the dirty sync never runs and
  // the check stays aria-disabled: only the click handler's guard can stop the
  // request (an unchanged value alone would also skip it, masking a removed guard).
  it("a click on the aria-disabled URL check sends no request", async () => {
    const { urlCard, urlInput } = openPanel();
    const check = urlCard.find(".urlStringSubmitBtnUpdate");
    urlInput.val("https://new-example.com");
    mockSave({ outcome: "done" });
    expect(check.attr("aria-disabled")).toBe("true");

    check.trigger("click");
    await flush();

    expect(ajaxCall).not.toHaveBeenCalled();

    // Once the check is enabled the same click goes through.
    urlInput.trigger("input");
    check.trigger("click");
    await flush();
    expect(ajaxCall).toHaveBeenCalledTimes(1);
  });

  it("a click on the aria-disabled title check sends no request", async () => {
    const { urlCard } = openPanel();
    const check = urlCard.find(".urlTitleSubmitBtnUpdate");
    const titleInput = urlCard.find(".urlTitleUpdate");
    titleInput.val("Edited title");
    mockSave({ outcome: "done" });
    expect(check.attr("aria-disabled")).toBe("true");

    check.trigger("click");
    await flush();

    expect(ajaxCall).not.toHaveBeenCalled();

    // Once the check is enabled the same click goes through.
    titleInput.trigger("input");
    check.trigger("click");
    await flush();
    expect(ajaxCall).toHaveBeenCalledTimes(1);
  });

  it("a green check save never closes the panel", async () => {
    const { urlCard, urlInput } = openPanel();
    urlInput.val("https://new-example.com").trigger("input");
    mockSave({ outcome: "done" });

    urlCard.find(".urlStringSubmitBtnUpdate").trigger("click");
    await flush();

    expect(ajaxCall).toHaveBeenCalledTimes(1);
    expect(closeURLEditPanel).not.toHaveBeenCalled();
  });

  it("re-disables the check after a kept-open save and keeps it enabled after a failed save", async () => {
    const { urlCard, urlInput } = openPanel();
    const check = urlCard.find(".urlStringSubmitBtnUpdate");
    urlInput.val("https://new-example.com").trigger("input");
    expect(check.attr("aria-disabled")).toBeUndefined();

    mockSave({ outcome: "fail" });
    check.trigger("click");
    await flush();
    expect(check.attr("aria-disabled")).toBeUndefined();

    mockSave({ outcome: "done" });
    check.trigger("click");
    await flush();
    // Stored href now equals the input, so the field reads as unchanged again.
    expect(check.attr("aria-disabled")).toBe("true");
    expect(check.hasClass("unchanged")).toBe(true);
  });

  describe("title ✓ re-sync after a kept-open save", () => {
    it("re-disables the title check once the stored title catches up, and keeps it enabled after a failed save", async () => {
      const { urlCard } = openPanel();
      const check = urlCard.find(".urlTitleSubmitBtnUpdate");
      urlCard.find(".urlTitleUpdate").val("Edited title").trigger("input");
      expect(check.attr("aria-disabled")).toBeUndefined();

      mockSave({ outcome: "fail" });
      check.trigger("click");
      await flush();
      expect(ajaxCall).toHaveBeenCalledTimes(1);
      expect(check.attr("aria-disabled")).toBeUndefined();
      expect(check.hasClass("unchanged")).toBe(false);

      mockSave({ outcome: "done", urlTitle: "Edited title" });
      check.trigger("click");
      await flush();
      expect(ajaxCall).toHaveBeenCalledTimes(2);
      expect(urlCard.find(".urlTitle").text()).toBe("Edited title");
      expect(check.attr("aria-disabled")).toBe("true");
      expect(check.hasClass("unchanged")).toBe(true);
    });

    it("clears the in-flight state and re-syncs when the pre-flight fetch is rejected", async () => {
      const { urlCard } = openPanel();
      const check = urlCard.find(".urlTitleSubmitBtnUpdate");
      urlCard.find(".urlTitleUpdate").val("Edited title").trigger("input");
      vi.mocked(getUpdatedURL).mockRejectedValueOnce({ status: 404 });

      check.trigger("click");
      await flush();

      expect(ajaxCall).not.toHaveBeenCalled();
      expect(handleRejectFromGetURL).toHaveBeenCalledTimes(1);
      expect(check.attr("aria-disabled")).toBeUndefined();
      expect(check.hasClass("unchanged")).toBe(false);
    });
  });

  describe("Save URL branches", () => {
    // Keeps the PATCH pending so the test can act while the request is in flight.
    async function startPendingSave({
      urlCard,
      via,
    }: {
      urlCard: JQuery;
      via: "saveUrl" | "check";
    }): Promise<{ deferred: ReturnType<typeof createMockJqXHR> }> {
      // Returned inside an object: awaiting a bare jQuery Deferred would adopt it
      // as a thenable and hang until it settles.
      const deferred = createMockJqXHR();
      vi.mocked(ajaxCall).mockReturnValue(deferred);
      urlCard
        .find(
          via === "saveUrl"
            ? ".urlStringSaveBigBtnUpdate"
            : ".urlStringSubmitBtnUpdate",
        )
        .trigger("click");
      await flush();
      return { deferred };
    }

    function resolveSave(deferred: ReturnType<typeof createMockJqXHR>): void {
      deferred.resolve({ ...SAVED_RESPONSE, status: "Success" }, "success", {
        status: 200,
      });
    }

    it("a rejected pre-flight fetch sends no request, releases the in-flight guard and never closes", async () => {
      const { urlCard, urlInput } = openPanel();
      const check = urlCard.find(".urlStringSubmitBtnUpdate");
      urlInput.val("https://new-example.com").trigger("input");
      vi.mocked(getUpdatedURL).mockRejectedValueOnce({ status: 404 });

      urlCard.find(".urlStringSaveBigBtnUpdate").trigger("click");
      await flush();

      expect(ajaxCall).not.toHaveBeenCalled();
      expect(handleRejectFromGetURL).toHaveBeenCalledTimes(1);
      expect(isURLStringSubmitInFlight()).toBe(false);
      expect(check.attr("aria-disabled")).toBeUndefined();
      expect(closeURLEditPanel).not.toHaveBeenCalled();

      // The Save URL intent does not survive into a later ✓ save.
      mockSave({ outcome: "done" });
      check.trigger("click");
      await flush();
      expect(ajaxCall).toHaveBeenCalledTimes(1);
      expect(closeURLEditPanel).not.toHaveBeenCalled();
    });

    it("keeps the panel open when the title becomes dirty while the save is in flight", async () => {
      const { urlCard, urlInput } = openPanel();
      urlInput.val("https://new-example.com").trigger("input");
      const { deferred } = await startPendingSave({ urlCard, via: "saveUrl" });

      urlCard.find(".urlTitleUpdate").val("Typed meanwhile").trigger("input");
      resolveSave(deferred);
      await flush();

      expect(closeURLEditPanel).not.toHaveBeenCalled();
    });

    it("closes when the title stays clean while the save is in flight (control)", async () => {
      const { urlCard, urlInput } = openPanel();
      urlInput.val("https://new-example.com").trigger("input");
      const { deferred } = await startPendingSave({ urlCard, via: "saveUrl" });

      resolveSave(deferred);
      await flush();

      expect(closeURLEditPanel).toHaveBeenCalledTimes(1);
    });

    it("a Save URL click while a save is in flight sends no second request and does not close later", async () => {
      const { urlCard, urlInput } = openPanel();
      urlInput.val("https://new-example.com").trigger("input");
      const { deferred } = await startPendingSave({ urlCard, via: "check" });
      expect(ajaxCall).toHaveBeenCalledTimes(1);

      urlCard.find(".urlStringSaveBigBtnUpdate").trigger("click");
      await flush();
      expect(ajaxCall).toHaveBeenCalledTimes(1);

      resolveSave(deferred);
      await flush();
      // The blocked Save URL click must not leak into a later ✓ save either.
      urlInput.val("https://newer-example.com").trigger("input");
      mockSave({ outcome: "done" });
      urlCard.find(".urlStringSubmitBtnUpdate").trigger("click");
      await flush();

      expect(ajaxCall).toHaveBeenCalledTimes(2);
      expect(closeURLEditPanel).not.toHaveBeenCalled();
    });

    it("a Save URL click on an aria-disabled Save URL sends no request", async () => {
      const { urlCard, urlInput } = openPanel();
      const saveButton = urlCard.find(".urlStringSaveBigBtnUpdate");
      urlInput.val("https://new-example.com");
      expect(saveButton.attr("aria-disabled")).toBe("true");
      mockSave({ outcome: "done" });

      saveButton.trigger("click");
      await flush();

      expect(ajaxCall).not.toHaveBeenCalled();
      expect(closeURLEditPanel).not.toHaveBeenCalled();
    });

    it("does not close a panel that was closed while the save was in flight", async () => {
      const { urlCard, urlInput } = openPanel();
      urlInput.val("https://new-example.com").trigger("input");
      const { deferred } = await startPendingSave({ urlCard, via: "saveUrl" });

      hideAndResetUpdateURLStringForm({ urlCard });
      resolveSave(deferred);
      await flush();

      expect(closeURLEditPanel).not.toHaveBeenCalled();
    });
  });

  describe("Enter honors the same gate as the ✓ (mobile panel)", () => {
    function pressEnterInTitle(urlCard: JQuery): void {
      const input = urlCard.find(".urlTitleUpdate");
      input.trigger("blur").trigger("focus");
      input.trigger(
        $.Event("keydown", { key: "Enter", originalEvent: { repeat: false } }),
      );
    }

    function pressEnterInURL(urlCard: JQuery): void {
      urlCard.find(".urlStringUpdate").trigger("blur").trigger("focus");
      $(document).trigger($.Event("keyup", { key: "Enter" }));
    }

    afterEach(() => {
      $(document).off("keyup.updateURLStringFocus");
    });

    it("title: no request while the check is disabled, even with a silently changed value", async () => {
      const { urlCard } = openPanel();
      urlCard.find(".urlTitleUpdate").val("Silently edited");
      mockSave({ outcome: "done", urlTitle: "Silently edited" });
      expect(
        urlCard.find(".urlTitleSubmitBtnUpdate").attr("aria-disabled"),
      ).toBe("true");

      pressEnterInTitle(urlCard);
      await flush();

      expect(ajaxCall).not.toHaveBeenCalled();
    });

    it("title: saves when the check is enabled", async () => {
      const { urlCard } = openPanel();
      urlCard.find(".urlTitleUpdate").val("Edited title").trigger("input");
      mockSave({ outcome: "done", urlTitle: "Edited title" });

      pressEnterInTitle(urlCard);
      await flush();

      expect(ajaxCall).toHaveBeenCalledTimes(1);
    });

    it("URL: no request while the check is disabled, even with a silently changed value", async () => {
      const { urlCard, urlInput } = openPanel();
      urlInput.val("https://new-example.com");
      mockSave({ outcome: "done" });
      expect(
        urlCard.find(".urlStringSubmitBtnUpdate").attr("aria-disabled"),
      ).toBe("true");

      pressEnterInURL(urlCard);
      await flush();

      expect(ajaxCall).not.toHaveBeenCalled();
    });

    it("URL: saves when the check is enabled, without closing the panel", async () => {
      const { urlCard, urlInput } = openPanel();
      urlInput.val("https://new-example.com").trigger("input");
      mockSave({ outcome: "done" });

      pressEnterInURL(urlCard);
      await flush();

      expect(ajaxCall).toHaveBeenCalledTimes(1);
      expect(closeURLEditPanel).not.toHaveBeenCalled();
    });
  });
});
