import {
  initTagSheet,
  openTagSheet,
  closeTagSheet,
  toggleTagSheet,
  relocateTagDeckForViewport,
  refreshTagSheetHandleVisibility,
  isTagSheetOpen,
  _resetTagSheetGestureForTests,
} from "../sheet.js";
import { TAG_SHEET_TOGGLE_ACTION } from "../../../types/metrics-dim-values.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

// Resettable in-memory event-bus mock: `on`/`emit` operate against a handler
// registry that the suite clears in beforeEach, so initTagSheet() subscriptions
// never accumulate across tests and emitting an event drives the real
// subscriber logic.
const { busHandlers, resetBus } = vi.hoisted(() => {
  const handlers = new Map<string, Set<(payload: unknown) => void>>();
  return {
    busHandlers: handlers,
    resetBus: () => handlers.clear(),
  };
});

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../lib/event-bus.js", () => ({
  AppEvents: {
    UTUB_SELECTED: "utub:selected",
    UTUB_DELETED: "utub:deleted",
    TAG_FILTER_CHANGED: "tag:filter-changed",
    CROSS_UTUB_SEARCH_VISIBILITY_CHANGED:
      "cross-utub-search:visibility-changed",
    MOBILE_DECK_SWITCHED: "mobile:deck-switched",
  },
  on: vi.fn((event: string, handler: (payload: unknown) => void) => {
    if (!busHandlers.has(event)) busHandlers.set(event, new Set());
    busHandlers.get(event)!.add(handler);
    return () => busHandlers.get(event)?.delete(handler);
  }),
  emit: vi.fn((event: string, payload: unknown) => {
    busHandlers.get(event)?.forEach((handler) => handler(payload));
  }),
}));

vi.mock("../../mobile.js", () => ({ isMobile: vi.fn(() => false) }));

vi.mock("../../search/cross-utub-search.js", () => ({
  isCrossUtubSearchActive: vi.fn(() => false),
}));

const $ = window.jQuery;

const SHEET_OPEN_CLASS = "tag-sheet-open";
const BACKDROP_SHOW_CLASS = "tag-sheet-backdrop-show";
const HIDDEN_CLASS = "hidden";
const ARIA_HIDDEN = "aria-hidden";
const ARIA_EXPANDED = "aria-expanded";

const OPENER_ID = "fakeOpener";
const TAG_FILTER_MARKUP = '<div class="tagFilter"></div>';

// Mirrors the actual template nesting: backdrop + sheet are siblings of
// #centerPanel inside #mainPanel; the handle is a direct child of #URLDeck.
const SHEET_HTML = `
  <main id="mainPanel">
    <div id="leftPanel" class="panel">
      <div id="UTubDeck" class="deck"></div>
      <div id="MemberDeck" class="deck"></div>
      <div id="TagDeck" class="deck">
        <div class="titleElement">
          <div id="TagDeckTitleGroup" class="flex-row gap-10p">
            <div id="TagDeckHeaderAndCaret" class="clickable">
              <h2 id="TagDeckHeader">Tags</h2>
            </div>
          </div>
          <div class="button-container">
            <button id="utubTagBtnCreate" type="button"></button>
          </div>
        </div>
        <div id="listTags"></div>
      </div>
    </div>
    <div id="centerPanel" class="panel visible-flex">
      <div id="URLDeck" class="deck">
        <button id="tagSheetHandle" class="tag-sheet-handle hidden" type="button" aria-expanded="false">
          <span id="tagSheetHandleCount" class="tag-sheet-handle-count hidden"></span>
        </button>
      </div>
    </div>
    <div id="tagSheetBackdrop" class="tag-sheet-backdrop"></div>
    <section id="tagDeckSheet" class="tag-deck-sheet" role="dialog" aria-modal="true" aria-hidden="true">
      <button id="tagSheetGrabber" class="tag-sheet-grabber" type="button"></button>
      <div id="tagSheetBody" class="tag-sheet-body">
        <p id="tagSheetEmpty" class="hidden">No tags in this UTub.</p>
      </div>
    </section>
    <button id="${OPENER_ID}" type="button"></button>
  </main>
`;

