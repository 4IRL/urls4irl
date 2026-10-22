import type { Mock } from "vitest";

import { AppEvents, emit } from "../../../lib/event-bus.js";
import { resetStore, setState } from "../../../store/app-store.js";
import { initPopover, resetPopover } from "../popover.js";
import { DEBOUNCE_MS } from "../queue.js";
import { _resetRegistryForTests } from "../registry.js";
import {
  SELF_BACK_TIMEOUT_MS,
  closeSettingsSheetFromPopstate,
  consumePanelSettingsSheetSelfBackClose,
  getSettingsSheetBaseState,
  isPanelSettingsSheetSelfBackPending,
  isSettingsSheetOpen,
  openSettingsSheet,
  registerSettingsSheetCloseHandler,
  TAP_SLOP_PX,
} from "../sheet.js";
import type { CloseKind } from "../sheet.js";
import {
  FLING_VELOCITY_PX_PER_MS,
  SNAP_DISTANCE_FRACTION,
  shouldCommitSheetGesture,
} from "../../../logic/tag-sheet-snap.js";
import {
  isPanelSettingsBusy,
  setPanelSettingsPendingSaveCount,
} from "../state.js";
import {
  FIXTURE,
  el,
  gear,
  installHistoryStub,
  mockBreakpoint,
  openGear,
  pressKey,
  registerControlled,
  selectUTub,
} from "./helpers.js";
import type { BreakpointMock, HistoryStub } from "./helpers.js";

vi.mock("../announce.js", () => ({
  announceSettingsStatus: vi.fn(({ message }: { message: string }) => {
    const region = document.querySelector("#PanelSettingsAnnouncement");
    if (region) region.textContent = message;
  }),
}));
vi.mock("../client.js", () => ({
  handleActiveUTubGone: vi.fn(),
  resyncSettings: vi.fn(async () => true),
}));
vi.mock("../../utubs/stale-data.js", () => ({
  updateUTubOnFindingStaleData: vi.fn(async () => {}),
}));
vi.mock("../../onboarding/nudges.js", () => ({
  dismissActiveTip: vi.fn(),
  maybeShowNextTip: vi.fn(),
}));
vi.mock("../../members/row-menu.js", () => ({
  closeAllMemberRowMenus: vi.fn(),
}));
vi.mock("../../utubs/header-fit.js", () => ({
  fitUTubHeaderAndSubheader: vi.fn(),
}));
vi.mock("../../../lib/tooltips.js", () => ({
  hideTooltip: vi.fn(),
}));
// The real Tag sheet pulls in the whole home module graph (and its event-bus
// subscribers); stacked behaviour against it lives in sheet-history.test.ts.
vi.mock("../../tags/sheet.js", () => ({
  isTagSheetOpen: () => mockIsTagSheetOpen(),
  isTagSheetSelfBackPending: () => mockIsTagSheetSelfBackPending(),
}));

const mockIsTagSheetOpen = vi.fn(() => false);
const mockIsTagSheetSelfBackPending = vi.fn(() => false);

// A modal before the root; main, footer and cookie banner after it (layout.html),
// plus the non-element-ish nodes that must never be inerted.
const MODAL_MARKUP = '<div id="someModal"></div>';
const PAGE_MARKUP = `
  <main id="mainPanel">
    <button id="tagSheetHandle" type="button">handle</button>
    <div id="mainChild"></div>
    <span id="liveBanner" aria-live="polite"></span>
  </main>
  <footer id="pageFooter"></footer>
  <div id="cookieBanner"></div>
  <script id="inlineScript"></script>
  <style id="inlineStyle"></style>
  <template id="inlineTemplate"></template>
`;

const SHEET_HEIGHT = 400;
const PANELS = ["utubs", "members", "tags", "urls"] as const;

function sheet(): HTMLElement {
  return el("panelSettingsSheet");
}

function backdrop(): HTMLElement {
  return el("panelSettingsBackdrop");
}

function popover(): HTMLElement {
  return el("panelSettingsPopover");
}

function isSheetOpen(): boolean {
  return !sheet().classList.contains("hidden");
}

function isPopoverOpen(): boolean {
  return !popover().classList.contains("hidden");
}

function inertBodyChildren(): string[] {
  return Array.from(document.body.children)
    .filter((child) => child.hasAttribute("inert"))
    .map((child) => child.id || child.tagName);
}

function announced(): string {
  vi.advanceTimersByTime(0);
  return el("PanelSettingsAnnouncement").textContent ?? "";
}

function registerPanels(): void {
  registerControlled({ id: "urls-sec", panel: "urls", title: "URLs" });
  registerControlled({ id: "members-sec", panel: "members", title: "Members" });
  registerControlled({ id: "tags-sec", panel: "tags", title: "Tags" });
  registerControlled({
    id: "utubs-sec",
    panel: "utubs",
    title: "UTubs",
    scope: "user",
    userKind: "global",
  });
}

function setupUrlsSheet(): ReturnType<typeof registerControlled> {
  initPopover();
  const harness = registerControlled();
  selectUTub();
  openGear("urls");
  return harness;
}

function touch({
  type,
  target,
  clientY,
  pointerType = "touch",
  pointerId = 1,
}: {
  type: string;
  target: HTMLElement;
  clientY: number;
  pointerType?: string;
  pointerId?: number;
}): PointerEvent {
  const event = new PointerEvent(type, {
    pointerId,
    pointerType,
    clientY,
    bubbles: true,
    cancelable: true,
  });
  target.dispatchEvent(event);
  return event;
}

const BASE_STATE = { UTubID: 5, mobilePanel: "urls" };

function stubSheetHeight(): void {
  vi.spyOn(sheet(), "getBoundingClientRect").mockReturnValue({
    height: SHEET_HEIGHT,
    width: 390,
    top: 0,
    left: 0,
    right: 390,
    bottom: SHEET_HEIGHT,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  } as DOMRect);
}

