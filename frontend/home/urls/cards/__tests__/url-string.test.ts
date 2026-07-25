import {
  createURLStringAndUpdateBlock,
  modifyURLStringForDisplay,
} from "../url-string.js";
import { updateURL, isURLStringSubmitInFlight } from "../update-string.js";
import { ajaxCall } from "../../../../lib/ajax.js";
import { isCoarsePointer } from "../../../mobile.js";
import { createMockJqXHR } from "../../../../__tests__/helpers/mock-jquery.js";
import { UI_EVENTS } from "../../../../types/metrics-events.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../update-string.js", () => ({
  updateURL: vi.fn(),
  hideAndResetUpdateURLStringForm: vi.fn(),
  isURLStringSubmitInFlight: vi.fn(() => false),
}));

vi.mock("../access.js", () => ({ accessLink: vi.fn() }));

vi.mock("../url-context.js", () => ({
  isURLSearchActive: vi.fn(() => false),
  getActiveTagCount: vi.fn(() => 0),
}));

// Infra mocks for the in-flight guard test, which drives the REAL updateURL
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

describe("modifyURLStringForDisplay", () => {
  it("strips https:// prefix", () => {
    expect(modifyURLStringForDisplay("https://example.com")).toBe(
      "example.com",
    );
  });

  it("strips http:// prefix", () => {
    expect(modifyURLStringForDisplay("http://example.com")).toBe("example.com");
  });

  it("strips www. prefix alone", () => {
    expect(modifyURLStringForDisplay("www.example.com")).toBe("example.com");
  });

  it("strips https://www. combined prefix", () => {
    expect(modifyURLStringForDisplay("https://www.example.com")).toBe(
      "example.com",
    );
  });

  it("strips http://www. combined prefix", () => {
    expect(modifyURLStringForDisplay("http://www.example.com")).toBe(
      "example.com",
    );
  });

  it("preserves path after stripping https://", () => {
    expect(modifyURLStringForDisplay("https://example.com/path/to/page")).toBe(
      "example.com/path/to/page",
    );
  });

  it("preserves path after stripping https://www.", () => {
    expect(modifyURLStringForDisplay("https://www.example.com/path")).toBe(
      "example.com/path",
    );
  });

  it("does not strip non-http protocols", () => {
    expect(modifyURLStringForDisplay("ftp://example.com")).toBe(
      "ftp://example.com",
    );
  });

  it("returns string unchanged when no recognisable prefix is present", () => {
    expect(modifyURLStringForDisplay("example.com")).toBe("example.com");
  });

  it("returns empty string for empty input", () => {
    expect(modifyURLStringForDisplay("")).toBe("");
  });
});

describe("createUpdateURLStringInput - Saved✓ tick slot structure", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function mountStringBlock(): JQuery {
    document.body.innerHTML = `<div class="urlRow" utuburlid="1" urlSelected="true" filterable="true"></div>`;
    const urlCard = $(".urlRow");
    urlCard.append(
      createURLStringAndUpdateBlock("https://example.com", urlCard, 1),
    );
    return urlCard;
  }

  it("hangs .field-saved-tick-slot directly off the wrap as a SIBLING of the inner input row (not nested inside it)", () => {
    const urlCard = mountStringBlock();
    const wrap = urlCard.find(".updateUrlStringWrap");
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

describe("createUpdateURLStringInput - in-flight submit guard blocks a second overlapping submit", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(isCoarsePointer).mockReturnValue(false);
  });

  function mountStringBlock(): JQuery {
    document.body.innerHTML = `<div class="urlRow" utuburlid="1" urlSelected="true" filterable="true"></div>`;
    const urlCard = $(".urlRow");
    urlCard.append(
      createURLStringAndUpdateBlock("https://example.com", urlCard, 1),
    );
    return urlCard;
  }

  it("fires the real PATCH once and emits UI_FORM_SUBMIT once when a second submit lands while the first is genuinely in flight", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    // Wire the module mock to delegate to the REAL updateURL + REAL
    // isURLStringSubmitInFlight (same module instance → same module-level flag)
    // so the entry-point guard reads the true in-flight state a real pending
    // PATCH sets — not a hard-coded getter return sequence. This test therefore
    // FAILS if the getter is ever disconnected from real request state.
    const updateStringActual = await vi.importActual<
      typeof import("../update-string.js")
    >("../update-string.js");
    vi.mocked(updateURL).mockImplementation(updateStringActual.updateURL);
    vi.mocked(isURLStringSubmitInFlight).mockImplementation(
      updateStringActual.isURLStringSubmitInFlight,
    );

    // Mobile consolidated panel open: coarse pointer + the morphed Cancel bar
    // present/unhidden is the card panel-open signal updateURL reads to arm the
    // in-flight guard.
    vi.mocked(isCoarsePointer).mockReturnValue(true);

    const urlCard = mountStringBlock();
    urlCard.append('<button class="urlStringCancelBigBtnUpdate"></button>');
    const submitBtn = urlCard.find(".urlStringSubmitBtnUpdate");
    // Changed + valid value so the real updateURL runs the PATCH (not the
    // unchanged-skip / invalid-URL early returns).
    urlCard.find(".urlStringUpdate").val("https://changed-example.com");

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
    expect(isURLStringSubmitInFlight()).toBe(true);

    // Settle the request (non-200) so the always-handler clears the real
    // module-level guard and it does not leak into other tests/files.
    deferred.resolve(
      {
        URL: {
          utubUrlID: 1,
          urlString: "https://changed-example.com",
          urlTitle: "",
          urlTags: [],
        },
      },
      "success",
      { status: 500 },
    );
    expect(isURLStringSubmitInFlight()).toBe(false);
  });
});
