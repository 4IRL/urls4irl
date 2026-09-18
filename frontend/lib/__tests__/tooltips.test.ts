import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Per-file globals mock: a single shared Tooltip spy instance returned by both
// `getOrCreateInstance` and `getInstance`, so the assertions below can count
// instantiations and disposals. Copied from `access-btn-metrics.test.ts`; the
// ambient `test-setup.ts` Tooltip mock returns `null` from `getInstance`, which
// would make every `dispose()` a silent no-op.
vi.mock("../globals.js", async () => {
  const jquery = (await import("jquery")).default;
  const tooltipInstance = {
    show: vi.fn(),
    hide: vi.fn(),
    dispose: vi.fn(),
  };
  return {
    $: jquery,
    jQuery: jquery,
    bootstrap: {
      Tooltip: {
        getInstance: vi.fn(() => tooltipInstance),
        getOrCreateInstance: vi.fn(() => tooltipInstance),
      },
    },
  };
});

const TOOLTIP_DECK_HTML = `
  <button id="utubBtnDelete" data-bs-toggle="tooltip" data-bs-title="Delete UTub"></button>
  <button id="memberSelfBtnDelete" data-bs-toggle="tooltip" data-bs-title="Leave UTub"></button>
  <button id="utubNameFilterBtn" class="hidden" data-bs-toggle="tooltip" data-bs-title="Filter UTub names"></button>
  <button id="utubBtnCreate"></button>
`;

/**
 * Stub the `(any-pointer: coarse)` media query `isCoarsePointer()` reads, using
 * the `vi.spyOn(window, "matchMedia")` pattern established in `mobile.test.ts`.
 * Every test sets this explicitly so neither branch depends on a happy-dom
 * default.
 */
function stubCoarsePointer(isCoarse: boolean): void {
  vi.spyOn(window, "matchMedia").mockReturnValue({
    matches: isCoarse,
  } as MediaQueryList);
}

function instantiatedElementIds(
  getOrCreateInstance: ReturnType<typeof vi.fn>,
): string[] {
  return getOrCreateInstance.mock.calls.map(
    (call) => (call[0] as HTMLElement).id,
  );
}

describe("initTooltips", () => {
  beforeEach(async () => {
    const { _resetTooltipsForTests } = await import("../tooltips.js");
    _resetTooltipsForTests();
    vi.clearAllMocks();
    document.body.innerHTML = TOOLTIP_DECK_HTML;
    stubCoarsePointer(false);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = "";
  });

  it("creates exactly one instance per [data-bs-toggle='tooltip'] element", async () => {
    const { initTooltips } = await import("../tooltips.js");
    const { bootstrap } = await import("../globals.js");
    const getOrCreateInstance = bootstrap.Tooltip
      .getOrCreateInstance as unknown as ReturnType<typeof vi.fn>;

    initTooltips();

    expect(getOrCreateInstance).toHaveBeenCalledTimes(3);
    expect(instantiatedElementIds(getOrCreateInstance)).toEqual([
      "utubBtnDelete",
      "memberSelfBtnDelete",
      "utubNameFilterBtn",
    ]);
  });

  it("skips elements without the data-bs-toggle attribute", async () => {
    const { initTooltips } = await import("../tooltips.js");
    const { bootstrap } = await import("../globals.js");
    const getOrCreateInstance = bootstrap.Tooltip
      .getOrCreateInstance as unknown as ReturnType<typeof vi.fn>;

    initTooltips();

    expect(instantiatedElementIds(getOrCreateInstance)).not.toContain(
      "utubBtnCreate",
    );
  });

  it("instantiates a hidden element so it is ready once it is revealed", async () => {
    const { initTooltips } = await import("../tooltips.js");
    const { bootstrap } = await import("../globals.js");
    const getOrCreateInstance = bootstrap.Tooltip
      .getOrCreateInstance as unknown as ReturnType<typeof vi.fn>;

    initTooltips();

    expect(instantiatedElementIds(getOrCreateInstance)).toContain(
      "utubNameFilterBtn",
    );
  });

  it("is one-shot — a second call creates no duplicate instances", async () => {
    const { initTooltips } = await import("../tooltips.js");
    const { bootstrap } = await import("../globals.js");
    const getOrCreateInstance = bootstrap.Tooltip
      .getOrCreateInstance as unknown as ReturnType<typeof vi.fn>;

    initTooltips();
    initTooltips();

    expect(getOrCreateInstance).toHaveBeenCalledTimes(3);
  });

  it("creates nothing on a coarse-pointer (touch) device", async () => {
    const { initTooltips } = await import("../tooltips.js");
    const { bootstrap } = await import("../globals.js");
    const getOrCreateInstance = bootstrap.Tooltip
      .getOrCreateInstance as unknown as ReturnType<typeof vi.fn>;
    stubCoarsePointer(true);

    initTooltips();

    expect(getOrCreateInstance).not.toHaveBeenCalled();
  });
});

