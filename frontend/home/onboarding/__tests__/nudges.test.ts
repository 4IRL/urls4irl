import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppEvents, emit as emitBusEvent } from "../../../lib/event-bus.js";
import type { UtubSelectedPayload } from "../../../lib/event-bus.js";
import { getOpenForm } from "../../../lib/modal-tracking.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";
import { resetStore, setState } from "../../../store/app-store.js";
import type { UtubSummaryItem } from "../../../types/utub.js";
import { isCrossUtubSearchActive } from "../../search/cross-utub-search.js";
import { isUTubSearchActive } from "../../utubs/search.js";
import * as nudgeStorage from "../nudge-storage.js";

// Canonical metrics-client mock (copied verbatim from `copy-metrics.test.ts`):
// hoist the helper above the ESM imports so the `vi.mock` factory can use it.
const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

// Resettable in-memory event-bus mock (mirrors swipe.test.ts): `on`/`emit`
// operate against a registry the Step 6 suite clears in beforeEach, so
// initOnboardingNudges() subscriptions never accumulate across tests and
// emitting drives the real registry/sequencing logic. `AppEvents` mirrors the
// real event-bus.ts values so emit(UTUB_SELECTED)/emit(MOBILE_DECK_SWITCHED)
// reach the subscribers.
const { busHandlers, resetBus } = vi.hoisted(() => {
  const handlers = new Map<string, Set<(payload: unknown) => void>>();
  return { busHandlers: handlers, resetBus: (): void => handlers.clear() };
});

vi.mock("../../../lib/event-bus.js", () => ({
  AppEvents: {
    UTUB_SELECTED: "utub:selected",
    MOBILE_DECK_SWITCHED: "mobile:deck-switched",
  },
  on: vi.fn((event: string, handler: (payload: unknown) => void) => {
    if (!busHandlers.has(event)) busHandlers.set(event, new Set());
    busHandlers.get(event)!.add(handler);
    return (): void => {
      busHandlers.get(event)?.delete(handler);
    };
  }),
  emit: vi.fn((event: string, payload: unknown) => {
    busHandlers.get(event)?.forEach((handler) => handler(payload));
  }),
}));

// Config mock: expose a mutable APP_CONFIG so the `?resetNudges` tests can flip
// `isProduction` between the enabled (non-prod) and disabled (prod) paths.
// nudges.ts is the only module in this test's graph that reads config; the
// onboarding string keys read by showTip() are mirrored from test-setup.ts.
const { mockAppConfig } = vi.hoisted(() => ({
  mockAppConfig: {
    debugEnabled: true,
    isProduction: false,
    strings: {
      ONBOARDING_CREATE_UTUB_TIP_TITLE: "Start here",
      ONBOARDING_CREATE_UTUB_TIP_BODY:
        "Create your first UTub to begin collecting URLs.",
      ONBOARDING_ADD_URL_TIP_TITLE: "Add a URL",
      ONBOARDING_ADD_URL_TIP_BODY:
        "Tap here to save your first link to this UTub.",
    } as Record<string, string>,
  },
}));

vi.mock("../../../lib/config.js", () => ({ APP_CONFIG: mockAppConfig }));

