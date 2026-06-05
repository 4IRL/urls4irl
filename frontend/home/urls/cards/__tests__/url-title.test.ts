import { APP_CONFIG } from "../../../../lib/config.js";
import { createURLTitleAndUpdateBlock } from "../url-title.js";
import { showUpdateURLTitleForm } from "../update-title.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../update-title.js", () => ({
  showUpdateURLTitleForm: vi.fn(),
  hideAndResetUpdateURLTitleForm: vi.fn(),
  updateURLTitle: vi.fn(),
}));

const $ = window.jQuery;

const UTUB_ID = 1;
const URL_TITLE_TEXT = "My Title";

function mountTitleBlock(selected: boolean = true): {
  urlCard: JQuery;
  pencil: JQuery;
  wrap: JQuery;
} {
  document.body.innerHTML = `<div class="urlRow" utuburlid="1" urlSelected="${selected}" filterable="true"></div>`;
  const urlCard = $(".urlRow");
  const block = createURLTitleAndUpdateBlock(URL_TITLE_TEXT, urlCard, UTUB_ID);
  urlCard.append(block);
  const pencil = urlCard.find(".urlTitleBtnUpdate");
  const wrap = urlCard.find(".urlTitleAndUpdateIconWrap");
  return { urlCard, pencil, wrap };
}

describe("createShowUpdateURLTitleIcon - accessibility attributes", () => {
  it("renders pencil with aria-label, type=button, and tabbable class", () => {
    const { pencil } = mountTitleBlock();

    expect(pencil.length).toBe(1);
    expect(pencil.attr("aria-label")).toBe(
      APP_CONFIG.strings.EDIT_URL_TITLE_TOOLTIP,
    );
    expect(pencil.attr("type")).toBe("button");
    expect(pencil.hasClass("tabbable")).toBe(true);
  });
});

describe("createShowUpdateURLTitleIcon - keyboard activation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("invokes showUpdateURLTitleForm on Enter keydown", () => {
    const { pencil } = mountTitleBlock();

    const event = $.Event("keydown.showUpdateURLTitle", { key: "Enter" });
    pencil.trigger(event);

    expect(vi.mocked(showUpdateURLTitleForm)).toHaveBeenCalledOnce();
  });

  it("invokes showUpdateURLTitleForm on Space keydown", () => {
    const { pencil } = mountTitleBlock();

    const event = $.Event("keydown.showUpdateURLTitle", { key: " " });
    pencil.trigger(event);

    expect(vi.mocked(showUpdateURLTitleForm)).toHaveBeenCalledOnce();
  });

  it("does NOT invoke showUpdateURLTitleForm on non-activation key", () => {
    const { pencil } = mountTitleBlock();

    const event = $.Event("keydown.showUpdateURLTitle", { key: "a" });
    pencil.trigger(event);

    expect(vi.mocked(showUpdateURLTitleForm)).not.toHaveBeenCalled();
  });
});

describe("urlTitleAndUpdateIconWrap - row-level click (UTub edit pattern)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("invokes showUpdateURLTitleForm when wrap is clicked on a selected card", () => {
    const { wrap } = mountTitleBlock(true);

    wrap.trigger("click");

    expect(vi.mocked(showUpdateURLTitleForm)).toHaveBeenCalledOnce();
  });

  it("does NOT invoke showUpdateURLTitleForm when wrap is clicked on an unselected card", () => {
    const { wrap } = mountTitleBlock(false);

    wrap.trigger("click");

    expect(vi.mocked(showUpdateURLTitleForm)).not.toHaveBeenCalled();
  });
});