describe("disposeTooltipsWithin", () => {
  beforeEach(async () => {
    const { _resetTooltipsForTests } = await import("../tooltips.js");
    _resetTooltipsForTests();
    vi.clearAllMocks();
    stubCoarsePointer(false);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = "";
  });

  it("disposes only the live instances of matching descendants", async () => {
    const { disposeTooltipsWithin } = await import("../tooltips.js");
    const { $, bootstrap } = await import("../globals.js");
    document.body.innerHTML = `
      <div id="URLFocusRow">
        <button id="urlBtnAccess" data-bs-toggle="tooltip"></button>
        <button id="urlBtnDelete" data-bs-toggle="tooltip"></button>
        <button id="urlTitle"></button>
      </div>
    `;
    const liveInstance = bootstrap.Tooltip.getOrCreateInstance(
      document.querySelector("#urlBtnAccess") as HTMLElement,
    );
    const getInstance = bootstrap.Tooltip.getInstance as unknown as ReturnType<
      typeof vi.fn
    >;
    getInstance.mockImplementation((element: HTMLElement) =>
      element.id === "urlBtnAccess" ? liveInstance : null,
    );

    disposeTooltipsWithin($("#URLFocusRow"));

    expect(liveInstance.dispose).toHaveBeenCalledTimes(1);
    expect(
      getInstance.mock.calls.map((call) => (call[0] as HTMLElement).id),
    ).toEqual(["urlBtnAccess", "urlBtnDelete"]);
  });

  it("disposes the container itself when it is the tooltip trigger", async () => {
    // Call sites pass a single trigger as often as a subtree (a tag badge being
    // removed on its own), so a descendants-only sweep would leak it.
    const { disposeTooltipsWithin } = await import("../tooltips.js");
    const { $, bootstrap } = await import("../globals.js");
    document.body.innerHTML = `
      <button id="urlTagBtnDelete" data-bs-toggle="tooltip"></button>
    `;
    const liveInstance = bootstrap.Tooltip.getOrCreateInstance(
      document.querySelector("#urlTagBtnDelete") as HTMLElement,
    );
    const getInstance = bootstrap.Tooltip.getInstance as unknown as ReturnType<
      typeof vi.fn
    >;
    getInstance.mockImplementation((element: HTMLElement) =>
      element.id === "urlTagBtnDelete" ? liveInstance : null,
    );

    disposeTooltipsWithin($("#urlTagBtnDelete"));

    expect(liveInstance.dispose).toHaveBeenCalledTimes(1);
    expect(
      getInstance.mock.calls.map((call) => (call[0] as HTMLElement).id),
    ).toEqual(["urlTagBtnDelete"]);
  });
});

describe("disposeTooltipsWithinAfterHide", () => {
  // Guards the measured race: the tag-delete click hides the tooltip, then the
  // AJAX success tears the badge down ~60ms later — inside Bootstrap's 150ms
  // fade — and a synchronous dispose there makes the hide's queued callback
  // throw. The deferral is the whole point, so assert it, not just the dispose.
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    stubCoarsePointer(false);
    document.body.innerHTML = `
      <span id="tagBadge">
        <button id="urlTagBtnDelete" data-bs-toggle="tooltip"></button>
      </span>
    `;
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    document.body.innerHTML = "";
  });

  it("does not dispose until Bootstrap's hide transition has run", async () => {
    const { disposeTooltipsWithinAfterHide, TOOLTIP_DISPOSE_DELAY_MS } =
      await import("../tooltips.js");
    const { $, bootstrap } = await import("../globals.js");
    const liveInstance = bootstrap.Tooltip.getOrCreateInstance(
      document.querySelector("#urlTagBtnDelete") as HTMLElement,
    );
    const getInstance = bootstrap.Tooltip.getInstance as unknown as ReturnType<
      typeof vi.fn
    >;
    getInstance.mockImplementation((element: HTMLElement) =>
      element.id === "urlTagBtnDelete" ? liveInstance : null,
    );

    disposeTooltipsWithinAfterHide($("#tagBadge"));

    expect(liveInstance.dispose).not.toHaveBeenCalled();
    vi.advanceTimersByTime(TOOLTIP_DISPOSE_DELAY_MS - 50);
    expect(liveInstance.dispose).not.toHaveBeenCalled();

    vi.advanceTimersByTime(TOOLTIP_DISPOSE_DELAY_MS);

    expect(liveInstance.dispose).toHaveBeenCalledTimes(1);
  });

  it("still disposes a subtree that was already detached", async () => {
    // The caller removes the badge immediately and only the dispose is deferred;
    // Bootstrap keys its instance map by element, not by attachment.
    const { disposeTooltipsWithinAfterHide, TOOLTIP_DISPOSE_DELAY_MS } =
      await import("../tooltips.js");
    const { $, bootstrap } = await import("../globals.js");
    const liveInstance = bootstrap.Tooltip.getOrCreateInstance(
      document.querySelector("#urlTagBtnDelete") as HTMLElement,
    );
    const getInstance = bootstrap.Tooltip.getInstance as unknown as ReturnType<
      typeof vi.fn
    >;
    getInstance.mockImplementation((element: HTMLElement) =>
      element.id === "urlTagBtnDelete" ? liveInstance : null,
    );
    const tagBadge = $("#tagBadge");

    disposeTooltipsWithinAfterHide(tagBadge);
    tagBadge.remove();
    vi.advanceTimersByTime(TOOLTIP_DISPOSE_DELAY_MS);

    expect(document.querySelector("#tagBadge")).toBeNull();
    expect(liveInstance.dispose).toHaveBeenCalledTimes(1);
  });
});