describe("panel settings mobile sheet", () => {
  const originalMatchMedia = window.matchMedia;
  let breakpoint: BreakpointMock;
  let historyStub: HistoryStub;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    mockIsTagSheetOpen.mockReturnValue(false);
    mockIsTagSheetSelfBackPending.mockReturnValue(false);
    document.body.innerHTML = MODAL_MARKUP + FIXTURE + PAGE_MARKUP;
    resetStore();
    // The busy counter is module state a previous test's pending save can leave up.
    setPanelSettingsPendingSaveCount({ count: 0 });
    historyStub = installHistoryStub();
    // Stands in for window-events: the sheet's own back() popstate is consumed.
    // History tests that need the popstate pending replace back() with a no-op.
    window.addEventListener("popstate", consumePanelSettingsSheetSelfBackClose);
    breakpoint = mockBreakpoint({ matches: true });
  });

  afterEach(() => {
    window.removeEventListener(
      "popstate",
      consumePanelSettingsSheetSelfBackClose,
    );
    resetPopover();
    _resetRegistryForTests();
    historyStub.restore();
    window.matchMedia = originalMatchMedia;
    vi.useRealTimers();
  });

  describe("surface routing", () => {
    it("opens each of the four gears in the sheet body, not the popover", () => {
      initPopover();
      registerPanels();
      selectUTub();

      for (const panel of PANELS) {
        openGear(panel);
        expect(isSheetOpen()).toBe(true);
        expect(isPopoverOpen()).toBe(false);
        expect(
          el("panelSettingsSheetBody").querySelector("input"),
        ).not.toBeNull();
        expect(el("panelSettingsSheetTitle").textContent).toBe(
          gear(panel).getAttribute("aria-label"),
        );
        el("panelSettingsSheetClose").click();
        expect(isSheetOpen()).toBe(false);
      }
    });

    it("opens the popover at or above the breakpoint and leaves the sheet hidden", () => {
      breakpoint.cross({ matches: false });
      initPopover();
      registerControlled();
      selectUTub();
      openGear("urls");

      expect(isPopoverOpen()).toBe(true);
      expect(isSheetOpen()).toBe(false);
      expect(backdrop().classList.contains("hidden")).toBe(true);
      expect(inertBodyChildren()).toEqual([]);
    });

    it("sets the dialog state on the sheet, backdrop and root", () => {
      setupUrlsSheet();

      expect(isSettingsSheetOpen()).toBe(true);
      expect(sheet().classList.contains("panelSettingsSheet--open")).toBe(true);
      expect(backdrop().classList.contains("panelSettingsBackdrop--show")).toBe(
        true,
      );
      expect(
        el("panelSettingsRoot").classList.contains("panelSettingsRoot--sheet"),
      ).toBe(true);
      expect(gear("urls").getAttribute("aria-expanded")).toBe("true");
    });
  });

  describe("breakpoint crossing", () => {
    it("closes an open sheet when crossing to desktop", () => {
      setupUrlsSheet();
      breakpoint.cross({ matches: false });

      expect(isSheetOpen()).toBe(false);
      expect(isPopoverOpen()).toBe(false);
      expect(inertBodyChildren()).toEqual([]);
    });

    it("closes an open popover when crossing to mobile", () => {
      breakpoint.cross({ matches: false });
      initPopover();
      registerControlled();
      selectUTub();
      openGear("urls");
      breakpoint.cross({ matches: true });

      expect(isSheetOpen()).toBe(false);
      expect(isPopoverOpen()).toBe(false);
    });

    it("restores focus to the gear when focus was inside the sheet", () => {
      setupUrlsSheet();
      el("sort-input").focus();
      breakpoint.cross({ matches: false });

      expect(document.activeElement).toBe(gear("urls"));
      expect(announced()).toBe("Settings closed");
    });

    it("leaves focus alone when it was already elsewhere", () => {
      setupUrlsSheet();
      // Inside the root, so it is not inert and can take focus.
      const elsewhere = document.createElement("button");
      el("panelSettingsRoot").append(elsewhere);
      elsewhere.focus();
      breakpoint.cross({ matches: false });

      expect(document.activeElement).toBe(elsewhere);
    });

    it("falls back to the Tag sheet handle on a same-side breakpoint event when the Tags gear is detached", () => {
      initPopover();
      registerControlled({ id: "tags-sec", panel: "tags", title: "Tags" });
      selectUTub();
      openGear("tags");
      el("sort-input").focus();
      gear("tags").remove();
      breakpoint.cross({ matches: true });
      // Already below: a same-side change event still force-closes the sheet.
      expect(document.activeElement).toBe(el("tagSheetHandle"));
    });

    it("falls back to the Tag deck header at or above 992px", () => {
      initPopover();
      registerControlled({ id: "tags-sec", panel: "tags", title: "Tags" });
      selectUTub();
      openGear("tags");
      el("sort-input").focus();
      gear("tags").remove();
      breakpoint.cross({ matches: false });

      expect(document.activeElement).toBe(el("TagDeckHeaderAndCaret"));
    });
  });

  describe("close paths", () => {
    function closeByButton(): void {
      el("panelSettingsSheetClose").click();
    }
    function closeByBackdrop(): void {
      backdrop().click();
    }
    function closeByEscape(): void {
      pressKey({ key: "Escape", target: el("sort-input") });
    }

    it.each([
      ["the close button", closeByButton],
      ["a backdrop tap", closeByBackdrop],
      ["Escape", closeByEscape],
    ])(
      "%s closes, returns focus to the gear and clears inert",
      (_name, close) => {
        setupUrlsSheet();
        expect(inertBodyChildren().length).toBeGreaterThan(0);
        close();

        expect(isSheetOpen()).toBe(false);
        expect(backdrop().classList.contains("hidden")).toBe(true);
        expect(document.activeElement).toBe(gear("urls"));
        expect(inertBodyChildren()).toEqual([]);
        expect(
          el("panelSettingsRoot").classList.contains(
            "panelSettingsRoot--sheet",
          ),
        ).toBe(false);
        expect(gear("urls").getAttribute("aria-expanded")).toBe("false");
        // A user close is silent.
        expect(announced()).toBe("");
      },
    );

    it.each([
      ["the close button", closeByButton],
      ["a backdrop tap", closeByBackdrop],
      ["Escape", closeByEscape],
    ])("%s flushes pending edits", async (_name, close) => {
      const harness = setupUrlsSheet();
      harness.ctxs[harness.ctxs.length - 1].submit({
        patch: { sort: "new" },
        debounce: true,
      });
      close();
      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS);

      expect(harness.section.save).toHaveBeenCalledTimes(1);
    });

    it("does not close on a pointerdown outside (the backdrop is its outside)", () => {
      setupUrlsSheet();
      el("outside").dispatchEvent(
        new Event("pointerdown", { bubbles: true, cancelable: true }),
      );

      expect(isSheetOpen()).toBe(true);
    });
  });

  describe("inert", () => {
    it("inerts every body child except the root, skipping script, style and template", () => {
      setupUrlsSheet();
      const inert = inertBodyChildren();

      for (const id of [
        "someModal",
        "mainPanel",
        "pageFooter",
        "cookieBanner",
      ]) {
        expect(inert).toContain(id);
      }
      expect(inert).not.toContain("panelSettingsRoot");
      for (const id of ["inlineScript", "inlineStyle", "inlineTemplate"]) {
        expect(el(id).hasAttribute("inert")).toBe(false);
      }
    });

    it("restores an element that was already inert", () => {
      el("pageFooter").setAttribute("inert", "");
      setupUrlsSheet();
      el("panelSettingsSheetClose").click();

      expect(el("pageFooter").hasAttribute("inert")).toBe(true);
      expect(el("someModal").hasAttribute("inert")).toBe(false);
    });

    it("leaves the Tag sheet's inert state on #mainPanel and its children as it was", () => {
      el("mainChild").setAttribute("inert", "");
      el("tagSheetHandle").setAttribute("inert", "");
      const before = [
        el("mainPanel"),
        ...Array.from(el("mainPanel").children),
      ].map((node) => node.hasAttribute("inert"));
      setupUrlsSheet();
      el("panelSettingsSheetClose").click();
      const after = [
        el("mainPanel"),
        ...Array.from(el("mainPanel").children),
      ].map((node) => node.hasAttribute("inert"));

      expect(after).toEqual(before);
    });

    it("keeps an announcement written into an inert live region after close", () => {
      setupUrlsSheet();
      el("liveBanner").textContent = "Banner while open";
      expect(el("liveBanner").closest("[inert]")).not.toBeNull();
      el("panelSettingsSheetClose").click();

      expect(el("liveBanner").textContent).toBe("Banner while open");
      expect(el("liveBanner").closest("[inert]")).toBeNull();
    });
  });

  describe("focus", () => {
    it("lands on the first control", () => {
      setupUrlsSheet();
      expect(document.activeElement).toBe(el("sort-input"));
    });

    it("lands on the close button when the section renders nothing focusable", () => {
      initPopover();
      registerControlled({
        render: vi.fn(({ container }) => {
          container.textContent = "Nothing to focus";
        }),
      });
      selectUTub();
      openGear("urls");

      expect(document.activeElement).toBe(el("panelSettingsSheetClose"));
    });

    it("wraps Tab from the last control to the first, close button included", () => {
      setupUrlsSheet();
      el("sort-input").focus();
      const event = pressKey({ key: "Tab", target: el("sort-input") });

      expect(event.defaultPrevented).toBe(true);
      expect(document.activeElement).toBe(el("panelSettingsSheetClose"));
    });

    it("wraps Shift+Tab from the first control (the close button) to the last", () => {
      setupUrlsSheet();
      el("panelSettingsSheetClose").focus();
      const event = pressKey({
        key: "Tab",
        shiftKey: true,
        target: el("panelSettingsSheetClose"),
      });

      expect(event.defaultPrevented).toBe(true);
      expect(document.activeElement).toBe(el("sort-input"));
    });

    it("keeps focus in the sheet when a lock flip re-renders a section with nothing focusable", () => {
      initPopover();
      registerControlled({
        render: vi.fn(({ container, ctx }) => {
          if (ctx.canWrite) container.innerHTML = '<input id="sort-input" />';
          else container.textContent = "Read only";
        }),
      });
      selectUTub();
      openGear("urls");
      el("sort-input").focus();
      setState({ isCurrentUTubLocked: true });

      expect(document.activeElement).toBe(sheet());
      expect(isSheetOpen()).toBe(true);
    });

    it("uses the sheet, not the popover, for a forced close's inside-focus test", () => {
      setupUrlsSheet();
      el("sort-input").focus();
      emit(AppEvents.TRASH_OPENED);

      expect(isSheetOpen()).toBe(false);
      expect(document.activeElement).toBe(gear("urls"));
      expect(announced()).toBe("Settings closed");
    });
  });

  describe("escape order", () => {
    it("stops later document keydown listeners while the sheet is open", () => {
      setupUrlsSheet();
      const spy = vi.fn();
      document.addEventListener("keydown", spy);
      const event = pressKey({ key: "Escape", target: el("sort-input") });
      document.removeEventListener("keydown", spy);

      expect(event.defaultPrevented).toBe(true);
      expect(spy).not.toHaveBeenCalled();
      expect(isSheetOpen()).toBe(false);
    });
  });

  describe("shared shell rules", () => {
    it("shows the read-only note for a locked UTub in the sheet", () => {
      initPopover();
      registerControlled();
      selectUTub({ locked: true });
      openGear("urls");

      const note = el("panelSettingsSheetBody").querySelector<HTMLElement>(
        ".panelSettingsReadOnlyNote",
      );
      expect(note?.hidden).toBe(false);
      expect(note?.textContent).not.toBe("");
    });

    it("force-closes on a mobile deck switch", () => {
      setupUrlsSheet();
      emit(AppEvents.MOBILE_DECK_SWITCHED, { target: "member-deck" });

      expect(isSheetOpen()).toBe(false);
      expect(announced()).toBe("Settings closed");
    });

    it("is busy while open and idle one tick after close", () => {
      setupUrlsSheet();
      expect(isPanelSettingsBusy()).toBe(true);
      el("panelSettingsSheetClose").click();
      expect(isPanelSettingsBusy()).toBe(true);
      vi.advanceTimersByTime(0);
      expect(isPanelSettingsBusy()).toBe(false);
    });

    it("shows save status in the sheet", async () => {
      const harness = setupUrlsSheet();
      harness.ctxs[harness.ctxs.length - 1].submit({ patch: { sort: "new" } });
      await vi.advanceTimersByTimeAsync(0);
      const status = el("panelSettingsSheetBody").querySelector<HTMLElement>(
        ".panelSettingsStatus",
      );
      expect(status?.dataset.state).toBe("saving");
    });
  });

  describe("open failure", () => {
    it("rolls the sheet back and rethrows when opening the sheet throws", () => {
      historyStub.entries()[historyStub.index()] = BASE_STATE;
      initPopover();
      // A section's own render errors are swallowed per section; a throw from
      // the initial focus is what reaches openPopover's rollback.
      registerControlled({
        render: vi.fn(({ container }) => {
          const input = document.createElement("input");
          input.focus = () => {
            throw new Error("focus failed");
          };
          container.append(input);
        }),
      });
      selectUTub();

      expect(() => openGear("urls")).toThrow("focus failed");
      expect(isSheetOpen()).toBe(false);
      expect(backdrop().classList.contains("hidden")).toBe(true);
      expect(inertBodyChildren()).toEqual([]);
      expect(gear("urls").getAttribute("aria-expanded")).toBe("false");
      expect(historyStub.pushState).toHaveBeenCalledTimes(1);
      expect(history.state).toEqual(BASE_STATE);
      expect(historyStub.back).not.toHaveBeenCalled();
    });

    it("throws when the sheet markup is missing", () => {
      sheet().remove();

      expect(() => openSettingsSheet({ title: "URLs" })).toThrow(
        "panel settings sheet markup is missing",
      );
      expect(historyStub.pushState).not.toHaveBeenCalled();
      expect(inertBodyChildren()).toEqual([]);
    });
  });

  describe("gear rules", () => {
    it.each([true, false])(
      "shows no gear without a registered section (below breakpoint: %s)",
      (matches) => {
        breakpoint.cross({ matches });
        initPopover();
        selectUTub();
        for (const panel of PANELS) {
          expect(gear(panel).classList.contains("hidden")).toBe(true);
        }
      },
    );
  });

  describe("registered close handler", () => {
    it("is called with 'user' by the close button and the backdrop", () => {
      setupUrlsSheet();
      const handler = vi.fn();
      registerSettingsSheetCloseHandler(handler);

      el("panelSettingsSheetClose").click();
      backdrop().click();

      expect(handler).toHaveBeenCalledTimes(2);
      expect(handler).toHaveBeenNthCalledWith(1, "user");
      expect(handler).toHaveBeenNthCalledWith(2, "user");
    });

    it("is cleared by a reset, which tears the open sheet down completely", () => {
      setupUrlsSheet();
      const handler = vi.fn();
      registerSettingsSheetCloseHandler(handler);
      resetPopover();

      expect(isSheetOpen()).toBe(false);
      expect(backdrop().classList.contains("hidden")).toBe(true);
      expect(inertBodyChildren()).toEqual([]);
      expect(
        el("panelSettingsRoot").classList.contains("panelSettingsRoot--sheet"),
      ).toBe(false);
      el("panelSettingsSheetClose").click();
      expect(handler).not.toHaveBeenCalled();
      expect(isSheetOpen()).toBe(false);
    });

    it("ignores a user close when no handler is registered (fail closed)", () => {
      setupUrlsSheet();
      resetPopover();
      initPopover();
      resetPopover();
      backdrop().click();
      el("panelSettingsSheetClose").click();

      expect(inertBodyChildren()).toEqual([]);
      expect(isSheetOpen()).toBe(false);
    });

    it("re-binds after re-init without double listeners", () => {
      setupUrlsSheet();
      initPopover();
      const handler = vi.fn();
      registerSettingsSheetCloseHandler(handler);
      registerSettingsSheetCloseHandler(handler);
      selectUTub();
      registerControlled({ id: "again" });
      openGear("urls");
      el("panelSettingsSheetClose").click();

      expect(handler).toHaveBeenCalledTimes(1);
    });
  });

  describe("drag to dismiss", () => {
    let handler: Mock<(kind: CloseKind) => void>;

    beforeEach(() => {
      setupUrlsSheet();
      stubSheetHeight();
      handler = vi.fn();
      registerSettingsSheetCloseHandler((kind) => handler(kind));
    });

    function drag({
      target = el("panelSettingsSheetHeader"),
      moves,
      endType = "pointerup",
      pointerType = "touch",
    }: {
      target?: HTMLElement;
      moves: Array<{ y: number; advanceMs?: number }>;
      endType?: string;
      pointerType?: string;
    }): void {
      touch({ type: "pointerdown", target, clientY: 100, pointerType });
      for (const move of moves) {
        if (move.advanceMs) vi.advanceTimersByTime(move.advanceMs);
        touch({ type: "pointermove", target, clientY: move.y, pointerType });
      }
      const last = moves[moves.length - 1]?.y ?? 100;
      touch({ type: endType, target, clientY: last, pointerType });
    }

    it("closes as a user close past the distance threshold", () => {
      drag({ moves: [{ y: 100 + SHEET_HEIGHT * 0.4 }] });

      expect(handler).toHaveBeenCalledTimes(1);
      expect(handler).toHaveBeenCalledWith("user");
    });

    it("closes on a fast fling below the distance threshold", () => {
      // Pin both inputs: the distance alone must not commit, the velocity must.
      const flingDistance = 40 / SHEET_HEIGHT;
      const flingVelocity = 30 / 10;
      expect(flingDistance).toBeLessThan(SNAP_DISTANCE_FRACTION);
      expect(flingVelocity).toBeGreaterThanOrEqual(FLING_VELOCITY_PX_PER_MS);
      expect(
        shouldCommitSheetGesture({
          draggedFraction: flingDistance,
          velocity: 0,
        }),
      ).toBe(false);

      drag({
        moves: [
          { y: 110, advanceMs: 10 },
          { y: 140, advanceMs: 10 },
        ],
      });

      expect(handler).toHaveBeenCalledWith("user");
    });

    it("fakes performance.now so drag velocity is deterministic", () => {
      const before = performance.now();
      vi.advanceTimersByTime(10);
      expect(performance.now()).toBeGreaterThan(before);
    });

    it("snaps back after a short slow drag", () => {
      drag({ moves: [{ y: 100 + SHEET_HEIGHT * 0.1 }] });

      expect(handler).not.toHaveBeenCalled();
      expect(sheet().style.transform).toBe("");
      expect(sheet().classList.contains("panelSettingsSheet--dragging")).toBe(
        false,
      );
      expect(isSheetOpen()).toBe(true);
    });

    it("follows the finger downward only while dragging", () => {
      touch({
        type: "pointerdown",
        target: el("panelSettingsSheetGrabber"),
        clientY: 100,
      });
      touch({
        type: "pointermove",
        target: el("panelSettingsSheetGrabber"),
        clientY: 160,
      });
      expect(sheet().style.transform).toBe("translateY(60px)");
      expect(sheet().classList.contains("panelSettingsSheet--dragging")).toBe(
        true,
      );
      touch({
        type: "pointermove",
        target: el("panelSettingsSheetGrabber"),
        clientY: 20,
      });
      expect(sheet().style.transform).toBe("translateY(0px)");
    });

    it("snaps back on pointercancel", () => {
      drag({
        moves: [{ y: 100 + SHEET_HEIGHT * 0.5 }],
        endType: "pointercancel",
      });

      expect(handler).not.toHaveBeenCalled();
      expect(sheet().style.transform).toBe("");
    });

    it("ignores a mouse pointer", () => {
      drag({ moves: [{ y: 100 + SHEET_HEIGHT * 0.5 }], pointerType: "mouse" });

      expect(handler).not.toHaveBeenCalled();
      expect(sheet().style.transform).toBe("");
    });

    it("starts no drag from inside the body", () => {
      drag({
        target: el("panelSettingsSheetBody"),
        moves: [{ y: 100 + SHEET_HEIGHT * 0.5 }],
      });

      expect(handler).not.toHaveBeenCalled();
      expect(sheet().style.transform).toBe("");
    });

    it("starts no drag when the sheet has no height", () => {
      vi.mocked(sheet().getBoundingClientRect).mockReturnValue({
        height: 0,
      } as DOMRect);
      drag({ moves: [{ y: 400 }] });

      expect(handler).not.toHaveBeenCalled();
    });

    it("tears the drag down when a forced close lands mid-drag", () => {
      touch({
        type: "pointerdown",
        target: el("panelSettingsSheetHeader"),
        clientY: 100,
      });
      touch({
        type: "pointermove",
        target: el("panelSettingsSheetHeader"),
        clientY: 200,
      });
      const removeSpy = vi.spyOn(
        el("panelSettingsSheetHeader"),
        "removeEventListener",
      );
      emit(AppEvents.TRASH_OPENED);

      expect(sheet().style.transform).toBe("");
      expect(sheet().classList.contains("panelSettingsSheet--dragging")).toBe(
        false,
      );
      // The drag's move/end listeners were actually detached.
      const removed = removeSpy.mock.calls.map((call) => call[0]);
      expect(removed).toEqual(
        expect.arrayContaining(["pointermove", "pointerup", "pointercancel"]),
      );
    });

    it("ignores move and up events from a different pointerId", () => {
      const header = el("panelSettingsSheetHeader");
      touch({ type: "pointerdown", target: header, clientY: 100 });
      touch({
        type: "pointermove",
        target: header,
        clientY: 100 + SHEET_HEIGHT * 0.5,
        pointerId: 2,
      });
      expect(sheet().style.transform).toBe("");
      expect(sheet().classList.contains("panelSettingsSheet--dragging")).toBe(
        false,
      );

      touch({
        type: "pointerup",
        target: header,
        clientY: 100 + SHEET_HEIGHT * 0.5,
        pointerId: 2,
      });
      expect(handler).not.toHaveBeenCalled();

      // The original drag is still active and still governs.
      touch({
        type: "pointermove",
        target: header,
        clientY: 100 + SHEET_HEIGHT * 0.5,
      });
      expect(sheet().style.transform).toBe(
        `translateY(${SHEET_HEIGHT * 0.5}px)`,
      );
      touch({
        type: "pointerup",
        target: header,
        clientY: 100 + SHEET_HEIGHT * 0.5,
      });
      expect(handler).toHaveBeenCalledWith("user");
    });

    it("treats a move under the tap slop as a tap: no transform, no close", () => {
      expect(TAP_SLOP_PX).toBeGreaterThan(1);
      drag({ moves: [{ y: 100 + TAP_SLOP_PX - 1 }] });

      expect(handler).not.toHaveBeenCalled();
      expect(sheet().style.transform).toBe("");
      expect(sheet().classList.contains("panelSettingsSheet--dragging")).toBe(
        false,
      );
      expect(isSheetOpen()).toBe(true);
    });

    it("ignores a second pointerdown while a drag is active", () => {
      const header = el("panelSettingsSheetHeader");
      const grabber = el("panelSettingsSheetGrabber");
      const addSpy = vi.spyOn(grabber, "addEventListener");
      touch({ type: "pointerdown", target: header, clientY: 100 });
      touch({
        type: "pointerdown",
        target: grabber,
        clientY: 300,
        pointerId: 2,
      });

      expect(addSpy).not.toHaveBeenCalled();

      // The first drag (startY 100) still governs move and up.
      touch({
        type: "pointermove",
        target: header,
        clientY: 100 + SHEET_HEIGHT * 0.5,
      });
      expect(sheet().style.transform).toBe(
        `translateY(${SHEET_HEIGHT * 0.5}px)`,
      );
      touch({
        type: "pointerup",
        target: header,
        clientY: 100 + SHEET_HEIGHT * 0.5,
      });
      expect(handler).toHaveBeenCalledTimes(1);
      expect(handler).toHaveBeenCalledWith("user");
    });
  });

  describe("drag vs close button", () => {
    it("lets a touch tap on the close button close the sheet without a drag", () => {
      setupUrlsSheet();
      stubSheetHeight();
      const handler = vi.fn();
      registerSettingsSheetCloseHandler(handler);
      const close = el("panelSettingsSheetClose");
      close.setPointerCapture = vi.fn();

      touch({ type: "pointerdown", target: close, clientY: 100 });
      touch({ type: "pointerup", target: close, clientY: 100 });
      close.click();

      expect(close.setPointerCapture).not.toHaveBeenCalled();
      expect(sheet().classList.contains("panelSettingsSheet--dragging")).toBe(
        false,
      );
      expect(sheet().style.transform).toBe("");
      expect(handler).toHaveBeenCalledWith("user");
    });

    it("does start a drag from the grabber and the non-button header area", () => {
      setupUrlsSheet();
      stubSheetHeight();
      for (const id of [
        "panelSettingsSheetGrabber",
        "panelSettingsSheetHeader",
      ]) {
        const target = el(id);
        touch({ type: "pointerdown", target, clientY: 100 });
        touch({ type: "pointermove", target, clientY: 150 });
        expect(sheet().classList.contains("panelSettingsSheet--dragging")).toBe(
          true,
        );
        touch({ type: "pointercancel", target, clientY: 150 });
      }
    });
  });

  describe("drag dismiss visual", () => {
    it("hides the sheet before clearing the inline transform and dragging class", () => {
      setupUrlsSheet();
      stubSheetHeight();
      const order: string[] = [];
      const classes = sheet().classList;
      const realAdd = classes.add.bind(classes);
      const realRemove = classes.remove.bind(classes);
      vi.spyOn(classes, "add").mockImplementation((...tokens: string[]) => {
        if (tokens.includes("hidden")) order.push("hidden");
        realAdd(...tokens);
      });
      vi.spyOn(classes, "remove").mockImplementation((...tokens: string[]) => {
        if (tokens.includes("panelSettingsSheet--dragging")) {
          order.push("dragging-cleared");
        }
        realRemove(...tokens);
      });
      const styleSpy = vi.spyOn(sheet().style, "removeProperty");

      const header = el("panelSettingsSheetHeader");
      touch({ type: "pointerdown", target: header, clientY: 100 });
      touch({ type: "pointermove", target: header, clientY: 400 });
      touch({ type: "pointerup", target: header, clientY: 400 });

      expect(order.indexOf("hidden")).toBeGreaterThanOrEqual(0);
      expect(order.indexOf("hidden")).toBeLessThan(
        order.indexOf("dragging-cleared"),
      );
      expect(styleSpy).toHaveBeenCalledWith("transform");
      expect(isSheetOpen()).toBe(false);
      expect(sheet().style.transform).toBe("");
    });

    it("runs the full shell teardown after a committed drag", () => {
      setupUrlsSheet();
      stubSheetHeight();
      const header = el("panelSettingsSheetHeader");
      touch({ type: "pointerdown", target: header, clientY: 100 });
      touch({ type: "pointermove", target: header, clientY: 400 });
      touch({ type: "pointerup", target: header, clientY: 400 });

      expect(isSheetOpen()).toBe(false);
      expect(inertBodyChildren()).toEqual([]);
      expect(gear("urls").getAttribute("aria-expanded")).toBe("false");
      expect(document.activeElement).toBe(gear("urls"));
      expect(sheet().classList.contains("panelSettingsSheet--dragging")).toBe(
        false,
      );
    });
  });

  describe("history entry", () => {
    function setCurrentEntry({ state }: { state: unknown }): void {
      historyStub.entries()[historyStub.index()] = state;
    }

    // back() records the call but never pops, so no popstate ever arrives.
    function deferBack(): void {
      historyStub.back.mockImplementation(() => {});
    }

    function openFromState({ state }: { state: unknown }): void {
      setCurrentEntry({ state });
      setupUrlsSheet();
    }

    it("pushes the spread state over an existing one, tagSheetOpen included", () => {
      const tagState = { ...BASE_STATE, tagSheetOpen: true };
      mockIsTagSheetOpen.mockReturnValue(true);
      openFromState({ state: tagState });

      expect(historyStub.pushState).toHaveBeenCalledTimes(1);
      expect(historyStub.pushState.mock.calls[0][0]).toEqual({
        ...tagState,
        panelSettingsSheetOpen: true,
      });
    });

    it("pushes only the marker when there is no prior state", () => {
      openFromState({ state: null });

      expect(historyStub.pushState.mock.calls[0][0]).toEqual({
        panelSettingsSheetOpen: true,
      });
    });

    it("captures the base state at open and clears it on close and reset", () => {
      openFromState({ state: BASE_STATE });
      expect(getSettingsSheetBaseState()).toEqual(BASE_STATE);

      el("panelSettingsSheetClose").click();
      expect(getSettingsSheetBaseState()).toBeNull();

      openGear("urls");
      expect(getSettingsSheetBaseState()).toEqual(
        historyStub.entries()[historyStub.index() - 1],
      );
      resetPopover();
      expect(getSettingsSheetBaseState()).toBeNull();
    });

    it("takes back() once on a user close and removes the entry", () => {
      openFromState({ state: BASE_STATE });
      el("panelSettingsSheetClose").click();

      expect(historyStub.back).toHaveBeenCalledTimes(1);
      expect(history.state).toEqual(BASE_STATE);
      expect(isSheetOpen()).toBe(false);
    });

    it("sets the self-back flag before back() runs", () => {
      openFromState({ state: BASE_STATE });
      let flagDuringBack = false;
      historyStub.back.mockImplementation(() => {
        flagDuringBack = isPanelSettingsSheetSelfBackPending();
      });
      el("panelSettingsSheetClose").click();

      expect(flagDuringBack).toBe(true);
    });

    it("treats a committed drag-dismiss as the same user close", () => {
      openFromState({ state: BASE_STATE });
      deferBack();
      stubSheetHeight();
      const header = el("panelSettingsSheetHeader");
      touch({ type: "pointerdown", target: header, clientY: 100 });
      touch({ type: "pointermove", target: header, clientY: 400 });
      touch({ type: "pointerup", target: header, clientY: 400 });

      expect(historyStub.back).toHaveBeenCalledTimes(1);
      expect(isPanelSettingsSheetSelfBackPending()).toBe(true);
      expect(document.activeElement).toBe(gear("urls"));
      expect(inertBodyChildren()).toEqual([]);
    });

    it("treats a user close whose entry is already stripped as forced", () => {
      openFromState({ state: BASE_STATE });
      setCurrentEntry({ state: BASE_STATE });
      el("panelSettingsSheetClose").click();

      expect(historyStub.back).not.toHaveBeenCalled();
      expect(isPanelSettingsSheetSelfBackPending()).toBe(false);
    });

    it("clears the flag after SELF_BACK_TIMEOUT_MS so a gear-open works", () => {
      openFromState({ state: BASE_STATE });
      deferBack();
      el("panelSettingsSheetClose").click();
      const pushes = historyStub.pushState.mock.calls.length;

      vi.advanceTimersByTime(SELF_BACK_TIMEOUT_MS - 1);
      expect(isPanelSettingsSheetSelfBackPending()).toBe(true);
      openGear("urls");
      expect(isSheetOpen()).toBe(false);
      expect(historyStub.pushState).toHaveBeenCalledTimes(pushes);

      vi.advanceTimersByTime(1);
      expect(isPanelSettingsSheetSelfBackPending()).toBe(false);
      openGear("urls");
      expect(isSheetOpen()).toBe(true);
    });

    it("keeps a dropped gear tap dropped after the popstate lands", () => {
      openFromState({ state: BASE_STATE });
      deferBack();
      el("panelSettingsSheetClose").click();
      openGear("urls");
      consumePanelSettingsSheetSelfBackClose();

      expect(isSheetOpen()).toBe(false);
      openGear("urls");
      expect(isSheetOpen()).toBe(true);
    });

    it("clears the flag and cancels its timer on the consuming popstate", () => {
      openFromState({ state: BASE_STATE });
      deferBack();
      el("panelSettingsSheetClose").click();

      vi.advanceTimersByTime(0);
      const withFlagTimer = vi.getTimerCount();
      expect(consumePanelSettingsSheetSelfBackClose()).toBe(true);
      expect(consumePanelSettingsSheetSelfBackClose()).toBe(false);
      expect(vi.getTimerCount()).toBe(withFlagTimer - 1);
    });

    describe("Tag sheet back in flight", () => {
      const TAG_STATE = { ...BASE_STATE, tagSheetOpen: true };

      it("drops a gear-open while isTagSheetSelfBackPending() is true", () => {
        initPopover();
        registerControlled();
        selectUTub();
        setCurrentEntry({ state: TAG_STATE });
        mockIsTagSheetSelfBackPending.mockReturnValue(true);
        const pushes = historyStub.pushState.mock.calls.length;

        openGear("urls");
        expect(isPanelSettingsSheetSelfBackPending()).toBe(true);
        expect(isSheetOpen()).toBe(false);
        expect(historyStub.pushState).toHaveBeenCalledTimes(pushes);

        mockIsTagSheetSelfBackPending.mockReturnValue(false);
        openGear("urls");
        expect(isSheetOpen()).toBe(true);
      });

      it("opens on a tagSheetOpen entry when no Tag back() is pending", () => {
        initPopover();
        registerControlled();
        selectUTub();
        // E.g. a reload with the Tag sheet's entry current: the Tag sheet is
        // closed and nothing is in flight, so the first tap must not be eaten.
        setCurrentEntry({ state: TAG_STATE });
        mockIsTagSheetOpen.mockReturnValue(false);

        openGear("urls");
        expect(isSheetOpen()).toBe(true);
      });
    });

    describe("popstate close", () => {
      it("goes through the shell handler: flushes the queue and returns focus", () => {
        const harness = setupUrlsSheet();
        harness.ctxs[0].submit({ patch: {} as never, debounce: true });
        const calls = [
          historyStub.back,
          historyStub.pushState,
          historyStub.replaceState,
        ].map((spy) => spy.mock.calls.length);

        closeSettingsSheetFromPopstate();

        expect(harness.section.save).toHaveBeenCalledTimes(1);
        expect(isSheetOpen()).toBe(false);
        expect(document.activeElement).toBe(gear("urls"));
        expect(
          [
            historyStub.back,
            historyStub.pushState,
            historyStub.replaceState,
          ].map((spy) => spy.mock.calls.length),
        ).toEqual(calls);
      });

      it("performs the bare teardown when no handler is registered", () => {
        setupUrlsSheet();
        // A reset drops the handler (and the open sheet) in one teardown.
        resetPopover();
        expect(() => closeSettingsSheetFromPopstate()).not.toThrow();
        expect(isSheetOpen()).toBe(false);
        expect(inertBodyChildren()).toEqual([]);
      });
    });

    describe("forced close", () => {
      it("strips the key once, keeps other keys and never back()s or pushes", () => {
        openFromState({ state: BASE_STATE });
        const pushes = historyStub.pushState.mock.calls.length;
        emit(AppEvents.TRASH_OPENED);

        expect(historyStub.replaceState).toHaveBeenCalledTimes(1);
        expect(historyStub.replaceState.mock.calls[0][0]).toEqual(BASE_STATE);
        expect(historyStub.back).not.toHaveBeenCalled();
        expect(historyStub.pushState).toHaveBeenCalledTimes(pushes);
        expect(isPanelSettingsSheetSelfBackPending()).toBe(false);
      });

      it("replaces with null when the marker was the only key", () => {
        openFromState({ state: null });
        emit(AppEvents.TRASH_OPENED);

        expect(historyStub.replaceState).toHaveBeenCalledTimes(1);
        expect(historyStub.replaceState.mock.calls[0][0]).toBeNull();
      });

      it("does nothing when the current entry has no key", () => {
        openFromState({ state: BASE_STATE });
        setCurrentEntry({ state: BASE_STATE });
        emit(AppEvents.TRASH_OPENED);

        expect(historyStub.replaceState).not.toHaveBeenCalled();
      });

      it("strips synchronously inside MOBILE_DECK_SWITCHED, before the caller's pushState", () => {
        openFromState({ state: BASE_STATE });
        const order: string[] = [];
        historyStub.replaceState.mockImplementation(() => {
          order.push("replace");
        });
        historyStub.pushState.mockImplementation(() => {
          order.push("push");
        });
        emit(AppEvents.MOBILE_DECK_SWITCHED, { target: "member-deck" });
        history.pushState({ mobilePanel: "members" }, "");

        expect(order).toEqual(["replace", "push"]);
      });

      it("skips the strip on a stacked UTUB_SELECTED once the entry moved on", () => {
        openFromState({ state: BASE_STATE });
        setCurrentEntry({ state: { ...BASE_STATE, tagSheetOpen: true } });
        emit(AppEvents.UTUB_SELECTED, {
          utubID: 7,
          utubName: "UTub",
          urls: [],
          tags: [],
          members: [],
          utubOwnerID: 1,
          isCurrentUserOwner: true,
          currentUserID: 1,
        });

        expect(isSheetOpen()).toBe(false);
        expect(historyStub.replaceState).not.toHaveBeenCalled();
      });
    });

    describe("close-kind mapping", () => {
      type Trigger = [string, () => void];
      const triggers: Trigger[] = [
        ["UTUB_DELETED", () => emit(AppEvents.UTUB_DELETED, { utubID: 7 })],
        [
          "FORM_MODE_CHANGED",
          () => emit(AppEvents.FORM_MODE_CHANGED, { openForm: "x" as never }),
        ],
        [
          "URL_MULTISELECT_MODE_CHANGED",
          () => emit(AppEvents.URL_MULTISELECT_MODE_CHANGED, { active: true }),
        ],
        [
          "CROSS_UTUB_SEARCH_VISIBILITY_CHANGED",
          () =>
            emit(AppEvents.CROSS_UTUB_SEARCH_VISIBILITY_CHANGED, {
              active: true,
            }),
        ],
        ["TRASH_OPENED", () => emit(AppEvents.TRASH_OPENED)],
        [
          "LEFT_PANEL_COLLAPSE_CHANGED",
          () =>
            emit(AppEvents.LEFT_PANEL_COLLAPSE_CHANGED, { collapsed: true }),
        ],
        [
          "MOBILE_DECK_SWITCHED",
          () => emit(AppEvents.MOBILE_DECK_SWITCHED, { target: "member-deck" }),
        ],
        ["breakpoint crossing", () => breakpoint.cross({ matches: false })],
      ];

      it.each(triggers)(
        "%s is a forced close (strip, no back())",
        (_n, fire) => {
          openFromState({ state: BASE_STATE });
          fire();

          expect(isSheetOpen()).toBe(false);
          expect(historyStub.replaceState).toHaveBeenCalledTimes(1);
          expect(historyStub.back).not.toHaveBeenCalled();
        },
      );

      const userCloses: Array<[string, () => void]> = [
        ["close button", () => el("panelSettingsSheetClose").click()],
        ["backdrop", () => backdrop().click()],
        ["Escape", () => pressKey({ key: "Escape" })],
      ];

      it.each(userCloses)("maps the %s to a user close", (_name, close) => {
        openFromState({ state: BASE_STATE });
        close();

        expect(isSheetOpen()).toBe(false);
        expect(historyStub.back).toHaveBeenCalledTimes(1);
        expect(historyStub.replaceState).not.toHaveBeenCalled();
      });
    });

    describe("reset", () => {
      it("drops the entry without back() and clears base state and flag", () => {
        openFromState({ state: BASE_STATE });
        resetPopover();

        expect(historyStub.back).not.toHaveBeenCalled();
        expect(historyStub.replaceState).toHaveBeenCalledTimes(1);
        expect(getSettingsSheetBaseState()).toBeNull();
        expect(isPanelSettingsSheetSelfBackPending()).toBe(false);
      });

      it("clears a pending self-back flag and its timer", () => {
        openFromState({ state: BASE_STATE });
        deferBack();
        el("panelSettingsSheetClose").click();
        expect(isPanelSettingsSheetSelfBackPending()).toBe(true);

        resetPopover();

        expect(isPanelSettingsSheetSelfBackPending()).toBe(false);
        expect(vi.getTimerCount()).toBe(0);
      });
    });
  });
});
