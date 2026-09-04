import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as nudgeStorage from "../nudge-storage.js";

// Per-file globals mock: a single shared Tooltip spy instance returned by
// getOrCreateInstance so every showTip() call operates on the same spy. Copied
// from `copy-metrics.test.ts`; `setContent`/`dispose` are added explicitly (the
// global `test-setup.ts` Tooltip mock has `dispose()` but lacks `setContent`).
vi.mock("../../../lib/globals.js", async () => {
  const jquery = (await import("jquery")).default;
  const tooltipInstance = {
    setContent: vi.fn(),
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

// Map-backed localStorage stub (same pattern as `nudge-storage.test.ts`) so the
// real `markTipSeen`/`hasSeenTip` exercised through the nudge engine read/write
// against an in-memory store rather than the ambient (undefined-in-happy-dom)
// localStorage.
function installStorageStub(): void {
  const data = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (key: string): string | null => data.get(key) ?? null,
    setItem: (key: string, value: string): void => {
      data.set(key, String(value));
    },
    removeItem: (key: string): void => {
      data.delete(key);
    },
    clear: (): void => {
      data.clear();
    },
  });
}

// Flush the one-tick deferred listener bind that showTip() schedules.
async function flushDeferredBind(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
}

const CREATE_UTUB_TIP = {
  tipId: "createUtub" as const,
  anchorSelector: "#utubBtnCreate",
  titleKey: "ONBOARDING_CREATE_UTUB_TIP_TITLE",
  bodyKey: "ONBOARDING_CREATE_UTUB_TIP_BODY",
};

describe("onboarding nudges — show / act-or-tap-away dismiss / a11y", () => {
  let markTipSeenSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    // Reset the shared Tooltip spy's call counters between tests (the mock
    // factory's single tooltipInstance persists across the whole file).
    vi.clearAllMocks();
    installStorageStub();
    document.body.innerHTML = `<button id="utubBtnCreate"></button>`;
    // Keep the real read/write behavior intact (no mockImplementation) so the
    // seen-flag is genuinely persisted; assertions use the spy's call record.
    markTipSeenSpy = vi.spyOn(nudgeStorage, "markTipSeen");
  });

  afterEach(async () => {
    const { _resetOnboardingNudgesForTests } = await import("../nudges.js");
    _resetOnboardingNudgesForTests();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    document.body.innerHTML = "";
  });

  it("(Red 1) showTip sets the bridged strings and shows the tooltip", async () => {
    const { showTip } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubBtnCreate") as HTMLElement;

    showTip(CREATE_UTUB_TIP);

    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);
    expect(tip.setContent).toHaveBeenCalledTimes(1);
    const contentArg = (tip.setContent as ReturnType<typeof vi.fn>).mock
      .calls[0][0] as Record<string, string>;
    expect(contentArg[".tooltip-inner"]).toContain("Start here");
    expect(contentArg[".tooltip-inner"]).toContain(
      "Create your first UTub to begin collecting URLs.",
    );
    expect(tip.show).toHaveBeenCalledTimes(1);
  });

  it("(Red 2) showTip on a missing anchor is a no-op", async () => {
    const { showTip } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    document.body.innerHTML = ""; // remove the anchor

    showTip(CREATE_UTUB_TIP);

    const tooltipInstance = bootstrap.Tooltip.getOrCreateInstance(
      document.createElement("button"),
    );
    expect(tooltipInstance.show).not.toHaveBeenCalled();
  });

  it("(Red 3a) a click fired before the deferred bind does NOT self-dismiss", async () => {
    const { showTip } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubBtnCreate") as HTMLElement;

    showTip(CREATE_UTUB_TIP);
    // Synchronous click on the anchor, before the setTimeout(0) bind fires.
    window.jQuery(anchor).trigger("click");

    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);
    expect(tip.dispose).not.toHaveBeenCalled();
    expect(markTipSeenSpy).not.toHaveBeenCalled();
  });

  it("(Red 3b) a click on the anchor after bind hides+disposes and marks seen", async () => {
    const { showTip } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubBtnCreate") as HTMLElement;

    showTip(CREATE_UTUB_TIP);
    await flushDeferredBind();
    window.jQuery(anchor).trigger("click");

    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);
    expect(tip.hide).toHaveBeenCalledTimes(1);
    expect(tip.dispose).toHaveBeenCalledTimes(1);
    expect(markTipSeenSpy).toHaveBeenCalledWith("createUtub");
  });

  it("(Red 4) a click elsewhere dismisses the tip and marks it seen", async () => {
    const { showTip } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubBtnCreate") as HTMLElement;

    showTip(CREATE_UTUB_TIP);
    await flushDeferredBind();
    window.jQuery(document.body).trigger("click");

    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);
    expect(tip.dispose).toHaveBeenCalledTimes(1);
    expect(markTipSeenSpy).toHaveBeenCalledWith("createUtub");
  });

  it("(Red 5) Escape dismisses the tip and marks it seen", async () => {
    const { showTip } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubBtnCreate") as HTMLElement;

    showTip(CREATE_UTUB_TIP);
    await flushDeferredBind();
    window
      .jQuery(document)
      .trigger(window.jQuery.Event("keydown", { key: "Escape" }));

    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);
    expect(tip.dispose).toHaveBeenCalledTimes(1);
    expect(markTipSeenSpy).toHaveBeenCalledWith("createUtub");
  });

  it("(Red 5b) a non-Escape keydown does NOT dismiss the tip", async () => {
    const { showTip } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubBtnCreate") as HTMLElement;

    showTip(CREATE_UTUB_TIP);
    await flushDeferredBind();
    window
      .jQuery(document)
      .trigger(window.jQuery.Event("keydown", { key: "Enter" }));

    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);
    expect(tip.dispose).not.toHaveBeenCalled();
    expect(markTipSeenSpy).not.toHaveBeenCalled();
  });

  it("(re-show) showTip while a tip is active tears down the prior tip without marking it seen", async () => {
    const { showTip } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubBtnCreate") as HTMLElement;

    showTip(CREATE_UTUB_TIP);
    // Second show before any dismiss: the prior tip must be disposed once, and
    // NOT marked seen (environment-style teardown so it can re-show later).
    showTip({ ...CREATE_UTUB_TIP, tipId: "addUrl" });

    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);
    expect(tip.dispose).toHaveBeenCalledTimes(1);
    expect(markTipSeenSpy).not.toHaveBeenCalled();
    expect(tip.show).toHaveBeenCalledTimes(2);
  });

  it("(Red 6, invariant) the seen flag is NOT written on show, only on dismiss", async () => {
    const { showTip } = await import("../nudges.js");

    showTip(CREATE_UTUB_TIP);

    expect(markTipSeenSpy).not.toHaveBeenCalled();
  });
});