describe("applyHoverTooltip", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    stubCoarsePointer(false);
    document.body.innerHTML = `<button id="target"></button>`;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = "";
  });

  it("stamps the attribute block, defaults the aria-label to the title, and instantiates", async () => {
    const { applyHoverTooltip } = await import("../tooltips.js");
    const { $, bootstrap } = await import("../globals.js");
    const btn = $("#target");

    applyHoverTooltip({
      btn,
      tooltip: { title: "Remove tag", customClass: "urlTagBtnDelete-tooltip" },
    });

    expect(btn.attr("data-bs-toggle")).toBe("tooltip");
    expect(btn.attr("data-bs-custom-class")).toBe("urlTagBtnDelete-tooltip");
    expect(btn.attr("data-bs-placement")).toBe("top");
    expect(btn.attr("data-bs-trigger")).toBe("hover");
    expect(btn.attr("data-bs-title")).toBe("Remove tag");
    expect(btn.attr("aria-label")).toBe("Remove tag");
    expect(bootstrap.Tooltip.getOrCreateInstance).toHaveBeenCalledWith(btn[0]);
  });

  it("uses an explicit ariaLabel override without changing the bubble text", async () => {
    const { applyHoverTooltip } = await import("../tooltips.js");
    const { $ } = await import("../globals.js");
    const btn = $("#target");

    applyHoverTooltip({
      btn,
      tooltip: {
        title: "Remove tag",
        customClass: "urlTagBtnDelete-tooltip",
        ariaLabel: "Remove tag work",
      },
    });

    expect(btn.attr("data-bs-title")).toBe("Remove tag");
    expect(btn.attr("aria-label")).toBe("Remove tag work");
  });

  it("skips the attributes and the instance on a coarse pointer, keeping the aria-label", async () => {
    stubCoarsePointer(true);
    const { applyHoverTooltip } = await import("../tooltips.js");
    const { $, bootstrap } = await import("../globals.js");
    const btn = $("#target");

    applyHoverTooltip({
      btn,
      tooltip: {
        title: "Remove tag",
        customClass: "urlTagBtnDelete-tooltip",
        ariaLabel: "Remove tag work",
      },
    });

    expect(btn.attr("data-bs-toggle")).toBeUndefined();
    expect(btn.attr("data-bs-title")).toBeUndefined();
    expect(bootstrap.Tooltip.getOrCreateInstance).not.toHaveBeenCalled();
    // The accessible name is not a tooltip — touch screen readers still need it.
    expect(btn.attr("aria-label")).toBe("Remove tag work");
  });

  it("is a no-op when no tooltip is configured", async () => {
    const { applyHoverTooltip } = await import("../tooltips.js");
    const { $, bootstrap } = await import("../globals.js");
    const btn = $("#target");

    applyHoverTooltip({ btn, tooltip: undefined });

    expect(btn.attr("aria-label")).toBeUndefined();
    expect(btn.attr("data-bs-toggle")).toBeUndefined();
    expect(bootstrap.Tooltip.getOrCreateInstance).not.toHaveBeenCalled();
  });
});

