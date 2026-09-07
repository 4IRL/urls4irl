import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppEvents, emit as emitBusEvent } from "../../../lib/event-bus.js";
import type { UtubSelectedPayload } from "../../../lib/event-bus.js";
import { getOpenForm } from "../../../lib/modal-tracking.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";
import { resetStore, setState } from "../../../store/app-store.js";
import type { MemberItem } from "../../../types/member.js";
import type { UtubTag, UtubUrlItem } from "../../../types/url.js";
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
    UTUB_DELETED: "utub:deleted",
    URL_DECK_CHANGED: "url:deck-changed",
    MOBILE_DECK_SWITCHED: "mobile:deck-switched",
    MEMBER_DECK_CHANGED: "member:deck-changed",
    TAG_DECK_CHANGED: "tag:deck-changed",
    TAG_SHEET_TOGGLED: "tag-sheet:toggled",
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
      ONBOARDING_ADD_TAG_TIP_TITLE: "Tag your links",
      ONBOARDING_ADD_TAG_TIP_BODY:
        "Add a tag to group and find URLs in this UTub.",
      ONBOARDING_ADD_MEMBER_TIP_TITLE: "Invite a member",
      ONBOARDING_ADD_MEMBER_TIP_BODY:
        "Add a member to share this UTub and gather links together.",
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
    // Popper reposition hook: the TAG_SHEET_TOGGLED retry loop calls this on each
    // tick after the tip is shown so the bubble tracks the still-sliding sheet
    // anchor. A no-op spy here (the real Bootstrap Tooltip.update drives Popper).
    update: vi.fn(),
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

const ADD_TAG_TIP = {
  tipId: "addTag" as const,
  anchorSelector: "#utubTagBtnCreate",
  titleKey: "ONBOARDING_ADD_TAG_TIP_TITLE",
  bodyKey: "ONBOARDING_ADD_TAG_TIP_BODY",
};

const ADD_MEMBER_TIP = {
  tipId: "addMember" as const,
  anchorSelector: "#memberBtnCreate",
  titleKey: "ONBOARDING_ADD_MEMBER_TIP_TITLE",
  bodyKey: "ONBOARDING_ADD_MEMBER_TIP_BODY",
};

