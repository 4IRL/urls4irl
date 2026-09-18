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
    const getInstance = bootstrap.Tooltip
      .getInstance as unknown as ReturnType<typeof vi.fn>;
    getInstance.mockImplementation((element: HTMLElement) =>
      element.id === "urlBtnAccess" ? liveInstance : null,
    );

    disposeTooltipsWithin($("#URLFocusRow"));

    expect(liveInstance.dispose).toHaveBeenCalledTimes(1);
    expect(
      getInstance.mock.calls.map((call) => (call[0] as HTMLElement).id),
    ).toEqual(["urlBtnAccess", "urlBtnDelete"]);
  });
});