describe("restoreTooltipIfHovered", () => {
  // The disposeTooltipsWithin suite above installs its own getInstance
  // implementation, and vi.clearAllMocks() clears call history but NOT
  // implementations — so pin a known instance for every test here.
  const restoreInstance = { show: vi.fn(), hide: vi.fn(), dispose: vi.fn() };

  beforeEach(async () => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    document.body.innerHTML = `<button id="submitBtn"></button>`;
    const { bootstrap } = await import("../globals.js");
    vi.mocked(bootstrap.Tooltip.getInstance).mockReturnValue(
      restoreInstance as unknown as ReturnType<
        typeof bootstrap.Tooltip.getInstance
      >,
    );
    restoreInstance.show.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  function submitBtn(): HTMLElement {
    return document.querySelector("#submitBtn") as HTMLElement;
  }

  it("does nothing when the element is undefined", async () => {
    const { restoreTooltipIfHovered } = await import("../tooltips.js");
    const { bootstrap } = await import("../globals.js");

    expect(() => restoreTooltipIfHovered(undefined)).not.toThrow();
    vi.advanceTimersByTime(1000);

    expect(vi.mocked(bootstrap.Tooltip.getInstance)).not.toHaveBeenCalled();
  });

  it("does nothing when the cursor is not on the element", async () => {
    const { restoreTooltipIfHovered } = await import("../tooltips.js");
    const { bootstrap } = await import("../globals.js");
    // happy-dom has no pointer, so `:hover` never matches on its own.
    vi.spyOn(submitBtn(), "matches").mockReturnValue(false);

    restoreTooltipIfHovered(submitBtn());
    vi.advanceTimersByTime(1000);

    expect(vi.mocked(bootstrap.Tooltip.getInstance)).not.toHaveBeenCalled();
  });

  it("defers the show past Bootstrap's fade rather than showing synchronously", async () => {
    const { restoreTooltipIfHovered, TOOLTIP_RESTORE_DELAY_MS } =
      await import("../tooltips.js");
    const { bootstrap } = await import("../globals.js");
    vi.spyOn(submitBtn(), "matches").mockReturnValue(true);

    restoreTooltipIfHovered(submitBtn());

    // A show() inside hide()'s fade window builds a tip that hide()'s queued
    // teardown immediately disposes — a real backend 400 lands in ~75ms, well
    // inside the 150ms fade, so an eager show leaves no bubble at all.
    expect(restoreInstance.show).not.toHaveBeenCalled();

    vi.advanceTimersByTime(TOOLTIP_RESTORE_DELAY_MS);

    expect(restoreInstance.show).toHaveBeenCalledTimes(1);
    expect(vi.mocked(bootstrap.Tooltip.getInstance)).toHaveBeenCalledWith(
      submitBtn(),
    );
  });

  it("re-checks hover when the timer fires and skips the show if the cursor left", async () => {
    const { restoreTooltipIfHovered, TOOLTIP_RESTORE_DELAY_MS } =
      await import("../tooltips.js");
    const matches = vi.spyOn(submitBtn(), "matches").mockReturnValue(true);

    restoreTooltipIfHovered(submitBtn());
    // The pointer moves away during the deferral window.
    matches.mockReturnValue(false);
    vi.advanceTimersByTime(TOOLTIP_RESTORE_DELAY_MS);

    expect(restoreInstance.show).not.toHaveBeenCalled();
  });

  it("keeps only one pending restore per button when a resubmit schedules another", async () => {
    // A second failure schedules its own restore; the first timer must be
    // cancelled or the bubble would come back twice (and once mid-flight of the
    // second request, while it is deliberately hidden).
    const { restoreTooltipIfHovered, TOOLTIP_RESTORE_DELAY_MS } =
      await import("../tooltips.js");
    vi.spyOn(submitBtn(), "matches").mockReturnValue(true);

    restoreTooltipIfHovered(submitBtn());
    vi.advanceTimersByTime(TOOLTIP_RESTORE_DELAY_MS - 50);
    restoreTooltipIfHovered(submitBtn());
    vi.advanceTimersByTime(TOOLTIP_RESTORE_DELAY_MS);

    expect(restoreInstance.show).toHaveBeenCalledTimes(1);
  });

  it("does not throw when the instance was disposed during the deferral", async () => {
    const { restoreTooltipIfHovered, TOOLTIP_RESTORE_DELAY_MS } =
      await import("../tooltips.js");
    const { bootstrap } = await import("../globals.js");
    vi.spyOn(submitBtn(), "matches").mockReturnValue(true);
    vi.mocked(bootstrap.Tooltip.getInstance).mockReturnValue(null);

    restoreTooltipIfHovered(submitBtn());

    expect(() =>
      vi.advanceTimersByTime(TOOLTIP_RESTORE_DELAY_MS),
    ).not.toThrow();
  });
});
