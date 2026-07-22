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
  isURLTitleSubmitInFlight: vi.fn(() => false),
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
  it("renders pencil span with aria-label, role=button, tabindex, edit-pencil-icon, and tabbable classes", () => {
    const { pencil } = mountTitleBlock();

    expect(pencil.length).toBe(1);
    expect(pencil.is("span")).toBe(true);
    expect(pencil.attr("aria-label")).toBe(
      APP_CONFIG.strings.EDIT_URL_TITLE_TOOLTIP,
    );
    expect(pencil.attr("role")).toBe("button");
    expect(pencil.attr("tabindex")).toBe("0");
    expect(pencil.hasClass("edit-pencil-icon")).toBe(true);
    expect(pencil.hasClass("tabbable")).toBe(true);
  });

  it("renders the same 14x14 bi-pencil SVG as the UTub name/description edit icons", () => {
    const { pencil } = mountTitleBlock();
    const svg = pencil.find("svg");

    expect(svg.length).toBe(1);
    expect(svg.attr("width")).toBe("14");
    expect(svg.attr("height")).toBe("14");
    expect(svg.hasClass("bi-pencil")).toBe(true);
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

describe("createUpdateURLTitleInput - Saved✓ tick slot structure", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("hangs .field-saved-tick-slot directly off the wrap as a SIBLING of the inner input row (not nested inside it)", () => {
    const { urlCard } = mountTitleBlock();
    const wrap = urlCard.find(".updateUrlTitleWrap");
    const tickSlot = wrap.find(".field-saved-tick-slot");

    expect(tickSlot.length).toBe(1);
    // Core invariant: the tick slot's parent is the wrap itself, so it renders
    // below the input row (guards against a future edit nesting it too deep).
    expect(tickSlot.parent().is(wrap)).toBe(true);

    // The input container moved one level deeper into the new inner row, so it
    // is no longer a direct child of the wrap (the > width selector was updated
    // to a descendant selector to match — Step 3 CSS fix).
    expect(wrap.children(".text-input-container").length).toBe(0);
    expect(wrap.find(".text-input-container").length).toBe(1);

    const tick = tickSlot.find(".field-saved-tick");
    expect(tick.length).toBe(1);
    expect(tick.hasClass("opa-0")).toBe(true);
    expect(tick.attr("aria-hidden")).toBe("true");
  });
});
