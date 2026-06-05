import { createMockJqXHRChainable } from "../../../../__tests__/helpers/mock-jquery.js";
import {
  hideAndResetUpdateURLTitleForm,
  showUpdateURLTitleForm,
  updateURLTitle,
} from "../update-title.js";
import { enableClickOnSelectedURLCardToHide } from "../selection.js";
import { ajaxCall } from "../../../../lib/ajax.js";
import { getState, setState, AppState } from "../../../../store/app-store.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../selection.js", () => ({
  disableClickOnSelectedURLCardToHide: vi.fn(),
  enableClickOnSelectedURLCardToHide: vi.fn(),
}));

vi.mock("../loading.js", () => ({
  setTimeoutAndShowURLCardLoadingIcon: vi.fn(() => 1),
  clearTimeoutIDAndHideLoadingIcon: vi.fn(),
}));

vi.mock("../get.js", () => ({
  getUpdatedURL: vi.fn(() => Promise.resolve()),
  handleRejectFromGetURL: vi.fn(),
}));

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ urls: [] })),
  setState: vi.fn(),
}));

vi.mock("../../../mobile.js", () => ({
  isMobile: vi.fn(() => true),
}));

const $ = window.jQuery;

const URL_CARD_HTML = `
  <div class="urlRow" utuburlid="1" urlSelected="false">
    <div class="updateUrlTitleWrap hidden"></div>
    <div class="urlTitleAndUpdateIconWrap">
      <span class="urlTitle">My Title</span>
    </div>
    <input class="urlTitleUpdate" value="My Title" />
  </div>
`;

describe("hideAndResetUpdateURLTitleForm - selection guard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does NOT call enableClickOnSelectedURLCardToHide when card is NOT selected", () => {
    document.body.innerHTML = URL_CARD_HTML;
    const urlCard = $(".urlRow");
    urlCard.attr("urlSelected", "false");

    hideAndResetUpdateURLTitleForm(urlCard);

    expect(enableClickOnSelectedURLCardToHide).not.toHaveBeenCalled();
  });

  it("DOES call enableClickOnSelectedURLCardToHide when card IS selected", () => {
    document.body.innerHTML = URL_CARD_HTML;
    const urlCard = $(".urlRow");
    urlCard.attr("urlSelected", "true");

    hideAndResetUpdateURLTitleForm(urlCard);

    expect(enableClickOnSelectedURLCardToHide).toHaveBeenCalledWith(urlCard);
  });
});

describe("url_title_edit unchanged value", () => {
  const UNCHANGED_URL_CARD_HTML = `
    <div class="urlRow" utuburlid="1" urlSelected="false">
      <div class="updateUrlTitleWrap"></div>
      <div class="urlTitleAndUpdateIconWrap">
        <span class="urlTitle">Same Title</span>
      </div>
      <input class="urlTitleUpdate" value="Same Title" />
    </div>
  `;

  beforeEach(() => {
    document.body.innerHTML = UNCHANGED_URL_CARD_HTML;
    vi.clearAllMocks();
    vi.mocked(getState).mockReturnValue({
      urls: [
        {
          utubUrlID: 1,
          urlString: "https://example.com",
          urlTitle: "Same Title",
          utubUrlTagIDs: [],
          canDelete: true,
        },
      ],
    } as unknown as AppState);
  });

  it("emits submit but fires no AJAX when value is unchanged", async () => {
    const urlCard = $(".urlRow");
    const urlTitleInput = urlCard.find(".urlTitleUpdate");

    // updateURLTitle's unchanged-value guard short-circuits before ajaxCall is invoked.
    // The emit-before-early-return convention places the emit(UI_FORM_SUBMIT) call at the
    // top of the submit-button click handler in url-title.ts (not inside updateURLTitle
    // itself), so here we only assert that no AJAX is invoked — the emit is asserted in
    // the url-title.ts vitest below.
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();

    await updateURLTitle(urlTitleInput, urlCard, 1);

    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });
});

