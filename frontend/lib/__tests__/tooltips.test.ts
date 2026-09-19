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

  it("stamps the managed marker on every trigger it instantiates", async () => {
    const { initTooltips } = await import("../tooltips.js");

    initTooltips();

    expect(
      document.querySelector("#utubBtnDelete")?.hasAttribute(
        "data-hover-tooltip",
      ),
    ).toBe(true);
    // The nudge anchors carry no `data-bs-toggle` at ready time, so the sweep
    // never reaches them and they never get the marker the a11y handlers use.
    expect(
      document.querySelector("#utubBtnCreate")?.hasAttribute(
        "data-hover-tooltip",
      ),
    ).toBe(false);
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

describe("hideTooltip", () => {
  beforeEach(async () => {
    const { _resetTooltipsForTests } = await import("../tooltips.js");
    _resetTooltipsForTests();
    vi.clearAllMocks();
    stubCoarsePointer(false);
    document.body.innerHTML = TOOLTIP_DECK_HTML;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = "";
  });

  it("hides the live instance of the element it is given", async () => {
    const { hideTooltip } = await import("../tooltips.js");
    const { bootstrap } = await import("../globals.js");
    const trigger = document.querySelector("#utubBtnDelete") as HTMLElement;
    const liveInstance = bootstrap.Tooltip.getOrCreateInstance(trigger);

    hideTooltip(trigger);

    expect(vi.mocked(bootstrap.Tooltip.getInstance)).toHaveBeenCalledWith(
      trigger,
    );
    expect(liveInstance.hide).toHaveBeenCalledTimes(1);
  });

  it("is a no-op when the element has no live instance", async () => {
    // Coarse pointers instantiate nothing, so a hide site can legitimately run
    // against a trigger Bootstrap has never seen.
    const { hideTooltip } = await import("../tooltips.js");
    const { bootstrap } = await import("../globals.js");
    const trigger = document.querySelector("#utubBtnDelete") as HTMLElement;
    const sharedInstance = bootstrap.Tooltip.getOrCreateInstance(trigger);
    vi.mocked(bootstrap.Tooltip.getInstance).mockReturnValueOnce(null);

    expect(() => hideTooltip(trigger)).not.toThrow();
    expect(sharedInstance.hide).not.toHaveBeenCalled();
  });

  it("does not reach for an instance when the selector matched nothing", async () => {
    // Call sites pass `$(selector)[0]` / `.get(0)`, which is `undefined` on an
    // empty match — Bootstrap's `getInstance` must never be handed that.
    const { hideTooltip } = await import("../tooltips.js");
    const { $, bootstrap } = await import("../globals.js");

    hideTooltip($("#noSuchButton")[0]);

    expect(vi.mocked(bootstrap.Tooltip.getInstance)).not.toHaveBeenCalled();
  });

  it("still hides an instance whose element has been detached", async () => {
    // Bootstrap keys its instance map by element, not by attachment, so a
    // trigger torn down by its own click is still hideable.
    const { hideTooltip } = await import("../tooltips.js");
    const { bootstrap } = await import("../globals.js");
    const trigger = document.querySelector("#utubBtnDelete") as HTMLElement;
    const liveInstance = bootstrap.Tooltip.getOrCreateInstance(trigger);
    trigger.remove();

    hideTooltip(trigger);

    expect(liveInstance.hide).toHaveBeenCalledTimes(1);
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
  beforeEach(async () => {
    const { _resetTooltipsForTests } = await import("../tooltips.js");
    _resetTooltipsForTests();
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
    // The marker the a11y handlers delegate through — an onboarding-nudge
    // anchor never gets it, which is what keeps Escape away from the nudge.
    expect(btn.attr("data-hover-tooltip")).toBe("");
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

describe("restoreTooltipIfStillTargeted", () => {
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
    const { restoreTooltipIfStillTargeted } = await import("../tooltips.js");
    const { bootstrap } = await import("../globals.js");

    expect(() => restoreTooltipIfStillTargeted(undefined)).not.toThrow();
    vi.advanceTimersByTime(1000);

    expect(vi.mocked(bootstrap.Tooltip.getInstance)).not.toHaveBeenCalled();
  });

  it("does nothing when the button is neither hovered nor keyboard-focused", async () => {
    // The Enter-key submit (focus on the text input) and the same-name
    // confirmation modal (focus on #modalSubmit) both reach the same 400 without
    // ever targeting the button — a forced bubble there would strand.
    const { restoreTooltipIfStillTargeted } = await import("../tooltips.js");
    const { bootstrap } = await import("../globals.js");
    // happy-dom has no pointer, so `:hover` never matches on its own.
    vi.spyOn(submitBtn(), "matches").mockReturnValue(false);

    restoreTooltipIfStillTargeted(submitBtn());
    vi.advanceTimersByTime(1000);

    expect(vi.mocked(bootstrap.Tooltip.getInstance)).not.toHaveBeenCalled();
  });

  it("defers the show past Bootstrap's fade rather than showing synchronously", async () => {
    const { restoreTooltipIfStillTargeted, TOOLTIP_RESTORE_DELAY_MS } =
      await import("../tooltips.js");
    const { bootstrap } = await import("../globals.js");
    vi.spyOn(submitBtn(), "matches").mockReturnValue(true);

    restoreTooltipIfStillTargeted(submitBtn());

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
    const { restoreTooltipIfStillTargeted, TOOLTIP_RESTORE_DELAY_MS } =
      await import("../tooltips.js");
    const matches = vi.spyOn(submitBtn(), "matches").mockReturnValue(true);

    restoreTooltipIfStillTargeted(submitBtn());
    // The pointer moves away during the deferral window.
    matches.mockReturnValue(false);
    vi.advanceTimersByTime(TOOLTIP_RESTORE_DELAY_MS);

    expect(restoreInstance.show).not.toHaveBeenCalled();
  });

  it("keeps only one pending restore per button when a resubmit schedules another", async () => {
    // A second failure schedules its own restore; the first timer must be
    // cancelled or the bubble would come back twice (and once mid-flight of the
    // second request, while it is deliberately hidden).
    const { restoreTooltipIfStillTargeted, TOOLTIP_RESTORE_DELAY_MS } =
      await import("../tooltips.js");
    vi.spyOn(submitBtn(), "matches").mockReturnValue(true);

    restoreTooltipIfStillTargeted(submitBtn());
    vi.advanceTimersByTime(TOOLTIP_RESTORE_DELAY_MS - 50);
    restoreTooltipIfStillTargeted(submitBtn());
    vi.advanceTimersByTime(TOOLTIP_RESTORE_DELAY_MS);

    expect(restoreInstance.show).toHaveBeenCalledTimes(1);
  });

  it("does not throw when the instance was disposed during the deferral", async () => {
    const { restoreTooltipIfStillTargeted, TOOLTIP_RESTORE_DELAY_MS } =
      await import("../tooltips.js");
    const { bootstrap } = await import("../globals.js");
    vi.spyOn(submitBtn(), "matches").mockReturnValue(true);
    vi.mocked(bootstrap.Tooltip.getInstance).mockReturnValue(null);

    restoreTooltipIfStillTargeted(submitBtn());

    expect(() =>
      vi.advanceTimersByTime(TOOLTIP_RESTORE_DELAY_MS),
    ).not.toThrow();
  });

  it("restores for a keyboard-focused button the cursor never touched", async () => {
    // Symmetry with the pointer path: once a bubble can be raised by keyboard
    // focus, a keyboard user who presses Enter and gets a keep-open 400 would
    // otherwise be left with the label silently gone and no `focusin` left to
    // fire while the button is still focused.
    const { restoreTooltipIfStillTargeted, TOOLTIP_RESTORE_DELAY_MS } =
      await import("../tooltips.js");
    vi.spyOn(submitBtn(), "matches").mockImplementation(
      (selector: string) => selector === ":focus-visible",
    );

    restoreTooltipIfStillTargeted(submitBtn());
    vi.advanceTimersByTime(TOOLTIP_RESTORE_DELAY_MS);

    expect(restoreInstance.show).toHaveBeenCalledTimes(1);
  });

  it("re-checks keyboard focus when the timer fires and skips the show if focus left", async () => {
    const { restoreTooltipIfStillTargeted, TOOLTIP_RESTORE_DELAY_MS } =
      await import("../tooltips.js");
    const matches = vi
      .spyOn(submitBtn(), "matches")
      .mockImplementation((selector: string) => selector === ":focus-visible");

    restoreTooltipIfStillTargeted(submitBtn());
    // The user tabs onward during the deferral window.
    matches.mockReturnValue(false);
    vi.advanceTimersByTime(TOOLTIP_RESTORE_DELAY_MS);

    expect(restoreInstance.show).not.toHaveBeenCalled();
  });
});

describe("managed tooltip accessibility handlers", () => {
  // `#utubBtnDelete` is a real Jinja trigger the sweep picks up and marks.
  // `#utubBtnCreate` is an onboarding-nudge anchor: NO `data-bs-toggle` at ready
  // time, so the sweep never marks it — `showTip()` stamps that attribute on it
  // at runtime, which `simulateNudgeShowTip()` below replays. Every assertion
  // about the nudge exists to prove the marker, not the Bootstrap attribute, is
  // what these handlers key off.
  const A11Y_DECK_HTML = `
    <button id="utubBtnDelete" data-bs-toggle="tooltip"
            aria-label="Delete UTub" data-bs-title="Delete UTub"></button>
    <button id="utubBtnCreate"></button>
    <div id="tooltipBubble" role="tooltip"></div>
  `;

  const tooltipInstance = { show: vi.fn(), hide: vi.fn(), dispose: vi.fn() };

  function managedTrigger(): HTMLElement {
    return document.querySelector("#utubBtnDelete") as HTMLElement;
  }

  function nudgeAnchor(): HTMLElement {
    return document.querySelector("#utubBtnCreate") as HTMLElement;
  }

  // The Escape handler is a NATIVE capture-phase listener (so a widget that
  // stops Escape propagating cannot starve it), which jQuery's synthetic
  // `.trigger()` would never reach — dispatch a real KeyboardEvent.
  function pressKey(key: string): void {
    document.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
  }

  function simulateNudgeShowTip(): void {
    nudgeAnchor().setAttribute("data-bs-toggle", "tooltip");
    nudgeAnchor().setAttribute(
      "data-bs-custom-class",
      "onboarding-nudge-tooltip",
    );
  }

  beforeEach(async () => {
    const { _resetTooltipsForTests, initTooltips } =
      await import("../tooltips.js");
    const { bootstrap } = await import("../globals.js");
    _resetTooltipsForTests();
    vi.clearAllMocks();
    // `clearAllMocks` drops call history but keeps implementations, and one case
    // below gives `show` a real one — reset so no test inherits it.
    tooltipInstance.show.mockReset();
    tooltipInstance.hide.mockReset();
    tooltipInstance.dispose.mockReset();
    stubCoarsePointer(false);
    document.body.innerHTML = A11Y_DECK_HTML;
    // Pin the instance for this suite: earlier suites install their own
    // `getInstance` implementations and `vi.clearAllMocks()` clears call history
    // but not implementations.
    vi.mocked(bootstrap.Tooltip.getInstance).mockReturnValue(
      tooltipInstance as unknown as ReturnType<
        typeof bootstrap.Tooltip.getInstance
      >,
    );
    initTooltips();
  });

  afterEach(async () => {
    const { _resetTooltipsForTests } = await import("../tooltips.js");
    _resetTooltipsForTests();
    vi.restoreAllMocks();
    document.body.innerHTML = "";
  });

  it("hides the visible managed tooltip on Escape (WCAG 1.4.13 dismissible)", async () => {
    const { $ } = await import("../globals.js");

    $(managedTrigger()).trigger("show.bs.tooltip");
    $(managedTrigger()).trigger("shown.bs.tooltip");
    pressKey("Escape");

    expect(tooltipInstance.hide).toHaveBeenCalledTimes(1);
  });

  it("dismisses on an Escape pressed during Bootstrap's fade-in", async () => {
    // `shown.bs.tooltip` only fires once the 150ms fade has finished. Tracking
    // the trigger from `show` instead is what stops an Escape inside that window
    // from finding nothing to dismiss and stranding the bubble for good.
    const { $ } = await import("../globals.js");

    $(managedTrigger()).trigger("show.bs.tooltip");
    pressKey("Escape");

    expect(tooltipInstance.hide).toHaveBeenCalledTimes(1);
  });

  it("ignores Escape for a nudge anchor stamped with data-bs-toggle at runtime", async () => {
    // A sweep keyed on `data-bs-toggle` would dismiss the live nudge behind
    // `nudges.ts`'s back, leaving `_activeTip` non-null and suppressing every
    // remaining tip for the session.
    const { $ } = await import("../globals.js");
    simulateNudgeShowTip();

    $(nudgeAnchor()).trigger("show.bs.tooltip");
    $(nudgeAnchor()).trigger("shown.bs.tooltip");
    pressKey("Escape");

    expect(tooltipInstance.hide).not.toHaveBeenCalled();
  });

  it("ignores a non-Escape key", async () => {
    const { $ } = await import("../globals.js");

    $(managedTrigger()).trigger("show.bs.tooltip");
    pressKey("Enter");

    expect(tooltipInstance.hide).not.toHaveBeenCalled();
  });

  it("hides nothing on Escape once the bubble is already hiding", async () => {
    const { $ } = await import("../globals.js");

    $(managedTrigger()).trigger("show.bs.tooltip");
    $(managedTrigger()).trigger("hide.bs.tooltip");
    pressKey("Escape");

    expect(tooltipInstance.hide).not.toHaveBeenCalled();
  });

  it("forgets a tracked trigger that disposeTooltipsWithin tore down", async () => {
    // Disposal fires no `hide.bs.tooltip`, so without the explicit clear the
    // Escape handler would reach into a nulled-out instance.
    const { $ } = await import("../globals.js");
    const { disposeTooltipsWithin } = await import("../tooltips.js");

    $(managedTrigger()).trigger("show.bs.tooltip");
    disposeTooltipsWithin($("#utubBtnDelete"));
    tooltipInstance.hide.mockClear();
    pressKey("Escape");

    expect(tooltipInstance.hide).not.toHaveBeenCalled();
  });

  it("drops the duplicate aria-describedby and hides the bubble from assistive tech", async () => {
    // Bubble text == aria-label, so leaving Bootstrap's wiring in place makes a
    // screen reader announce "Delete UTub, Delete UTub".
    const { $ } = await import("../globals.js");
    managedTrigger().setAttribute("aria-describedby", "tooltipBubble");

    $(managedTrigger()).trigger("shown.bs.tooltip");

    expect(managedTrigger().hasAttribute("aria-describedby")).toBe(false);
    expect(managedTrigger().getAttribute("aria-label")).toBe("Delete UTub");
    expect(
      document.querySelector("#tooltipBubble")?.getAttribute("aria-hidden"),
    ).toBe("true");
  });

  it("leaves a nudge anchor's aria-describedby alone", async () => {
    const { $ } = await import("../globals.js");
    simulateNudgeShowTip();
    nudgeAnchor().setAttribute("aria-describedby", "tooltipBubble");

    $(nudgeAnchor()).trigger("shown.bs.tooltip");

    expect(nudgeAnchor().getAttribute("aria-describedby")).toBe("tooltipBubble");
    expect(
      document.querySelector("#tooltipBubble")?.hasAttribute("aria-hidden"),
    ).toBe(false);
  });

  it("shows the tooltip when the button takes keyboard focus", async () => {
    const { $ } = await import("../globals.js");
    vi.spyOn(managedTrigger(), "matches").mockImplementation(
      (selector: string) => selector === ":focus-visible",
    );

    $(managedTrigger()).trigger("focusin");

    expect(tooltipInstance.show).toHaveBeenCalledTimes(1);
  });

  it("shows nothing for click-focus, which is what a 'hover focus' trigger got wrong", async () => {
    const { $ } = await import("../globals.js");
    vi.spyOn(managedTrigger(), "matches").mockReturnValue(false);

    $(managedTrigger()).trigger("focusin");

    expect(tooltipInstance.show).not.toHaveBeenCalled();
  });

  it("hides the tooltip when focus leaves the button", async () => {
    const { $ } = await import("../globals.js");

    $(managedTrigger()).trigger("focusout");

    expect(tooltipInstance.hide).toHaveBeenCalledTimes(1);
  });

  it("never shows or hides a nudge anchor on focus", async () => {
    const { $ } = await import("../globals.js");
    simulateNudgeShowTip();
    vi.spyOn(nudgeAnchor(), "matches").mockImplementation(
      (selector: string) => selector === ":focus-visible",
    );

    $(nudgeAnchor()).trigger("focusin");
    $(nudgeAnchor()).trigger("focusout");

    expect(tooltipInstance.show).not.toHaveBeenCalled();
    expect(tooltipInstance.hide).not.toHaveBeenCalled();
  });

  it("binds nothing on a coarse-pointer device", async () => {
    const { _resetTooltipsForTests, initTooltips } =
      await import("../tooltips.js");
    const { $ } = await import("../globals.js");
    _resetTooltipsForTests();
    stubCoarsePointer(true);
    initTooltips();

    $(managedTrigger()).trigger("show.bs.tooltip");
    pressKey("Escape");
    $(managedTrigger()).trigger("focusout");

    expect(tooltipInstance.hide).not.toHaveBeenCalled();
  });

  it("still dismisses a bubble whose trigger was detached without being disposed", async () => {
    // The bubble is a `document.body` child, so it outlives its trigger. Escape
    // is the only thing left that can clear it.
    const { $ } = await import("../globals.js");
    const trigger = managedTrigger();

    $(trigger).trigger("show.bs.tooltip");
    trigger.remove();
    pressKey("Escape");

    expect(tooltipInstance.hide).toHaveBeenCalledTimes(1);
  });

  it("keeps the bubble up on focusout while the pointer is still on the button", async () => {
    // Tab in (bubble up), move the pointer onto the button, tab away: the hover
    // still owns the bubble and Bootstrap's own mouseleave will hide it later.
    const { $ } = await import("../globals.js");
    vi.spyOn(managedTrigger(), "matches").mockImplementation(
      (selector: string) => selector === ":hover",
    );

    $(managedTrigger()).trigger("focusout");

    expect(tooltipInstance.hide).not.toHaveBeenCalled();
  });

  it("suppresses the duplicate description synchronously on keyboard focus", async () => {
    // `show()` writes `aria-describedby` immediately but `shown` does not fire
    // until the 150ms fade ends — a screen reader announcing the newly-focused
    // button inside that window would otherwise still hear the name twice.
    const { $ } = await import("../globals.js");
    vi.spyOn(managedTrigger(), "matches").mockImplementation(
      (selector: string) => selector === ":focus-visible",
    );
    tooltipInstance.show.mockImplementation(() => {
      managedTrigger().setAttribute("aria-describedby", "tooltipBubble");
    });

    $(managedTrigger()).trigger("focusin");

    expect(managedTrigger().hasAttribute("aria-describedby")).toBe(false);
    expect(
      document.querySelector("#tooltipBubble")?.getAttribute("aria-hidden"),
    ).toBe("true");
  });

  it("keeps aria-describedby on a trigger that has no aria-label", async () => {
    // Without a label the description is the button's ONLY accessible name, so
    // stripping it would leave it anonymous.
    const { $ } = await import("../globals.js");
    managedTrigger().removeAttribute("aria-label");
    managedTrigger().setAttribute("aria-describedby", "tooltipBubble");

    $(managedTrigger()).trigger("shown.bs.tooltip");

    expect(managedTrigger().getAttribute("aria-describedby")).toBe(
      "tooltipBubble",
    );
  });

  it("does nothing when Bootstrap set no aria-describedby", async () => {
    const { $ } = await import("../globals.js");

    expect(() =>
      $(managedTrigger()).trigger("shown.bs.tooltip"),
    ).not.toThrow();
    expect(
      document.querySelector("#tooltipBubble")?.hasAttribute("aria-hidden"),
    ).toBe(false);
  });

  it("treats an unsupported :focus-visible selector as no match instead of throwing", async () => {
    // Older engines (and happy-dom) can reject the pseudo-class outright; a11y
    // sugar must never take the page down with it.
    const { $ } = await import("../globals.js");
    vi.spyOn(managedTrigger(), "matches").mockImplementation(() => {
      throw new SyntaxError("unknown pseudo-class :focus-visible");
    });

    expect(() => $(managedTrigger()).trigger("focusin")).not.toThrow();
    expect(tooltipInstance.show).not.toHaveBeenCalled();
  });

  it("does not re-show after a keyboard activation hid the bubble", async () => {
    // Enter/Space fires the trigger's own click-hide guard while focus STAYS on
    // the button and `:focus-visible` stays true — nothing may fight the guard
    // by re-showing, because no fresh `focusin` ever arrives.
    const { $ } = await import("../globals.js");
    vi.spyOn(managedTrigger(), "matches").mockImplementation(
      (selector: string) => selector === ":focus-visible",
    );

    $(managedTrigger()).trigger("focusin");
    expect(tooltipInstance.show).toHaveBeenCalledTimes(1);

    // The click-hide guard fires, Bootstrap hides, focus never left.
    $(managedTrigger()).trigger("hide.bs.tooltip");

    expect(tooltipInstance.show).toHaveBeenCalledTimes(1);
  });

  it("binds the handlers on a page where only applyHoverTooltip ran", async () => {
    // The reason the handler guard is separate from the sweep guard: a page can
    // have nothing for `initTooltips()` to instantiate and still build
    // per-card triggers later.
    const { _resetTooltipsForTests, applyHoverTooltip } =
      await import("../tooltips.js");
    const { $ } = await import("../globals.js");
    _resetTooltipsForTests();
    document.body.innerHTML = `<button id="urlTagBtnDelete"></button>`;

    applyHoverTooltip({
      btn: $("#urlTagBtnDelete"),
      tooltip: { title: "Remove tag", customClass: "urlTagBtnDelete-tooltip" },
    });
    $("#urlTagBtnDelete").trigger("show.bs.tooltip");
    pressKey("Escape");

    expect(tooltipInstance.hide).toHaveBeenCalledTimes(1);
  });
});