// Form/search suppression predicates mocked so Step 6 tests toggle them
// deterministically; default to "not suppressing" so tips can show.
vi.mock("../../../lib/modal-tracking.js", () => ({
  getOpenForm: vi.fn(() => null),
}));
vi.mock("../../utubs/search.js", () => ({
  isUTubSearchActive: vi.fn(() => false),
}));
vi.mock("../../search/cross-utub-search.js", () => ({
  isCrossUtubSearchActive: vi.fn(() => false),
}));

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

  it("(metrics) showTip emits UI_ONBOARDING_TIP_SHOWN with the tip_id", async () => {
    const { showTip } = await import("../nudges.js");
    const { emit } = await import("../../../lib/metrics-client.js");

    showTip(CREATE_UTUB_TIP);

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_ONBOARDING_TIP_SHOWN,
      tip_id: "createUtub",
    });
  });

  it("(metrics) showTip carries the addUrl tip_id through to the SHOWN event", async () => {
    const { showTip } = await import("../nudges.js");
    const { emit } = await import("../../../lib/metrics-client.js");

    // Cover the second closed-set tip_id value (the createUtub anchor is reused;
    // only the emitted dimension value matters here).
    showTip({ ...CREATE_UTUB_TIP, tipId: "addUrl" });

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_ONBOARDING_TIP_SHOWN,
      tip_id: "addUrl",
    });
  });

  it("(metrics) a user-driven dismiss emits UI_ONBOARDING_TIP_DISMISSED with the tip_id", async () => {
    const { showTip } = await import("../nudges.js");
    const { emit } = await import("../../../lib/metrics-client.js");
    const anchor = document.querySelector("#utubBtnCreate") as HTMLElement;

    showTip(CREATE_UTUB_TIP);
    await flushDeferredBind();
    window.jQuery(anchor).trigger("click");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_ONBOARDING_TIP_DISMISSED,
      tip_id: "createUtub",
    });
  });

  it("(metrics, invariant) an environment-driven dismiss does NOT emit UI_ONBOARDING_TIP_DISMISSED", async () => {
    const { showTip } = await import("../nudges.js");
    const { emit } = await import("../../../lib/metrics-client.js");

    showTip(CREATE_UTUB_TIP);
    // A second show before any user dismiss tears down the prior tip with
    // markSeen:false (environment-style teardown) — it must NOT emit dismissed.
    showTip({ ...CREATE_UTUB_TIP, tipId: "addUrl" });

    expect(emit).not.toHaveBeenCalledWith(
      expect.objectContaining({
        event: UI_EVENTS.UI_ONBOARDING_TIP_DISMISSED,
      }),
    );
  });
});