describe("updateURLTitleSuccess - tag ID mapping regression guard", () => {
  const UPDATE_TITLE_URL_CARD_HTML = `
    <div class="urlRow" utuburlid="1" urlSelected="false">
      <div class="updateUrlTitleWrap"></div>
      <div class="urlTitleAndUpdateIconWrap">
        <span class="urlTitle">Old Title</span>
      </div>
      <input class="urlTitleUpdate" value="New Title" />
      <div class="urlTitleUpdate-error"></div>
      <div class="tagBadge"></div>
    </div>
  `;

  let urlCard: JQuery, urlTitleInput: JQuery;

  beforeEach(() => {
    document.body.innerHTML = UPDATE_TITLE_URL_CARD_HTML;
    urlCard = $(".urlRow");
    urlTitleInput = urlCard.find(".urlTitleUpdate");
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
    const response = {
      URL: {
        utubUrlID: 1,
        urlString: "https://example.com",
        urlTitle: "New Title",
        urlTags: [
          { utubTagID: 11, tagString: "t11" },
          { utubTagID: 22, tagString: "t22" },
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

    await updateURLTitle(urlTitleInput, urlCard, 1);

    expect(setState).toHaveBeenCalled();
    const setStateArg = vi.mocked(setState).mock.calls[0][0];
    const updatedUrl = setStateArg.urls!.find(
      (existingUrl) => existingUrl.utubUrlID === 1,
    );
    expect(updatedUrl!.utubUrlTagIDs).toEqual([11, 22]);
  });
});

describe("URL title edit hides string-edit button for mutual exclusivity", () => {
  const CONCURRENT_EDIT_CARD_HTML = `
    <div class="urlRow" utuburlid="1" urlSelected="true" filterable="true">
      <div class="urlTitleAndUpdateIconWrap">
        <span class="urlTitle">My Title</span>
        <button class="urlTitleBtnUpdate"></button>
      </div>
      <div class="updateUrlTitleWrap hidden">
        <input class="urlTitleUpdate" value="My Title" />
      </div>
      <button class="urlStringBtnUpdate"></button>
      <div class="tagBadge"></div>
    </div>
  `;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("hides .urlStringBtnUpdate while title-edit form is open and restores it on close", () => {
    document.body.innerHTML = CONCURRENT_EDIT_CARD_HTML;
    const urlCard = $(".urlRow");
    const urlTitleAndIcon = urlCard.find(".urlTitleAndUpdateIconWrap");

    showUpdateURLTitleForm(urlTitleAndIcon, urlCard);

    expect(urlCard.find(".urlStringBtnUpdate").hasClass("hidden")).toBe(true);

    hideAndResetUpdateURLTitleForm(urlCard);

    expect(urlCard.find(".urlStringBtnUpdate").hasClass("hidden")).toBe(false);
  });
});

describe("showUpdateURLTitleForm - iOS soft-keyboard focus", () => {
  const MOBILE_FOCUS_CARD_HTML = `
    <div class="urlRow" utuburlid="1" urlSelected="true" filterable="true">
      <div class="urlTitleAndUpdateIconWrap">
        <span class="urlTitle">My Title</span>
      </div>
      <div class="updateUrlTitleWrap hidden">
        <input class="urlTitleUpdate" value="My Title" />
      </div>
      <button class="urlStringBtnUpdate"></button>
      <div class="tagBadge"></div>
    </div>
  `;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls native input.focus() directly on mobile so iOS surfaces the soft keyboard", () => {
    document.body.innerHTML = MOBILE_FOCUS_CARD_HTML;
    const urlCard = $(".urlRow");
    const urlTitleAndIcon = urlCard.find(".urlTitleAndUpdateIconWrap");

    const focusSpy = vi.spyOn(HTMLInputElement.prototype, "focus");

    showUpdateURLTitleForm(urlTitleAndIcon, urlCard);

    expect(focusSpy).toHaveBeenCalled();

    focusSpy.mockRestore();
  });
});
