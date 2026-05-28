import { showUpdateURLTitleForm } from "../update-title.js";

vi.mock("../../../../lib/metrics-client.js", () => ({
  emit: vi.fn(),
  flush: vi.fn().mockResolvedValue(undefined),
  initMetricsClient: vi.fn(),
  resetMetricsClient: vi.fn(),
}));

vi.mock("../selection.js", () => ({
  disableClickOnSelectedURLCardToHide: vi.fn(),
  enableClickOnSelectedURLCardToHide: vi.fn(),
}));

vi.mock("../loading.js", () => ({
  setTimeoutAndShowURLCardLoadingIcon: vi.fn(),
  clearTimeoutIDAndHideLoadingIcon: vi.fn(),
}));

vi.mock("../get.js", () => ({
  getUpdatedURL: vi.fn(() => Promise.resolve()),
  handleRejectFromGetURL: vi.fn(),
}));

vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ urls: [] })),
  setState: vi.fn(),
}));

const $ = window.jQuery;

const URL_CARD_HTML = `
  <div class="urlRow" utuburlid="1" urlSelected="false">
    <div class="urlTitleAndUpdateIconWrap"></div>
    <div class="updateUrlTitleWrap"><input class="urlTitleUpdate" /></div>
  </div>
`;

describe("update-title metrics — UI_URL_TITLE_EDIT_OPEN", () => {
  beforeEach(() => {
    document.body.innerHTML = URL_CARD_HTML;
    vi.clearAllMocks();
  });

  it("emits ui_url_title_edit_open at the top of showUpdateURLTitleForm", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    const urlCard = $(".urlRow");
    const urlTitleAndShowUpdateIconWrap = urlCard.find(
      ".urlTitleAndUpdateIconWrap",
    );
    showUpdateURLTitleForm(urlTitleAndShowUpdateIconWrap, urlCard);

    expect(emit).toHaveBeenCalledWith("ui_url_title_edit_open");
  });

  it("emits exactly once per call", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    const urlCard = $(".urlRow");
    const urlTitleAndShowUpdateIconWrap = urlCard.find(
      ".urlTitleAndUpdateIconWrap",
    );
    showUpdateURLTitleForm(urlTitleAndShowUpdateIconWrap, urlCard);

    expect(emit).toHaveBeenCalledTimes(1);
  });
});
