import {
  hideAndResetUpdateURLTitleForm,
  updateURLTitle,
} from "../update-title.js";
import { enableClickOnSelectedURLCardToHide } from "../selection.js";
import { ajaxCall } from "../../../../lib/ajax.js";
import { getState, setState, AppState } from "../../../../store/app-store.js";

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

    const chainable = {
      done: vi.fn().mockImplementation((cb) => {
        cb(response, "success", { status: 200 });
        return chainable;
      }),
      fail: vi.fn().mockReturnThis(),
      always: vi.fn().mockReturnThis(),
    };
    vi.mocked(ajaxCall).mockReturnValue(chainable as unknown as JQuery.jqXHR);

    await updateURLTitle(urlTitleInput, urlCard, 1);

    expect(setState).toHaveBeenCalled();
    const setStateArg = vi.mocked(setState).mock.calls[0][0];
    const updatedUrl = setStateArg.urls!.find(
      (existingUrl) => existingUrl.utubUrlID === 1,
    );
    expect(updatedUrl!.utubUrlTagIDs).toEqual([11, 22]);
  });
});