async function setIsMobile(value: boolean): Promise<void> {
  const { isMobile } = await import("../../mobile.js");
  (isMobile as ReturnType<typeof vi.fn>).mockReturnValue(value);
}

async function setCrossSearchActive(value: boolean): Promise<void> {
  const { isCrossUtubSearchActive } = await import(
    "../../search/cross-utub-search.js"
  );
  (isCrossUtubSearchActive as ReturnType<typeof vi.fn>).mockReturnValue(value);
}

function seedTagFilter(): void {
  $("#listTags").append(TAG_FILTER_MARKUP);
}

describe("Tag Sheet Controller", () => {
  beforeEach(async () => {
    document.body.innerHTML = SHEET_HTML;
    resetBus();
    vi.clearAllMocks();
    await setIsMobile(false);
    await setCrossSearchActive(false);
    // Ensure no module-scoped open state leaks between tests; default close is
    // a no-op when already closed.
    closeTagSheet({ returnFocus: false });
  });

  afterEach(() => {
    closeTagSheet({ returnFocus: false });
    document.body.innerHTML = "";
  });

  describe("DOM relocation", () => {
    it("moves #TagDeck into #tagSheetBody on mobile, preserving #listTags and .tagFilter children", async () => {
      seedTagFilter();
      await setIsMobile(true);
      expect($("#tagSheetBody #TagDeck").length).toBe(0);
      expect($("#leftPanel #TagDeck").length).toBe(1);

      relocateTagDeckForViewport();

      expect($("#tagSheetBody #TagDeck").length).toBe(1);
      expect($("#leftPanel #TagDeck").length).toBe(0);
      expect($("#tagSheetBody #TagDeck #listTags").length).toBe(1);
      expect($("#listTags").children(".tagFilter").length).toBe(1);
    });

    it("moves #TagDeck back into #leftPanel after #MemberDeck on desktop", async () => {
      await setIsMobile(true);
      relocateTagDeckForViewport();
      expect($("#tagSheetBody #TagDeck").length).toBe(1);

      await setIsMobile(false);
      relocateTagDeckForViewport();

      expect($("#tagSheetBody #TagDeck").length).toBe(0);
      const leftPanelDeckIds = $("#leftPanel > .deck")
        .map((_index, element) => element.id)
        .get();
      expect(leftPanelDeckIds).toEqual(["UTubDeck", "MemberDeck", "TagDeck"]);
    });
  });

  describe("open", () => {
    it("opens the sheet on mobile, setting classes, aria, backdrop, and inert siblings", async () => {
      vi.useFakeTimers();
      try {
        await setIsMobile(true);
        expect($("#tagDeckSheet").hasClass(SHEET_OPEN_CLASS)).toBe(false);
        expect(isTagSheetOpen()).toBe(false);

        openTagSheet();

        expect($("#tagDeckSheet").hasClass(SHEET_OPEN_CLASS)).toBe(true);
        expect($("#tagDeckSheet").attr(ARIA_HIDDEN)).toBe("false");
        expect($("#tagSheetHandle").attr(ARIA_EXPANDED)).toBe("true");
        expect(isTagSheetOpen()).toBe(true);
        expect($("#centerPanel").prop("inert")).toBe(true);

        // Backdrop class is applied via setTimeout(0); advance fake timers.
        vi.runAllTimers();
        expect($("#tagSheetBackdrop").hasClass(BACKDROP_SHOW_CLASS)).toBe(true);
      } finally {
        vi.useRealTimers();
      }
    });
  });

  describe("close", () => {
    it("restores focus to the opener element and reverts state on default close", async () => {
      await setIsMobile(true);
      const opener = document.getElementById(OPENER_ID)!;
      opener.focus();
      openTagSheet();
      expect(isTagSheetOpen()).toBe(true);

      closeTagSheet();

      expect(document.activeElement).toBe(opener);
      expect($("#tagDeckSheet").hasClass(SHEET_OPEN_CLASS)).toBe(false);
      expect($("#tagDeckSheet").attr(ARIA_HIDDEN)).toBe("true");
      expect(isTagSheetOpen()).toBe(false);
      expect($("#centerPanel").prop("inert")).toBe(false);
    });

    it("falls back to the handle for focus when the opener is no longer in the DOM", async () => {
      await setIsMobile(true);
      const opener = document.getElementById(OPENER_ID)!;
      opener.focus();
      openTagSheet();
      // Opener leaves the DOM before close (e.g. its deck was re-rendered), so
      // document.contains(_opener) is false → focus restore falls back to the
      // handle.
      opener.remove();

      closeTagSheet();

      expect(document.activeElement).toBe(
        document.getElementById("tagSheetHandle"),
      );
    });
  });

  describe("toggle", () => {
    it("two toggles return the sheet to closed", async () => {
      await setIsMobile(true);
      expect(isTagSheetOpen()).toBe(false);

      toggleTagSheet();
      expect(isTagSheetOpen()).toBe(true);

      toggleTagSheet();
      expect(isTagSheetOpen()).toBe(false);
    });
  });

  describe("desktop guard", () => {
    it("openTagSheet is a no-op on desktop", async () => {
      await setIsMobile(false);
      expect(isTagSheetOpen()).toBe(false);

      openTagSheet();

      expect($("#tagDeckSheet").hasClass(SHEET_OPEN_CLASS)).toBe(false);
      expect(isTagSheetOpen()).toBe(false);
    });
  });

  describe("close affordances", () => {
    it("clicking the backdrop closes the sheet", async () => {
      await setIsMobile(true);
      initTagSheet();
      openTagSheet();
      expect(isTagSheetOpen()).toBe(true);

      $("#tagSheetBackdrop").trigger("click");

      expect(isTagSheetOpen()).toBe(false);
    });

    it("clicking the grabber closes the sheet", async () => {
      await setIsMobile(true);
      initTagSheet();
      openTagSheet();
      expect(isTagSheetOpen()).toBe(true);

      $("#tagSheetGrabber").trigger("click");

      expect(isTagSheetOpen()).toBe(false);
    });

    it("clicking the title group (left half of the header) closes the sheet", async () => {
      await setIsMobile(true);
      initTagSheet();
      openTagSheet();
      expect(isTagSheetOpen()).toBe(true);

      $("#TagDeckTitleGroup").trigger("click");

      expect(isTagSheetOpen()).toBe(false);
    });

    it("clicking a title-row action button does not close the sheet", async () => {
      await setIsMobile(true);
      initTagSheet();
      openTagSheet();
      expect(isTagSheetOpen()).toBe(true);

      // The buttons live in the right-half .button-container, outside the
      // #TagDeckTitleGroup close target, so they never dismiss the sheet.
      $("#utubTagBtnCreate").trigger("click");

      expect(isTagSheetOpen()).toBe(true);
    });

    it("Escape keydown closes the sheet while open and is a no-op when closed", async () => {
      await setIsMobile(true);
      initTagSheet();
      openTagSheet();
      expect(isTagSheetOpen()).toBe(true);

      const escapeDown = $.Event("keydown", { key: "Escape" });
      $(document).trigger(escapeDown);
      expect(isTagSheetOpen()).toBe(false);

      // Already closed: the handler is unbound on close, so Escape does nothing.
      $(document).trigger($.Event("keydown", { key: "Escape" }));
      expect(isTagSheetOpen()).toBe(false);
    });
  });

  describe("handle count badge", () => {
    it("shows the count when tags are selected and hides it when none are", async () => {
      await setIsMobile(true);
      initTagSheet();
      expect($("#tagSheetHandleCount").hasClass(HIDDEN_CLASS)).toBe(true);

      const { emit, AppEvents } = await import("../../../lib/event-bus.js");
      emit(AppEvents.TAG_FILTER_CHANGED, { selectedTagIDs: [1, 2] });
      expect($("#tagSheetHandleCount").hasClass(HIDDEN_CLASS)).toBe(false);
      expect($("#tagSheetHandleCount").text()).toBe("2");

      emit(AppEvents.TAG_FILTER_CHANGED, { selectedTagIDs: [] });
      expect($("#tagSheetHandleCount").hasClass(HIDDEN_CLASS)).toBe(true);
    });
  });

  describe("metrics", () => {
    it("emits UI_TAG_SHEET_TOGGLE with action OPEN on open and CLOSE on close", async () => {
      await setIsMobile(true);
      const { emit } = await import("../../../lib/metrics-client.js");

      openTagSheet();
      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_TAG_SHEET_TOGGLE,
        action: TAG_SHEET_TOGGLE_ACTION.OPEN,
      });

      closeTagSheet({ returnFocus: false });
      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_TAG_SHEET_TOGGLE,
        action: TAG_SHEET_TOGGLE_ACTION.CLOSE,
      });
    });

    it("does not emit a CLOSE metric when the sheet is already closed", async () => {
      await setIsMobile(true);
      const { emit } = await import("../../../lib/metrics-client.js");

      expect(isTagSheetOpen()).toBe(false);
      closeTagSheet({ returnFocus: false });

      expect(emit).not.toHaveBeenCalled();
    });
  });

  describe("programmatic close", () => {
    it("does not move focus when returnFocus is false", async () => {
      await setIsMobile(true);
      const opener = document.getElementById(OPENER_ID)!;
      opener.focus();
      openTagSheet();

      const openerFocusSpy = vi.spyOn(opener, "focus");
      const handle = document.getElementById("tagSheetHandle")!;
      const handleFocusSpy = vi.spyOn(handle, "focus");

      closeTagSheet({ returnFocus: false });

      expect(openerFocusSpy).not.toHaveBeenCalled();
      expect(handleFocusSpy).not.toHaveBeenCalled();
    });
  });

  describe("cross-utub search subscription", () => {
    it("closes the sheet when cross-search becomes active and only refreshes the handle when inactive", async () => {
      await setIsMobile(true);
      // Seed an active UTub selector so refreshTagSheetHandleVisibility() would
      // SHOW the handle when cross-search is inactive — this makes the
      // "hidden while cross-search active" assertion below load-bearing rather
      // than always-true.
      $("#centerPanel").append('<div class="UTubSelector active"></div>');
      initTagSheet();
      openTagSheet();
      expect(isTagSheetOpen()).toBe(true);

      const { emit, AppEvents } = await import("../../../lib/event-bus.js");
      await setCrossSearchActive(true);
      emit(AppEvents.CROSS_UTUB_SEARCH_VISIBILITY_CHANGED, { active: true });
      expect(isTagSheetOpen()).toBe(false);
      // While cross-search is active the handle is hidden despite an active UTub.
      expect($("#tagSheetHandle").hasClass(HIDDEN_CLASS)).toBe(true);

      // Reopen, then signal inactive: sheet stays open and the handle re-shows
      // (active UTub + URL deck visible + cross-search inactive).
      await setCrossSearchActive(false);
      openTagSheet();
      expect(isTagSheetOpen()).toBe(true);
      emit(AppEvents.CROSS_UTUB_SEARCH_VISIBILITY_CHANGED, { active: false });
      expect(isTagSheetOpen()).toBe(true);
      expect($("#tagSheetHandle").hasClass(HIDDEN_CLASS)).toBe(false);
    });
  });

  describe("utub lifecycle subscriptions", () => {
    it("closes the sheet on UTUB_SELECTED", async () => {
      await setIsMobile(true);
      initTagSheet();
      openTagSheet();
      expect(isTagSheetOpen()).toBe(true);

      const { emit, AppEvents } = await import("../../../lib/event-bus.js");
      // The UTUB_SELECTED subscriber ignores the payload, but emit() is typed to
      // require a full UtubSelectedPayload — supply a minimal valid one.
      emit(AppEvents.UTUB_SELECTED, {
        utubID: 1,
        utubName: "Test UTub",
        urls: [],
        tags: [],
        members: [],
        utubOwnerID: 1,
        isCurrentUserOwner: true,
        currentUserID: 1,
      });

      expect($("#tagDeckSheet").hasClass(SHEET_OPEN_CLASS)).toBe(false);
      expect($("#tagDeckSheet").attr(ARIA_HIDDEN)).toBe("true");
      expect(isTagSheetOpen()).toBe(false);
    });

    it("closes the sheet on UTUB_DELETED", async () => {
      await setIsMobile(true);
      initTagSheet();
      openTagSheet();
      expect(isTagSheetOpen()).toBe(true);

      const { emit, AppEvents } = await import("../../../lib/event-bus.js");
      emit(AppEvents.UTUB_DELETED, { utubID: 1 });

      expect($("#tagDeckSheet").hasClass(SHEET_OPEN_CLASS)).toBe(false);
      expect($("#tagDeckSheet").attr(ARIA_HIDDEN)).toBe("true");
      expect(isTagSheetOpen()).toBe(false);
    });
  });

  describe("mobile deck switched subscription", () => {
    it("closes the sheet for target url-deck (navbar navigation dismisses an open sheet)", async () => {
      await setIsMobile(true);
      initTagSheet();
      openTagSheet();
      expect(isTagSheetOpen()).toBe(true);

      const { emit, AppEvents } = await import("../../../lib/event-bus.js");
      emit(AppEvents.MOBILE_DECK_SWITCHED, { target: "url-deck" });

      // Navigating (back) to the URL deck while the sheet is open must dismiss it;
      // otherwise #mainPanel siblings stay inert and the navbar cannot re-open over
      // the URL deck. closeTagSheet is a no-op on the closed-sheet UTub-select path.
      expect(isTagSheetOpen()).toBe(false);
    });

    it("closes the sheet for target member-deck (representative of member/utub/no-utub)", async () => {
      await setIsMobile(true);
      initTagSheet();
      openTagSheet();
      expect(isTagSheetOpen()).toBe(true);

      const { emit, AppEvents } = await import("../../../lib/event-bus.js");
      emit(AppEvents.MOBILE_DECK_SWITCHED, { target: "member-deck" });

      expect(isTagSheetOpen()).toBe(false);
    });

    it("closes the sheet for target utub-deck", async () => {
      await setIsMobile(true);
      initTagSheet();
      openTagSheet();
      expect(isTagSheetOpen()).toBe(true);

      const { emit, AppEvents } = await import("../../../lib/event-bus.js");
      emit(AppEvents.MOBILE_DECK_SWITCHED, { target: "utub-deck" });

      expect(isTagSheetOpen()).toBe(false);
    });

    it("closes the sheet for target no-utub", async () => {
      await setIsMobile(true);
      initTagSheet();
      openTagSheet();
      expect(isTagSheetOpen()).toBe(true);

      const { emit, AppEvents } = await import("../../../lib/event-bus.js");
      emit(AppEvents.MOBILE_DECK_SWITCHED, { target: "no-utub" });

      expect(isTagSheetOpen()).toBe(false);
    });

    it("relocates #TagDeck back to #leftPanel for target desktop", async () => {
      await setIsMobile(true);
      initTagSheet();
      relocateTagDeckForViewport();
      expect($("#tagSheetBody #TagDeck").length).toBe(1);

      const { emit, AppEvents } = await import("../../../lib/event-bus.js");
      await setIsMobile(false);
      emit(AppEvents.MOBILE_DECK_SWITCHED, { target: "desktop" });

      expect($("#tagSheetBody #TagDeck").length).toBe(0);
      expect($("#leftPanel #TagDeck").length).toBe(1);
    });
  });

  describe("refreshTagSheetHandleVisibility", () => {
    // Each case starts from the all-guards-satisfied baseline and flips exactly
    // one guard, isolating that guard as the sole cause of the handle hiding.
    function seedActiveUtubSelector(): void {
      $("#centerPanel").append('<div class="UTubSelector active"></div>');
    }

    it("shows the handle when every guard is satisfied", async () => {
      await setIsMobile(true);
      seedActiveUtubSelector();
      // The SHEET_HTML fixture already gives #centerPanel the visible-flex class.
      expect($("#centerPanel").hasClass("visible-flex")).toBe(true);
      await setCrossSearchActive(false);

      refreshTagSheetHandleVisibility();

      expect($("#tagSheetHandle").hasClass(HIDDEN_CLASS)).toBe(false);
    });

    it("hides the handle when not mobile", async () => {
      await setIsMobile(false);
      seedActiveUtubSelector();
      await setCrossSearchActive(false);

      refreshTagSheetHandleVisibility();

      expect($("#tagSheetHandle").hasClass(HIDDEN_CLASS)).toBe(true);
    });

    it("hides the handle when no UTub is selected", async () => {
      await setIsMobile(true);
      // No active .UTubSelector seeded — the utub-selected guard fails.
      await setCrossSearchActive(false);

      refreshTagSheetHandleVisibility();

      expect($("#tagSheetHandle").hasClass(HIDDEN_CLASS)).toBe(true);
    });

    it("hides the handle when the URL deck is not showing", async () => {
      await setIsMobile(true);
      seedActiveUtubSelector();
      $("#centerPanel").removeClass("visible-flex");
      await setCrossSearchActive(false);

      refreshTagSheetHandleVisibility();

      expect($("#tagSheetHandle").hasClass(HIDDEN_CLASS)).toBe(true);
    });

    it("hides the handle when cross-utub search is active", async () => {
      await setIsMobile(true);
      seedActiveUtubSelector();
      await setCrossSearchActive(true);

      refreshTagSheetHandleVisibility();

      expect($("#tagSheetHandle").hasClass(HIDDEN_CLASS)).toBe(true);
    });
  });

  describe("empty-state message", () => {
    it("shows the empty state when #listTags has no tags and hides it once a tag exists", async () => {
      await setIsMobile(true);
      // No .tagFilter children seeded.
      expect($("#tagSheetEmpty").hasClass(HIDDEN_CLASS)).toBe(true);

      relocateTagDeckForViewport();
      expect($("#tagSheetEmpty").hasClass(HIDDEN_CLASS)).toBe(false);

      seedTagFilter();
      openTagSheet();
      expect($("#tagSheetEmpty").hasClass(HIDDEN_CLASS)).toBe(true);
    });
  });

  describe("swipe gesture", () => {
    const DRAGGING_CLASS = "tag-sheet-dragging";
    const SHEET_RECT = {
      height: 400,
      top: 400,
      bottom: 800,
      left: 0,
      right: 390,
      width: 390,
      x: 0,
      y: 400,
      toJSON: () => ({}),
    } as DOMRect;

    function stubSheetRect(): HTMLElement {
      const sheet = document.getElementById("tagDeckSheet")!;
      sheet.getBoundingClientRect = (): DOMRect => SHEET_RECT;
      return sheet;
    }

    function dispatchPointer({
      target,
      type,
      clientY,
      pointerType = "touch",
    }: {
      target: HTMLElement;
      type: "pointerdown" | "pointermove" | "pointerup" | "pointercancel";
      clientY: number;
      pointerType?: string;
    }): void {
      const event = new Event(type, { bubbles: true, cancelable: true });
      Object.defineProperty(event, "button", { value: 0 });
      Object.defineProperty(event, "pointerId", { value: 1 });
      Object.defineProperty(event, "clientX", { value: 0 });
      Object.defineProperty(event, "clientY", { value: clientY });
      Object.defineProperty(event, "pointerType", { value: pointerType });
      target.dispatchEvent(event);
    }

    afterEach(() => {
      _resetTagSheetGestureForTests();
    });

    it("opens the sheet on an upward drag from the handle past the threshold", async () => {
      vi.useFakeTimers();
      try {
        stubSheetRect();
        await setIsMobile(true);
        initTagSheet();
        const { emit } = await import("../../../lib/metrics-client.js");
        expect(isTagSheetOpen()).toBe(false);

        const handle = document.getElementById("tagSheetHandle")!;
        dispatchPointer({ target: handle, type: "pointerdown", clientY: 780 });
        dispatchPointer({ target: handle, type: "pointermove", clientY: 600 });
        dispatchPointer({ target: handle, type: "pointerup", clientY: 600 });
        vi.runAllTimers();

        expect(isTagSheetOpen()).toBe(true);
        expect($("#tagDeckSheet").hasClass(SHEET_OPEN_CLASS)).toBe(true);
        expect(emit).toHaveBeenCalledWith({
          event: UI_EVENTS.UI_TAG_SHEET_TOGGLE,
          action: TAG_SHEET_TOGGLE_ACTION.OPEN,
        });
      } finally {
        vi.useRealTimers();
      }
    });

    it("closes the sheet on a downward drag from the grabber past the threshold", async () => {
      stubSheetRect();
      await setIsMobile(true);
      initTagSheet();
      openTagSheet();
      expect(isTagSheetOpen()).toBe(true);
      const { emit } = await import("../../../lib/metrics-client.js");
      (emit as ReturnType<typeof vi.fn>).mockClear();

      const grabber = document.getElementById("tagSheetGrabber")!;
      dispatchPointer({ target: grabber, type: "pointerdown", clientY: 420 });
      dispatchPointer({ target: grabber, type: "pointermove", clientY: 640 });
      dispatchPointer({ target: grabber, type: "pointerup", clientY: 640 });

      expect(isTagSheetOpen()).toBe(false);
      expect($("#tagDeckSheet").hasClass(SHEET_OPEN_CLASS)).toBe(false);
      expect(emit).toHaveBeenCalledTimes(1);
      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_TAG_SHEET_TOGGLE,
        action: TAG_SHEET_TOGGLE_ACTION.CLOSE,
      });
    });

    it("does not open via the gesture on desktop (gesture early-returns)", async () => {
      stubSheetRect();
      await setIsMobile(false);
      initTagSheet();
      const { emit } = await import("../../../lib/metrics-client.js");

      const handle = document.getElementById("tagSheetHandle")!;
      dispatchPointer({ target: handle, type: "pointerdown", clientY: 780 });
      dispatchPointer({ target: handle, type: "pointermove", clientY: 600 });
      dispatchPointer({ target: handle, type: "pointerup", clientY: 600 });

      expect(isTagSheetOpen()).toBe(false);
      expect(emit).not.toHaveBeenCalledWith({
        event: UI_EVENTS.UI_TAG_SHEET_TOGGLE,
        action: TAG_SHEET_TOGGLE_ACTION.OPEN,
      });
    });

    it("snaps back (does not open) when the upward drag is below the threshold", async () => {
      // Fake timers freeze performance.now() so velocity sampling is
      // deterministic (same-tick events => dt 0 => velocity stays 0); otherwise
      // a sub-millisecond real dt inflates velocity into a spurious fling commit.
      vi.useFakeTimers();
      try {
        stubSheetRect();
        await setIsMobile(true);
        initTagSheet();
        const { emit } = await import("../../../lib/metrics-client.js");

        const handle = document.getElementById("tagSheetHandle")!;
        // ~40px up < 35% of 400 (140px) and below fling velocity.
        dispatchPointer({ target: handle, type: "pointerdown", clientY: 780 });
        dispatchPointer({ target: handle, type: "pointermove", clientY: 740 });
        dispatchPointer({ target: handle, type: "pointerup", clientY: 740 });

        expect(isTagSheetOpen()).toBe(false);
        expect(emit).not.toHaveBeenCalledWith({
          event: UI_EVENTS.UI_TAG_SHEET_TOGGLE,
          action: TAG_SHEET_TOGGLE_ACTION.OPEN,
        });
      } finally {
        vi.useRealTimers();
      }
    });

    it("cancels an in-flight drag when a force-close event fires mid-drag", async () => {
      stubSheetRect();
      await setIsMobile(true);
      initTagSheet();
      // A force-close routes through closeTagSheet(), whose force-close
      // subscribers act only when the sheet is open — so the realistic mid-drag
      // cancellation is during a CLOSE drag (sheet open). _cancelDrag at the top
      // of closeTagSheet() then tears down the live drag.
      openTagSheet();
      expect(isTagSheetOpen()).toBe(true);

      const grabber = document.getElementById("tagSheetGrabber")!;
      dispatchPointer({ target: grabber, type: "pointerdown", clientY: 420 });
      dispatchPointer({ target: grabber, type: "pointermove", clientY: 500 });
      // Mid-drag: dragging class present, sheet has an inline transform.
      expect($("#tagDeckSheet").hasClass(DRAGGING_CLASS)).toBe(true);

      const { emit, AppEvents } = await import("../../../lib/event-bus.js");
      emit(AppEvents.UTUB_SELECTED, {
        utubID: 1,
        utubName: "Test UTub",
        urls: [],
        tags: [],
        members: [],
        utubOwnerID: 1,
        isCurrentUserOwner: true,
        currentUserID: 1,
      });

      expect($("#tagDeckSheet").hasClass(DRAGGING_CLASS)).toBe(false);
      expect(
        (document.querySelector("#tagDeckSheet") as HTMLElement).style
          .transform,
      ).toBe("");
      expect(
        (document.querySelector("#tagSheetBackdrop") as HTMLElement).style
          .opacity,
      ).toBe("");
    });

    it("treats a sub-slop press-release as a tap so the click toggle still fires", async () => {
      stubSheetRect();
      await setIsMobile(true);
      initTagSheet();

      const handle = document.getElementById("tagSheetHandle")!;
      // Movement < TAP_SLOP_PX (8px): no drag, no suppression flag.
      dispatchPointer({ target: handle, type: "pointerdown", clientY: 780 });
      dispatchPointer({ target: handle, type: "pointermove", clientY: 776 });
      dispatchPointer({ target: handle, type: "pointerup", clientY: 776 });

      // The native click that a real tap would fire still toggles the sheet open.
      handle.dispatchEvent(new MouseEvent("click", { bubbles: true }));

      expect(isTagSheetOpen()).toBe(true);
    });

    it("suppresses the click that follows a committed open drag", async () => {
      vi.useFakeTimers();
      try {
        stubSheetRect();
        await setIsMobile(true);
        initTagSheet();
        const { emit } = await import("../../../lib/metrics-client.js");

        const handle = document.getElementById("tagSheetHandle")!;
        dispatchPointer({ target: handle, type: "pointerdown", clientY: 780 });
        dispatchPointer({ target: handle, type: "pointermove", clientY: 600 });
        dispatchPointer({ target: handle, type: "pointerup", clientY: 600 });
        vi.runAllTimers();
        expect(isTagSheetOpen()).toBe(true);

        // jQuery .trigger invokes the .on("click") handler directly, exercising
        // the suppression wrapper regardless of native event propagation.
        $(handle).trigger("click");

        // Sheet stays open: toggleTagSheet was suppressed (would have closed it).
        expect(isTagSheetOpen()).toBe(true);
        expect(emit).not.toHaveBeenCalledWith({
          event: UI_EVENTS.UI_TAG_SHEET_TOGGLE,
          action: TAG_SHEET_TOGGLE_ACTION.CLOSE,
        });
      } finally {
        vi.useRealTimers();
      }
    });

    it("ignores a mouse-pointer drag on mobile (touch/pen only)", async () => {
      stubSheetRect();
      await setIsMobile(true);
      initTagSheet();
      const { emit } = await import("../../../lib/metrics-client.js");

      const handle = document.getElementById("tagSheetHandle")!;
      dispatchPointer({
        target: handle,
        type: "pointerdown",
        clientY: 780,
        pointerType: "mouse",
      });
      dispatchPointer({
        target: handle,
        type: "pointermove",
        clientY: 600,
        pointerType: "mouse",
      });
      dispatchPointer({
        target: handle,
        type: "pointerup",
        clientY: 600,
        pointerType: "mouse",
      });

      expect(isTagSheetOpen()).toBe(false);
      expect(emit).not.toHaveBeenCalledWith({
        event: UI_EVENTS.UI_TAG_SHEET_TOGGLE,
        action: TAG_SHEET_TOGGLE_ACTION.OPEN,
      });
    });
  });
});