describe("onboarding nudges — registry, eligibility, sequencing & init wiring", () => {
  const A_UTUB: UtubSummaryItem = {
    id: 1,
    name: "My UTub",
    memberRole: "member",
    isLocked: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    resetBus();
    resetStore();
    installStorageStub();
    // Default to the non-prod path (the #resetNudges hook enabled); the prod
    // invariant test flips this to true. Reset here so it never leaks across
    // tests (clearAllMocks does not touch this plain object).
    mockAppConfig.isProduction = false;
    document.body.innerHTML = `<button id="utubBtnCreate"></button><button id="urlBtnCreate"></button>`;
    // Re-assert the default "not suppressing" return values: clearAllMocks wipes
    // call history but preserves implementations, so a prior test's
    // mockReturnValue override would otherwise leak into this test.
    vi.mocked(getOpenForm).mockReturnValue(null);
    vi.mocked(isUTubSearchActive).mockReturnValue(false);
    vi.mocked(isCrossUtubSearchActive).mockReturnValue(false);
  });

  afterEach(async () => {
    const { _resetOnboardingNudgesForTests } = await import("../nudges.js");
    _resetOnboardingNudgesForTests();
    resetStore();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    document.body.innerHTML = "";
    // Restore a clean URL so a lingering #resetNudges hash never bleeds into
    // the next test.
    window.history.replaceState({}, "", "/");
  });

  it("(Red 1) initOnboardingNudges shows the Create-UTub tip in the zero-UTub state, gated on anchor visibility", async () => {
    const { initOnboardingNudges, _resetOnboardingNudgesForTests } =
      await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);

    // (a) Visible anchor (happy-dom default offsetParent) → the tip shows.
    initOnboardingNudges();
    expect(tip.show).toHaveBeenCalledTimes(1);
    const contentArg = (tip.setContent as ReturnType<typeof vi.fn>).mock
      .calls[0][0] as Record<string, string>;
    expect(contentArg[".tooltip-inner"]).toContain("Start here");

    // (b) Same anchor with offsetParent forced null → not visible → no show.
    _resetOnboardingNudgesForTests();
    vi.clearAllMocks();
    Object.defineProperty(anchor, "offsetParent", {
      value: null,
      configurable: true,
    });
    initOnboardingNudges();
    expect(tip.show).not.toHaveBeenCalled();
  });

  it("(Red 2) selecting a URL-less UTub advances to the Add-URL tip via UTUB_SELECTED", async () => {
    const { initOnboardingNudges } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#urlBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);

    // A UTub already exists (Create tip not eligible) but none is selected yet,
    // so init shows nothing.
    setState({ utubs: [A_UTUB], activeUTubID: null });
    initOnboardingNudges();
    expect(tip.show).not.toHaveBeenCalled();

    // Selecting the (URL-less) UTub advances to the Add-URL tip.
    nudgeStorage.markTipSeen("createUtub");
    setState({ activeUTubID: 1, urls: [] });
    // The sequencing subscriber ignores the event payload (it re-reads
    // app-store state), so the payload content is irrelevant here — cast an
    // empty object to satisfy the real typed `emit` signature.
    emitBusEvent(AppEvents.UTUB_SELECTED, {} as UtubSelectedPayload);

    expect(tip.show).toHaveBeenCalledTimes(1);
    const contentArg = (tip.setContent as ReturnType<typeof vi.fn>).mock
      .calls[0][0] as Record<string, string>;
    expect(contentArg[".tooltip-inner"]).toContain("Add a URL");
  });

  it("(Red 3, regression) with both tips already seen, init shows nothing", async () => {
    const { initOnboardingNudges } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);

    nudgeStorage.markTipSeen("createUtub");
    nudgeStorage.markTipSeen("addUrl");
    initOnboardingNudges();

    expect(tip.show).not.toHaveBeenCalled();
  });

  it("(Red 4) multi-select mode or an open form suppresses the Add-URL tip", async () => {
    const { initOnboardingNudges, _resetOnboardingNudgesForTests } =
      await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#urlBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);

    // Add-URL-eligible baseline (Create tip already seen).
    nudgeStorage.markTipSeen("createUtub");
    setState({
      utubs: [A_UTUB],
      activeUTubID: 1,
      urls: [],
      multiSelectMode: true,
    });

    // Multi-select on → suppressed.
    initOnboardingNudges();
    expect(tip.show).not.toHaveBeenCalled();

    // Multi-select off but a home form open → still suppressed.
    _resetOnboardingNudgesForTests();
    nudgeStorage.markTipSeen("createUtub"); // _reset cleared seen state
    setState({ multiSelectMode: false });
    vi.mocked(getOpenForm).mockReturnValue("url_create");
    initOnboardingNudges();
    expect(tip.show).not.toHaveBeenCalled();
  });

  it("(Red 5) an active UTub-name or cross-UTub search suppresses the Add-URL tip", async () => {
    const { initOnboardingNudges, _resetOnboardingNudgesForTests } =
      await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#urlBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);

    nudgeStorage.markTipSeen("createUtub");
    setState({ utubs: [A_UTUB], activeUTubID: 1, urls: [] });

    // UTub-name search active → suppressed.
    vi.mocked(isUTubSearchActive).mockReturnValue(true);
    initOnboardingNudges();
    expect(tip.show).not.toHaveBeenCalled();

    // Cross-UTub search active → suppressed.
    _resetOnboardingNudgesForTests();
    nudgeStorage.markTipSeen("createUtub");
    vi.mocked(isUTubSearchActive).mockReturnValue(false);
    vi.mocked(isCrossUtubSearchActive).mockReturnValue(true);
    initOnboardingNudges();
    expect(tip.show).not.toHaveBeenCalled();
  });

  it("(Red 6) MOBILE_DECK_SWITCHED away from the active tip's anchor tears it down WITHOUT marking it seen", async () => {
    const { initOnboardingNudges } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);
    const markTipSeenSpy = vi.spyOn(nudgeStorage, "markTipSeen");

    // Zero-UTub state shows the Create tip on init.
    initOnboardingNudges();
    expect(tip.show).toHaveBeenCalledTimes(1);

    // The Create anchor goes off-panel (offsetParent null) and a deck switch
    // fires: the tip is torn down, but NOT marked seen, so it can re-show later.
    Object.defineProperty(anchor, "offsetParent", {
      value: null,
      configurable: true,
    });
    emitBusEvent(AppEvents.MOBILE_DECK_SWITCHED, { target: "url-deck" });

    expect(tip.dispose).toHaveBeenCalledTimes(1);
    expect(markTipSeenSpy).not.toHaveBeenCalled();
    expect(nudgeStorage.hasSeenTip("createUtub")).toBe(false);
  });

  it("(Green 3 teardown) a suppression condition arising while a tip is active tears it down WITHOUT marking it seen", async () => {
    const { initOnboardingNudges } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);
    const markTipSeenSpy = vi.spyOn(nudgeStorage, "markTipSeen");

    // Zero-UTub state shows the Create tip on init.
    initOnboardingNudges();
    expect(tip.show).toHaveBeenCalledTimes(1);

    // A home form opens, then a re-evaluation fires (its anchor is still on the
    // current panel, so the off-panel teardown branch does not apply). The
    // suppression guard must tear the active tip down WITHOUT marking it seen,
    // so it can re-show once the form closes.
    vi.mocked(getOpenForm).mockReturnValue("url_create");
    emitBusEvent(AppEvents.MOBILE_DECK_SWITCHED, { target: "utub-deck" });

    expect(tip.dispose).toHaveBeenCalledTimes(1);
    expect(markTipSeenSpy).not.toHaveBeenCalled();
    expect(nudgeStorage.hasSeenTip("createUtub")).toBe(false);
  });

  it("(resetNudges, non-prod) #resetNudges clears seen flags, re-shows the eligible tip, and strips the hash", async () => {
    const { initOnboardingNudges } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);

    // Pre-seed the Create tip as already seen, then load with #resetNudges.
    nudgeStorage.markTipSeen("createUtub");
    expect(nudgeStorage.hasSeenTip("createUtub")).toBe(true);
    window.history.replaceState({}, "", "/#resetNudges");
    const replaceStateSpy = vi.spyOn(window.history, "replaceState");

    initOnboardingNudges();

    // The seen flag was cleared, so the zero-UTub Create tip re-shows.
    expect(nudgeStorage.hasSeenTip("createUtub")).toBe(false);
    expect(tip.show).toHaveBeenCalledTimes(1);
    const contentArg = (tip.setContent as ReturnType<typeof vi.fn>).mock
      .calls[0][0] as Record<string, string>;
    expect(contentArg[".tooltip-inner"]).toContain("Start here");

    // The hash is stripped from the URL so a reload does not re-reset.
    expect(replaceStateSpy).toHaveBeenCalledTimes(1);
    expect(window.location.hash).toBe("");
  });

  it("(resetNudges, prod invariant) #resetNudges is inert in production", async () => {
    const { initOnboardingNudges } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);

    mockAppConfig.isProduction = true;
    nudgeStorage.markTipSeen("createUtub");
    window.history.replaceState({}, "", "/#resetNudges");

    initOnboardingNudges();

    // In production the hook no-ops: the seen flag survives and the (still-seen)
    // Create tip is not re-shown.
    expect(nudgeStorage.hasSeenTip("createUtub")).toBe(true);
    expect(tip.show).not.toHaveBeenCalled();
  });

  it("(resetNudges, no-op) without the hash the seen flag is preserved", async () => {
    const { initOnboardingNudges } = await import("../nudges.js");

    nudgeStorage.markTipSeen("createUtub");
    window.history.replaceState({}, "", "/");

    initOnboardingNudges();

    expect(nudgeStorage.hasSeenTip("createUtub")).toBe(true);
  });
});