describe("onboarding nudges — show / act-or-tap-away dismiss / a11y", () => {
  let markTipSeenSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    // Reset the shared Tooltip spy's call counters between tests (the mock
    // factory's single tooltipInstance persists across the whole file).
    vi.clearAllMocks();
    installStorageStub();
    // Include the shared visually-hidden aria-live region (mirrors
    // `pages/home.html`) so showTip()'s announcer write has a real target.
    document.body.innerHTML = `<button id="utubBtnCreate"></button><button id="utubTagBtnCreate"></button><button id="memberBtnCreate"></button><span id="onboardingNudgeAnnouncement"></span>`;
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

  it("(a11y) showTip announces the tip title+body via the visually-hidden live region", async () => {
    const { showTip } = await import("../nudges.js");

    showTip(CREATE_UTUB_TIP);

    // showTip writes `${title}. ${body}` into #onboardingNudgeAnnouncement for
    // screen readers (without moving focus). Assert the announced text directly.
    expect(
      document.querySelector("#onboardingNudgeAnnouncement")?.textContent,
    ).toBe("Start here. Create your first UTub to begin collecting URLs.");
  });

  it("(missing copy guard) showTip skips (no show, no metric) when a bridged string resolves falsy", async () => {
    const { showTip } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const { emit } = await import("../../../lib/metrics-client.js");
    const anchor = document.querySelector("#utubBtnCreate") as HTMLElement;

    // `APP_CONFIG.strings` is a `Record<string, string>`, so a mis-bridged/typo'd
    // key resolves to runtime-undefined/blank with no compile error. Blank one
    // key and assert showTip bails loudly instead of seeding "undefined" copy.
    const originalTitle =
      mockAppConfig.strings.ONBOARDING_CREATE_UTUB_TIP_TITLE;
    mockAppConfig.strings.ONBOARDING_CREATE_UTUB_TIP_TITLE = "";
    try {
      showTip(CREATE_UTUB_TIP);
    } finally {
      mockAppConfig.strings.ONBOARDING_CREATE_UTUB_TIP_TITLE = originalTitle;
    }

    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);
    expect(tip.show).not.toHaveBeenCalled();
    expect(emit).not.toHaveBeenCalledWith(
      expect.objectContaining({ event: UI_EVENTS.UI_ONBOARDING_TIP_SHOWN }),
    );
  });

  it("(caret inset) showTip pulls the caret in by half the box/icon width gap", async () => {
    const { showTip } = await import("../nudges.js");
    const anchor = document.querySelector("#utubBtnCreate") as HTMLElement;

    // Simulate a coarse-pointer tap target: a 44px box with a 30px centred icon.
    // The caret should pull in along the main axis by round((44 - 30) / 2) = 7.
    anchor.innerHTML = "<svg></svg>";
    const icon = anchor.querySelector("svg") as SVGElement;
    anchor.getBoundingClientRect = vi.fn(() => ({ width: 44 }) as DOMRect);
    icon.getBoundingClientRect = vi.fn(() => ({ width: 30 }) as DOMRect);

    showTip(CREATE_UTUB_TIP);

    expect(anchor.getAttribute("data-bs-offset")).toBe("0,-7");
  });

  it("(addTag primitive) showTip sets the addTag copy, shows, and emits SHOWN with tip_id addTag", async () => {
    const { showTip } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const { emit } = await import("../../../lib/metrics-client.js");
    const anchor = document.querySelector("#utubTagBtnCreate") as HTMLElement;

    showTip(ADD_TAG_TIP);

    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);
    const contentArg = (tip.setContent as ReturnType<typeof vi.fn>).mock
      .calls[0][0] as Record<string, string>;
    expect(contentArg[".tooltip-inner"]).toContain("Tag your links");
    expect(contentArg[".tooltip-inner"]).toContain(
      "Add a tag to group and find URLs in this UTub.",
    );
    expect(tip.show).toHaveBeenCalledTimes(1);
    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_ONBOARDING_TIP_SHOWN,
      tip_id: "addTag",
    });
  });

  it("(addMember primitive) showTip sets the addMember copy, shows, and emits SHOWN with tip_id addMember", async () => {
    const { showTip } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const { emit } = await import("../../../lib/metrics-client.js");
    const anchor = document.querySelector("#memberBtnCreate") as HTMLElement;

    showTip(ADD_MEMBER_TIP);

    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);
    const contentArg = (tip.setContent as ReturnType<typeof vi.fn>).mock
      .calls[0][0] as Record<string, string>;
    expect(contentArg[".tooltip-inner"]).toContain("Invite a member");
    expect(contentArg[".tooltip-inner"]).toContain(
      "Add a member to share this UTub and gather links together.",
    );
    expect(tip.show).toHaveBeenCalledTimes(1);
    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_ONBOARDING_TIP_SHOWN,
      tip_id: "addMember",
    });
  });

  it("(addTag primitive) a user-driven dismiss emits DISMISSED with tip_id addTag", async () => {
    const { showTip } = await import("../nudges.js");
    const { emit } = await import("../../../lib/metrics-client.js");
    const anchor = document.querySelector("#utubTagBtnCreate") as HTMLElement;

    showTip(ADD_TAG_TIP);
    await flushDeferredBind();
    window.jQuery(anchor).trigger("click");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_ONBOARDING_TIP_DISMISSED,
      tip_id: "addTag",
    });
  });

  it("(addMember primitive) a user-driven dismiss emits DISMISSED with tip_id addMember", async () => {
    const { showTip } = await import("../nudges.js");
    const { emit } = await import("../../../lib/metrics-client.js");
    const anchor = document.querySelector("#memberBtnCreate") as HTMLElement;

    showTip(ADD_MEMBER_TIP);
    await flushDeferredBind();
    window.jQuery(anchor).trigger("click");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_ONBOARDING_TIP_DISMISSED,
      tip_id: "addMember",
    });
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
    document.body.innerHTML = `<button id="utubBtnCreate"></button><button id="urlBtnCreate"></button><button id="utubTagBtnCreate"></button><button id="memberBtnCreate"></button>`;
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

  it("(re-arm) leaving the empty state clears a seen tip's flag", async () => {
    const { initOnboardingNudges } = await import("../nudges.js");

    // Create-UTub tip already dismissed; init while still empty must NOT re-arm.
    nudgeStorage.markTipSeen("createUtub");
    initOnboardingNudges();
    expect(nudgeStorage.hasSeenTip("createUtub")).toBe(true);

    // The user creates + selects a UTub (leaves the zero-UTub empty state). The
    // re-eval re-arms the now-content-bearing Create-UTub tip.
    setState({ utubs: [A_UTUB], activeUTubID: 1, urls: [] });
    emitBusEvent(AppEvents.UTUB_SELECTED, {} as UtubSelectedPayload);

    expect(nudgeStorage.hasSeenTip("createUtub")).toBe(false);
  });

  it("(re-show after emptying) deleting the last UTub re-shows the Create-UTub tip", async () => {
    const { initOnboardingNudges } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);

    // A UTub exists (none selected), Create tip previously dismissed. Init
    // re-arms it (deck has content) but shows nothing (no eligible tip here).
    nudgeStorage.markTipSeen("createUtub");
    setState({ utubs: [A_UTUB], activeUTubID: null, urls: [] });
    initOnboardingNudges();
    expect(tip.show).not.toHaveBeenCalled();
    expect(nudgeStorage.hasSeenTip("createUtub")).toBe(false);

    // Deleting the last UTub returns to the zero-UTub empty state: the re-armed
    // (now unseen) Create tip becomes eligible again and re-shows.
    setState({ utubs: [], activeUTubID: null, urls: [] });
    emitBusEvent(AppEvents.UTUB_DELETED, { utubID: 1 });

    expect(tip.show).toHaveBeenCalledTimes(1);
    const contentArg = (tip.setContent as ReturnType<typeof vi.fn>).mock
      .calls[0][0] as Record<string, string>;
    expect(contentArg[".tooltip-inner"]).toContain("Start here");
  });

  it("(addUrl re-arm) leaving then re-emptying the URL deck re-shows the Add-URL tip", async () => {
    const { initOnboardingNudges } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#urlBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);
    const A_URL = { utubUrlID: 1 } as unknown as UtubUrlItem;

    // Both tips previously dismissed; init in the zero-UTub state shows nothing
    // and (empty decks) re-arms nothing. addTag is also marked seen to isolate
    // the Add-URL tip: a UTub with a URL but no tags is now addTag-eligible, so
    // without this the higher-priority-consumed slot would show addTag instead.
    // addTag never re-arms here (its deck stays tag-empty → hasContent false).
    nudgeStorage.markTipSeen("createUtub");
    nudgeStorage.markTipSeen("addUrl");
    nudgeStorage.markTipSeen("addTag");
    initOnboardingNudges();
    expect(tip.show).not.toHaveBeenCalled();

    // The user opens a UTub that has a URL (leaves the empty URL deck): the
    // Add-URL tip is re-armed.
    setState({ utubs: [A_UTUB], activeUTubID: 1, urls: [A_URL] });
    emitBusEvent(AppEvents.UTUB_SELECTED, {} as UtubSelectedPayload);
    expect(nudgeStorage.hasSeenTip("addUrl")).toBe(false);

    // Emptying that UTub's URLs re-enters the empty state → the re-armed Add-URL
    // tip re-shows.
    setState({ urls: [] });
    emitBusEvent(AppEvents.UTUB_SELECTED, {} as UtubSelectedPayload);

    expect(tip.show).toHaveBeenCalledTimes(1);
    const contentArg = (tip.setContent as ReturnType<typeof vi.fn>).mock
      .calls[0][0] as Record<string, string>;
    expect(contentArg[".tooltip-inner"]).toContain("Add a URL");
  });

  it("(URL_DECK_CHANGED re-show instant) deleting the last URL re-shows the Add-URL tip immediately", async () => {
    const { initOnboardingNudges } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#urlBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);
    const A_URL = { utubUrlID: 1 } as unknown as UtubUrlItem;

    // Add-URL tip re-armed (flag cleared) and the active UTub currently holds a
    // URL, so init shows nothing (not eligible while the deck is non-empty).
    // addTag is marked seen to isolate Add-URL: a URL-bearing, tag-empty UTub is
    // now addTag-eligible, which would otherwise show on init.
    nudgeStorage.markTipSeen("createUtub");
    nudgeStorage.markTipSeen("addTag");
    setState({ utubs: [A_UTUB], activeUTubID: 1, urls: [A_URL] });
    initOnboardingNudges();
    expect(tip.show).not.toHaveBeenCalled();

    // Deleting the last URL empties the deck; the store-mutating site emits
    // URL_DECK_CHANGED (emit-after-setState), so the Add-URL tip re-shows live —
    // no UTub re-selection or reload needed.
    setState({ urls: [] });
    emitBusEvent(AppEvents.URL_DECK_CHANGED);

    expect(tip.show).toHaveBeenCalledTimes(1);
    const contentArg = (tip.setContent as ReturnType<typeof vi.fn>).mock
      .calls[0][0] as Record<string, string>;
    expect(contentArg[".tooltip-inner"]).toContain("Add a URL");
  });

  it("(URL_DECK_CHANGED re-arm instant) adding a URL clears the Add-URL seen flag immediately", async () => {
    const { initOnboardingNudges } = await import("../nudges.js");
    const A_URL = { utubUrlID: 1 } as unknown as UtubUrlItem;

    // Both tips previously dismissed; init in the empty-URL-deck state shows
    // nothing and (empty deck) re-arms nothing — the seen flag stays set.
    nudgeStorage.markTipSeen("createUtub");
    nudgeStorage.markTipSeen("addUrl");
    setState({ utubs: [A_UTUB], activeUTubID: 1, urls: [] });
    initOnboardingNudges();
    expect(nudgeStorage.hasSeenTip("addUrl")).toBe(true);

    // Adding the first URL fills the deck; the store-mutating site emits
    // URL_DECK_CHANGED, so rearmCompletedTips clears the Add-URL seen flag live.
    setState({ urls: [A_URL] });
    emitBusEvent(AppEvents.URL_DECK_CHANGED);

    expect(nudgeStorage.hasSeenTip("addUrl")).toBe(false);
  });

  it("(no-nag invariant) an empty deck never clears the seen flag or re-shows", async () => {
    const { initOnboardingNudges } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);

    // Dismissed while empty and staying empty: re-eval must NOT clear the flag
    // (deck has no content) and must NOT re-show the tip.
    nudgeStorage.markTipSeen("createUtub");
    setState({ utubs: [] });
    initOnboardingNudges();
    emitBusEvent(AppEvents.UTUB_SELECTED, {} as UtubSelectedPayload);

    expect(nudgeStorage.hasSeenTip("createUtub")).toBe(true);
    expect(tip.show).not.toHaveBeenCalled();
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

  // ── addTag / addMember: eligibility, sequencing, re-arm, suppression ──────
  const A_URL = { utubUrlID: 1 } as unknown as UtubUrlItem;
  const A_TAG = { id: 1 } as unknown as UtubTag;
  const M_SELF = { id: 1 } as unknown as MemberItem;
  const M_OTHER = { id: 2 } as unknown as MemberItem;

  it("(addTag eligibility) shows only when the UTub has URLs and no tags", async () => {
    const { initOnboardingNudges, _resetOnboardingNudgesForTests } =
      await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubTagBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);

    // createUtub + addUrl seen; a second member keeps addMember ineligible so
    // addTag is the only candidate the walk can reach.
    nudgeStorage.markTipSeen("createUtub");
    nudgeStorage.markTipSeen("addUrl");

    // 0 URLs → addTag NOT eligible.
    setState({
      utubs: [A_UTUB],
      activeUTubID: 1,
      urls: [],
      tags: [],
      members: [M_SELF, M_OTHER],
      isCurrentUserOwner: true,
    });
    initOnboardingNudges();
    expect(tip.show).not.toHaveBeenCalled();

    // A tag already present → addTag NOT eligible.
    _resetOnboardingNudgesForTests();
    nudgeStorage.markTipSeen("createUtub");
    nudgeStorage.markTipSeen("addUrl");
    setState({ urls: [A_URL], tags: [A_TAG] });
    initOnboardingNudges();
    expect(tip.show).not.toHaveBeenCalled();

    // URLs present, no tags → addTag shows.
    _resetOnboardingNudgesForTests();
    nudgeStorage.markTipSeen("createUtub");
    nudgeStorage.markTipSeen("addUrl");
    setState({ urls: [A_URL], tags: [] });
    initOnboardingNudges();
    expect(tip.show).toHaveBeenCalledTimes(1);
    const contentArg = (tip.setContent as ReturnType<typeof vi.fn>).mock
      .calls[0][0] as Record<string, string>;
    expect(contentArg[".tooltip-inner"]).toContain("Tag your links");
  });

  it("(addMember eligibility) shows only for a lone owner/co-creator, not a plain member or with a second member", async () => {
    const { initOnboardingNudges, _resetOnboardingNudgesForTests } =
      await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#memberBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);

    // A tag present keeps addTag ineligible so addMember is the only candidate.
    nudgeStorage.markTipSeen("createUtub");
    nudgeStorage.markTipSeen("addUrl");

    // Plain member (not owner, not co-creator) → NOT eligible.
    setState({
      utubs: [A_UTUB],
      activeUTubID: 1,
      urls: [A_URL],
      tags: [A_TAG],
      members: [M_SELF],
      isCurrentUserOwner: false,
      isCoCreator: false,
    });
    initOnboardingNudges();
    expect(tip.show).not.toHaveBeenCalled();

    // Owner but a second member already present → NOT eligible.
    _resetOnboardingNudgesForTests();
    nudgeStorage.markTipSeen("createUtub");
    nudgeStorage.markTipSeen("addUrl");
    setState({ members: [M_SELF, M_OTHER], isCurrentUserOwner: true });
    initOnboardingNudges();
    expect(tip.show).not.toHaveBeenCalled();

    // Lone owner → addMember shows.
    _resetOnboardingNudgesForTests();
    nudgeStorage.markTipSeen("createUtub");
    nudgeStorage.markTipSeen("addUrl");
    setState({ members: [M_SELF], isCurrentUserOwner: true });
    initOnboardingNudges();
    expect(tip.show).toHaveBeenCalledTimes(1);
    const contentArg = (tip.setContent as ReturnType<typeof vi.fn>).mock
      .calls[0][0] as Record<string, string>;
    expect(contentArg[".tooltip-inner"]).toContain("Invite a member");
  });

  it("(sequencing) addTag precedes addMember; once addTag is seen the next re-eval shows addMember", async () => {
    const { initOnboardingNudges, dismissActiveTip } = await import(
      "../nudges.js"
    );
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubTagBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);

    // Lone-owner UTub with 1 URL + 0 tags: BOTH addTag and addMember are
    // eligible, but addTag has priority (organize before collaborate).
    nudgeStorage.markTipSeen("createUtub");
    nudgeStorage.markTipSeen("addUrl");
    setState({
      utubs: [A_UTUB],
      activeUTubID: 1,
      urls: [A_URL],
      tags: [],
      members: [M_SELF],
      isCurrentUserOwner: true,
    });
    initOnboardingNudges();
    expect(tip.show).toHaveBeenCalledTimes(1);
    let contentArg = (tip.setContent as ReturnType<typeof vi.fn>).mock
      .calls[0][0] as Record<string, string>;
    expect(contentArg[".tooltip-inner"]).toContain("Tag your links");

    // User taps away (dismiss addTag, marks it seen). tags stays empty so the
    // addTag flag is NOT re-armed. The next re-eval advances to addMember.
    dismissActiveTip({ markSeen: true });
    expect(nudgeStorage.hasSeenTip("addTag")).toBe(true);
    emitBusEvent(AppEvents.MEMBER_DECK_CHANGED);

    expect(tip.show).toHaveBeenCalledTimes(2);
    contentArg = (tip.setContent as ReturnType<typeof vi.fn>).mock
      .calls[1][0] as Record<string, string>;
    expect(contentArg[".tooltip-inner"]).toContain("Invite a member");
  });

  it("(TAG_DECK_CHANGED re-arm instant) adding a tag clears the addTag seen flag immediately", async () => {
    const { initOnboardingNudges } = await import("../nudges.js");

    // addTag seen; the UTub has URLs but an empty tag deck → rearm is a no-op on
    // init (nothing to re-arm while the deck is empty). Second member keeps
    // addMember out of the way.
    nudgeStorage.markTipSeen("createUtub");
    nudgeStorage.markTipSeen("addUrl");
    nudgeStorage.markTipSeen("addTag");
    setState({
      utubs: [A_UTUB],
      activeUTubID: 1,
      urls: [A_URL],
      tags: [],
      members: [M_SELF, M_OTHER],
      isCurrentUserOwner: true,
    });
    initOnboardingNudges();
    expect(nudgeStorage.hasSeenTip("addTag")).toBe(true);

    // Adding the first tag fills the deck; TAG_DECK_CHANGED clears the flag live.
    setState({ tags: [A_TAG] });
    emitBusEvent(AppEvents.TAG_DECK_CHANGED);
    expect(nudgeStorage.hasSeenTip("addTag")).toBe(false);
  });

  it("(TAG_DECK_CHANGED re-show instant) deleting the last tag re-shows the addTag tip", async () => {
    const { initOnboardingNudges } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubTagBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);

    // addTag re-armed; the UTub currently holds a tag → not eligible, so init
    // shows nothing. Second member keeps addMember ineligible.
    nudgeStorage.markTipSeen("createUtub");
    nudgeStorage.markTipSeen("addUrl");
    setState({
      utubs: [A_UTUB],
      activeUTubID: 1,
      urls: [A_URL],
      tags: [A_TAG],
      members: [M_SELF, M_OTHER],
      isCurrentUserOwner: true,
    });
    initOnboardingNudges();
    expect(tip.show).not.toHaveBeenCalled();

    // Deleting the last tag empties the deck; TAG_DECK_CHANGED re-shows addTag.
    setState({ tags: [] });
    emitBusEvent(AppEvents.TAG_DECK_CHANGED);
    expect(tip.show).toHaveBeenCalledTimes(1);
    const contentArg = (tip.setContent as ReturnType<typeof vi.fn>).mock
      .calls[0][0] as Record<string, string>;
    expect(contentArg[".tooltip-inner"]).toContain("Tag your links");
  });

  it("(MEMBER_DECK_CHANGED re-arm instant) adding a member clears the addMember seen flag immediately", async () => {
    const { initOnboardingNudges } = await import("../nudges.js");

    // addMember seen; lone owner (members.length === 1) → hasContent false, so
    // init does not re-arm. A tag present keeps addTag out of the way.
    nudgeStorage.markTipSeen("createUtub");
    nudgeStorage.markTipSeen("addUrl");
    nudgeStorage.markTipSeen("addMember");
    setState({
      utubs: [A_UTUB],
      activeUTubID: 1,
      urls: [A_URL],
      tags: [A_TAG],
      members: [M_SELF],
      isCurrentUserOwner: true,
    });
    initOnboardingNudges();
    expect(nudgeStorage.hasSeenTip("addMember")).toBe(true);

    // Adding a member makes members.length > 1 → MEMBER_DECK_CHANGED clears it.
    setState({ members: [M_SELF, M_OTHER] });
    emitBusEvent(AppEvents.MEMBER_DECK_CHANGED);
    expect(nudgeStorage.hasSeenTip("addMember")).toBe(false);
  });

  it("(MEMBER_DECK_CHANGED re-show instant) removing the last added member re-shows the addMember tip", async () => {
    const { initOnboardingNudges } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#memberBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);

    // Owner with a second member present → addMember not eligible; a tag keeps
    // addTag out. Init shows nothing.
    nudgeStorage.markTipSeen("createUtub");
    nudgeStorage.markTipSeen("addUrl");
    setState({
      utubs: [A_UTUB],
      activeUTubID: 1,
      urls: [A_URL],
      tags: [A_TAG],
      members: [M_SELF, M_OTHER],
      isCurrentUserOwner: true,
    });
    initOnboardingNudges();
    expect(tip.show).not.toHaveBeenCalled();

    // Removing the added member returns to a lone owner; MEMBER_DECK_CHANGED
    // re-shows addMember live.
    setState({ members: [M_SELF] });
    emitBusEvent(AppEvents.MEMBER_DECK_CHANGED);
    expect(tip.show).toHaveBeenCalledTimes(1);
    const contentArg = (tip.setContent as ReturnType<typeof vi.fn>).mock
      .calls[0][0] as Record<string, string>;
    expect(contentArg[".tooltip-inner"]).toContain("Invite a member");
  });

  it("(suppression) isCurrentUTubLocked suppresses the new tips and tears down an active one WITHOUT marking it seen", async () => {
    const { initOnboardingNudges } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubTagBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);

    // addTag-eligible baseline, but the UTub is locked → suppressed on init.
    nudgeStorage.markTipSeen("createUtub");
    nudgeStorage.markTipSeen("addUrl");
    setState({
      utubs: [A_UTUB],
      activeUTubID: 1,
      urls: [A_URL],
      tags: [],
      members: [M_SELF],
      isCurrentUserOwner: true,
      isCurrentUTubLocked: true,
    });
    initOnboardingNudges();
    expect(tip.show).not.toHaveBeenCalled();

    // Unlock and re-eval → addTag shows.
    setState({ isCurrentUTubLocked: false });
    emitBusEvent(AppEvents.TAG_DECK_CHANGED);
    expect(tip.show).toHaveBeenCalledTimes(1);

    // Locking again while the tip is active tears it down WITHOUT marking seen.
    const markTipSeenSpy = vi.spyOn(nudgeStorage, "markTipSeen");
    setState({ isCurrentUTubLocked: true });
    emitBusEvent(AppEvents.TAG_DECK_CHANGED);
    expect(tip.dispose).toHaveBeenCalledTimes(1);
    expect(markTipSeenSpy).not.toHaveBeenCalled();
    expect(nudgeStorage.hasSeenTip("addTag")).toBe(false);
  });

  it("(mobile sheet hook) TAG_SHEET_TOGGLED {active:true} defers a re-eval that shows addTag inside the opened sheet", async () => {
    const { initOnboardingNudges } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubTagBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);

    // addTag-eligible, but the collapsed sheet renders the anchor
    // visibility:hidden (happy-dom lacks checkVisibility, so the isRenderedVisible
    // fallback reads getComputedStyle). Second member keeps addMember out.
    nudgeStorage.markTipSeen("createUtub");
    nudgeStorage.markTipSeen("addUrl");
    setState({
      utubs: [A_UTUB],
      activeUTubID: 1,
      urls: [A_URL],
      tags: [],
      members: [M_SELF, M_OTHER],
      isCurrentUserOwner: true,
    });

    const realGetComputedStyle = window.getComputedStyle.bind(window);
    const getComputedStyleSpy = vi
      .spyOn(window, "getComputedStyle")
      .mockImplementation((element: Element, pseudoElement?: string | null) => {
        const computed = realGetComputedStyle(element, pseudoElement);
        if (element === anchor) {
          return { ...computed, visibility: "hidden" } as CSSStyleDeclaration;
        }
        return computed;
      });
    try {
      // Collapsed sheet → the walk skips the hidden anchor → nothing shows.
      initOnboardingNudges();
      expect(tip.show).not.toHaveBeenCalled();

      // The sheet opens: the anchor is now visible and TAG_SHEET_TOGGLED fires.
      getComputedStyleSpy.mockImplementation(
        (element: Element, pseudoElement?: string | null) =>
          realGetComputedStyle(element, pseudoElement),
      );
      emitBusEvent(AppEvents.TAG_SHEET_TOGGLED, { active: true });
      await flushDeferredBind(); // flush the deferred setTimeout(…, 0)

      expect(tip.show).toHaveBeenCalledTimes(1);
      const contentArg = (tip.setContent as ReturnType<typeof vi.fn>).mock
        .calls[0][0] as Record<string, string>;
      expect(contentArg[".tooltip-inner"]).toContain("Tag your links");
    } finally {
      getComputedStyleSpy.mockRestore();
    }
  });

  it("(mobile priority inversion) addMember shows while the tag sheet is collapsed; addTag shows once it opens", async () => {
    const { initOnboardingNudges, dismissActiveTip } = await import(
      "../nudges.js"
    );
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubTagBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);

    // Lone-owner UTub, 1 URL, 0 tags: BOTH addTag and addMember eligible, but the
    // tag anchor is visibility:hidden (collapsed sheet), so the walk skips addTag
    // and shows addMember first — the accepted mobile inversion.
    nudgeStorage.markTipSeen("createUtub");
    nudgeStorage.markTipSeen("addUrl");
    setState({
      utubs: [A_UTUB],
      activeUTubID: 1,
      urls: [A_URL],
      tags: [],
      members: [M_SELF],
      isCurrentUserOwner: true,
    });

    const realGetComputedStyle = window.getComputedStyle.bind(window);
    const getComputedStyleSpy = vi
      .spyOn(window, "getComputedStyle")
      .mockImplementation((element: Element, pseudoElement?: string | null) => {
        const computed = realGetComputedStyle(element, pseudoElement);
        if (element === anchor) {
          return { ...computed, visibility: "hidden" } as CSSStyleDeclaration;
        }
        return computed;
      });
    try {
      initOnboardingNudges();
      expect(tip.show).toHaveBeenCalledTimes(1);
      let contentArg = (tip.setContent as ReturnType<typeof vi.fn>).mock
        .calls[0][0] as Record<string, string>;
      expect(contentArg[".tooltip-inner"]).toContain("Invite a member");

      // Opening the tag sheet is a tap-away: dismiss addMember (markSeen:true).
      // Then the sheet finishes opening (anchor visible) and emits {active:true}.
      dismissActiveTip({ markSeen: true });
      getComputedStyleSpy.mockImplementation(
        (element: Element, pseudoElement?: string | null) =>
          realGetComputedStyle(element, pseudoElement),
      );
      emitBusEvent(AppEvents.TAG_SHEET_TOGGLED, { active: true });
      await flushDeferredBind();

      expect(tip.show).toHaveBeenCalledTimes(2);
      contentArg = (tip.setContent as ReturnType<typeof vi.fn>).mock
        .calls[1][0] as Record<string, string>;
      expect(contentArg[".tooltip-inner"]).toContain("Tag your links");
    } finally {
      getComputedStyleSpy.mockRestore();
    }
  });

  it("(show-gate) a visibility:hidden addTag anchor blocks the show; clearing it lets addTag show (positive control)", async () => {
    const { initOnboardingNudges } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubTagBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);

    // addTag-eligible; a second member keeps addMember ineligible, so addTag is
    // the ONLY candidate — proving the block is the visibility gate itself, not
    // another tip winning the walk.
    nudgeStorage.markTipSeen("createUtub");
    nudgeStorage.markTipSeen("addUrl");
    setState({
      utubs: [A_UTUB],
      activeUTubID: 1,
      urls: [A_URL],
      tags: [],
      members: [M_SELF, M_OTHER],
      isCurrentUserOwner: true,
    });

    const realGetComputedStyle = window.getComputedStyle.bind(window);
    const getComputedStyleSpy = vi
      .spyOn(window, "getComputedStyle")
      .mockImplementation((element: Element, pseudoElement?: string | null) => {
        const computed = realGetComputedStyle(element, pseudoElement);
        if (element === anchor) {
          return { ...computed, visibility: "hidden" } as CSSStyleDeclaration;
        }
        return computed;
      });
    try {
      // Negative: the hidden anchor blocks addTag at the registry walk — via a
      // non-sheet event, so this exercises the visibility:hidden half of
      // isAnchorVisible directly (not the TAG_SHEET_TOGGLED path).
      initOnboardingNudges();
      expect(tip.show).not.toHaveBeenCalled();

      // Positive control: the anchor now reports visible; the SAME re-eval event
      // now shows addTag — proving the harness can detect a show, so the negative
      // assertion above is falsifiable.
      getComputedStyleSpy.mockImplementation(
        (element: Element, pseudoElement?: string | null) =>
          realGetComputedStyle(element, pseudoElement),
      );
      emitBusEvent(AppEvents.TAG_DECK_CHANGED);
      expect(tip.show).toHaveBeenCalledTimes(1);
      const contentArg = (tip.setContent as ReturnType<typeof vi.fn>).mock
        .calls[0][0] as Record<string, string>;
      expect(contentArg[".tooltip-inner"]).toContain("Tag your links");
    } finally {
      getComputedStyleSpy.mockRestore();
    }
  });

  it("(sheet reposition, fake timers) the TAG_SHEET_TOGGLED retry loop repositions the shown tip across the open slide (tip.update called >1×)", async () => {
    const { initOnboardingNudges } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubTagBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);

    // addTag-eligible; a second member keeps addMember ineligible so addTag is
    // the only candidate the walk can reach.
    nudgeStorage.markTipSeen("createUtub");
    nudgeStorage.markTipSeen("addUrl");
    setState({
      utubs: [A_UTUB],
      activeUTubID: 1,
      urls: [A_URL],
      tags: [],
      members: [M_SELF, M_OTHER],
      isCurrentUserOwner: true,
    });

    // Start with the anchor visibility:hidden (collapsed sheet), so init shows
    // nothing and the tip is first shown BY the retry loop's tick 0 — matching
    // the real "sheet opens, then finishes sliding" sequence.
    const realGetComputedStyle = window.getComputedStyle.bind(window);
    const getComputedStyleSpy = vi
      .spyOn(window, "getComputedStyle")
      .mockImplementation((element: Element, pseudoElement?: string | null) => {
        const computed = realGetComputedStyle(element, pseudoElement);
        if (element === anchor) {
          return { ...computed, visibility: "hidden" } as CSSStyleDeclaration;
        }
        return computed;
      });

    vi.useFakeTimers();
    try {
      initOnboardingNudges(); // collapsed sheet → nothing shows on init
      expect(tip.show).not.toHaveBeenCalled();

      // The sheet opens (anchor now reports visible) and the toggle event fires.
      // The retry loop schedules attemptShow on the next tick, shows the tip at
      // tick 0, then repositions it via `.update()` on each subsequent 40ms tick
      // so Popper tracks the still-sliding anchor.
      getComputedStyleSpy.mockImplementation(
        (element: Element, pseudoElement?: string | null) =>
          realGetComputedStyle(element, pseudoElement),
      );
      emitBusEvent(AppEvents.TAG_SHEET_TOGGLED, { active: true });

      // Advance several 40ms ticks past the initial show (tick 0 shows; ticks at
      // 40/80/120/160/200ms each reposition).
      vi.advanceTimersByTime(200);

      expect(tip.show).toHaveBeenCalledTimes(1);
      const updateSpy = tip.update as ReturnType<typeof vi.fn>;
      expect(updateSpy.mock.calls.length).toBeGreaterThan(1);
    } finally {
      getComputedStyleSpy.mockRestore();
      vi.useRealTimers();
    }
  });

  it("(sheet reposition, stale-timer guard) a second TAG_SHEET_TOGGLED cancels the prior loop so only one loop's ticks land", async () => {
    const { initOnboardingNudges } = await import("../nudges.js");
    const { bootstrap } = await import("../../../lib/globals.js");
    const anchor = document.querySelector("#utubTagBtnCreate") as HTMLElement;
    const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);

    nudgeStorage.markTipSeen("createUtub");
    nudgeStorage.markTipSeen("addUrl");
    setState({
      utubs: [A_UTUB],
      activeUTubID: 1,
      urls: [A_URL],
      tags: [],
      members: [M_SELF, M_OTHER],
      isCurrentUserOwner: true,
    });

    const realGetComputedStyle = window.getComputedStyle.bind(window);
    const getComputedStyleSpy = vi
      .spyOn(window, "getComputedStyle")
      .mockImplementation((element: Element, pseudoElement?: string | null) => {
        const computed = realGetComputedStyle(element, pseudoElement);
        if (element === anchor) {
          return { ...computed, visibility: "hidden" } as CSSStyleDeclaration;
        }
        return computed;
      });

    vi.useFakeTimers();
    try {
      initOnboardingNudges(); // collapsed sheet → nothing shows on init
      expect(tip.show).not.toHaveBeenCalled();

      // Two opens in quick succession (a jittery toggle): the second emit's guard
      // clears the first loop's still-pending timer, so only ONE retry loop stays
      // in flight. Both emitted synchronously before any timer advances.
      getComputedStyleSpy.mockImplementation(
        (element: Element, pseudoElement?: string | null) =>
          realGetComputedStyle(element, pseudoElement),
      );
      emitBusEvent(AppEvents.TAG_SHEET_TOGGLED, { active: true });
      emitBusEvent(AppEvents.TAG_SHEET_TOGGLED, { active: true });

      // Run the full retry window (12 × 40ms = 480ms, plus slack).
      vi.advanceTimersByTime(600);

      // A single surviving loop shows the tip once (tick 0) and repositions it on
      // each of the remaining ticks — exactly SHEET_OPEN_SHOW_RETRY_MAX (12)
      // `.update()` calls. Two overlapping loops (guard absent) would roughly
      // double this, so an exact count of 12 proves the prior loop was cancelled.
      expect(tip.show).toHaveBeenCalledTimes(1);
      const updateSpy = tip.update as ReturnType<typeof vi.fn>;
      expect(updateSpy.mock.calls.length).toBe(12);
    } finally {
      getComputedStyleSpy.mockRestore();
      vi.useRealTimers();
    }
  });
});
