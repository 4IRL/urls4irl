import { APP_CONFIG } from "../../../../lib/config.js";
import { createURLTitleAndUpdateBlock } from "../url-title.js";
import {
  showUpdateURLTitleForm,
  updateURLTitle,
  isURLTitleSubmitInFlight,
} from "../update-title.js";
import { ajaxCall } from "../../../../lib/ajax.js";
import { isCoarsePointer } from "../../../mobile.js";
import { createMockJqXHR } from "../../../../__tests__/helpers/mock-jquery.js";
import { UI_EVENTS } from "../../../../types/metrics-events.js";

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

// Infra mocks for the in-flight guard test, which drives the REAL updateURLTitle
// (pulled via vi.importActual inside the it() block) end-to-end: ajaxCall is
// stubbed to return a real unresolved Deferred, the pre-flight stale-check GET
// and loading-icon timer are stubbed out, and the coarse-pointer signal is
// controllable. Harmless to the DOM-only tests above (they never reach these).
vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../get.js", () => ({
  getUpdatedURL: vi.fn(() => Promise.resolve()),
  handleRejectFromGetURL: vi.fn(),
}));

vi.mock("../loading.js", () => ({
  setTimeoutAndShowURLCardLoadingIcon: vi.fn(() => 1),
  clearTimeoutIDAndHideLoadingIcon: vi.fn(),
}));

vi.mock("../../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  isCoarsePointer: vi.fn(() => false),
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

describe("createUpdateURLTitleInput - in-flight submit guard blocks a second overlapping submit", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(isCoarsePointer).mockReturnValue(false);
  });

  it("fires the real PATCH once and emits UI_FORM_SUBMIT once when a second submit lands while the first is genuinely in flight", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    // Wire the module mock to delegate to the REAL updateURLTitle + REAL
    // isURLTitleSubmitInFlight (same module instance → same module-level flag)
    // so the entry-point guard reads the true in-flight state a real pending
    // PATCH sets — not a hard-coded getter return sequence. This test therefore
    // FAILS if the getter is ever disconnected from real request state.
    const updateTitleActual =
      await vi.importActual<typeof import("../update-title.js")>(
        "../update-title.js",
      );
    vi.mocked(updateURLTitle).mockImplementation(
      updateTitleActual.updateURLTitle,
    );
    vi.mocked(isURLTitleSubmitInFlight).mockImplementation(
      updateTitleActual.isURLTitleSubmitInFlight,
    );

    // Mobile consolidated panel open: coarse pointer + the string Cancel bar
    // present/unhidden is the card panel-open signal updateURLTitle reads to arm
    // the in-flight guard.
    vi.mocked(isCoarsePointer).mockReturnValue(true);

    const { urlCard } = mountTitleBlock();
    urlCard.append('<button class="urlStringCancelBigBtnUpdate"></button>');
    const submitBtn = urlCard.find(".urlTitleSubmitBtnUpdate");
    // Changed value so the real updateURLTitle runs the PATCH (not the
    // unchanged-skip early return).
    urlCard.find(".urlTitleUpdate").val("Changed Title");

    // A real, UNRESOLVED Deferred: the first PATCH stays in flight (done/fail
    // never fire) so the real module-level guard stays set between the clicks.
    const deferred = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValue(deferred);

    // Two overlapping submits. The first sets the real flag (synchronously,
    // before its awaited pre-flight); the second must read that real flag and
    // short-circuit at the entry-point guard.
    submitBtn.trigger("click");
    submitBtn.trigger("click");

    // Flush microtasks so the first submit's awaited pre-flight resolves and it
    // reaches the real ajaxCall (the second click was already blocked above).
    await new Promise((resolve) => setTimeout(resolve, 0));

    // Exactly one PATCH and one UI_FORM_SUBMIT — the second click was blocked by
    // the real guard, which is still set while the request is pending.
    expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(1);
    expect(
      vi.mocked(emit).mock.calls.filter((call) => {
        const args = call[0] as { event?: string };
        return args.event === UI_EVENTS.UI_FORM_SUBMIT;
      }),
    ).toHaveLength(1);
    expect(isURLTitleSubmitInFlight()).toBe(true);

    // Settle the request (non-200) so the always-handler clears the real
    // module-level guard and it does not leak into other tests/files.
    deferred.resolve(
      {
        URL: {
          utubUrlID: 1,
          urlString: "https://example.com",
          urlTitle: "Changed Title",
          urlTags: [],
        },
      },
      "success",
      { status: 500 },
    );
    expect(isURLTitleSubmitInFlight()).toBe(false);
  });
});
