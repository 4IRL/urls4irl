import { UI_EVENTS } from "../../../../lib/metrics-events.js";
import { showUpdateURLTitleForm } from "../update-title.js";
import { createURLTitleAndUpdateBlock } from "../url-title.js";
import { ajaxCall } from "../../../../lib/ajax.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../../../../lib/config.js", () => ({
  APP_CONFIG: {
    routes: { updateURLTitle: () => "/dummy" },
    constants: {
      URLS_TITLE_MIN_LENGTH: 1,
      URLS_TITLE_MAX_LENGTH: 100,
    },
    strings: {},
  },
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

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_URL_TITLE_EDIT_OPEN,
    });
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

describe("url-title metrics — url_title_edit unchanged value", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    vi.clearAllMocks();
  });

  it("url_title_edit unchanged value: emits submit but fires no AJAX", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const { getState } = await import("../../../../store/app-store.js");
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
    } as unknown as ReturnType<typeof getState>);

    const urlRow = $('<div class="urlRow" utuburlid="1"></div>');
    $(document.body).append(urlRow);
    const block = createURLTitleAndUpdateBlock("Same Title", urlRow, 1);
    urlRow.append(block);

    const submitBtn = urlRow.find(".urlTitleSubmitBtnUpdate");
    const titleInput = urlRow.find("input.urlTitleUpdate");
    titleInput.val("Same Title");
    // .urlTitle text element is created inside the block with text "Same Title"
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
    expect(emit).not.toHaveBeenCalled();

    submitBtn.trigger("click.updateUrlTitle");

    // Wait for the async updateURLTitle to complete its unchanged-value short-circuit
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_FORM_SUBMIT,
      trigger: "button_click",
      form: "url_title_edit",
    });
    expect(
      vi.mocked(emit).mock.calls.filter((call) => {
        const args = call[0] as { event?: string; form?: string };
        return (
          args.event === UI_EVENTS.UI_FORM_SUBMIT &&
          args.form === "url_title_edit"
        );
      }),
    ).toHaveLength(1);
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });
});
