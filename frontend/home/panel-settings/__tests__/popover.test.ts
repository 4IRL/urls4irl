import { $ } from "../../../lib/globals.js";
import { AppEvents, emit } from "../../../lib/event-bus.js";
import { resetStore, setState } from "../../../store/app-store.js";
import { dismissActiveTip, maybeShowNextTip } from "../../onboarding/nudges.js";
import { closeAllMemberRowMenus } from "../../members/row-menu.js";
import { fitUTubHeaderAndSubheader } from "../../utubs/header-fit.js";
import { hideTooltip } from "../../../lib/tooltips.js";
import type { ResolvedUtubSettings } from "../../../types/settings.js";
import { announceSettingsStatus } from "../announce.js";
import { resyncSettings } from "../client.js";
import { resetPopover, initPopover } from "../popover.js";
import { DEBOUNCE_MS } from "../queue.js";
import { _resetRegistryForTests } from "../registry.js";
import { isPanelSettingsBusy, isPanelSettingsOpen } from "../state.js";
import type { SectionContext, SectionPatch } from "../types.js";
import type { BreakpointMock, Harness } from "./helpers.js";
import {
  FIXTURE,
  OTHER_UTUB_ID,
  SETTINGS,
  UTUB_ID,
  el,
  gear,
  mockBreakpoint,
  openGear,
  pressKey,
  registerControlled,
  selectUTub,
  summaries,
} from "./helpers.js";

// Writes straight to the live region so tests can both read it and count calls.
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
// sheet.ts reads isTagSheetSelfBackPending; the real module would load the home module graph.
vi.mock("../../tags/sheet.js", () => ({
  isTagSheetOpen: () => false,
  isTagSheetSelfBackPending: () => false,
}));
function popover(): HTMLElement {
  return el("panelSettingsPopover");
}

function isGearVisible(panel: string): boolean {
  return !gear(panel).classList.contains("hidden");
}

function isOpen(): boolean {
  return !popover().classList.contains("hidden");
}

function announced(): string {
  vi.advanceTimersByTime(0);
  return el("PanelSettingsAnnouncement").textContent ?? "";
}

function lastCtx(harness: Harness): SectionContext {
  return harness.ctxs[harness.ctxs.length - 1];
}

async function settle(): Promise<void> {
  await vi.advanceTimersByTimeAsync(0);
}

describe("panel settings popover", () => {
  const originalMatchMedia = window.matchMedia;
  let breakpoint: BreakpointMock;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    document.body.innerHTML = FIXTURE;
    resetStore();
    breakpoint = mockBreakpoint({ matches: false });
  });

  afterEach(() => {
    resetPopover();
    _resetRegistryForTests();
    window.matchMedia = originalMatchMedia;
    vi.useRealTimers();
  });

  describe("gear visibility", () => {
    it("keeps every gear hidden with no registered section", () => {
      initPopover();
      selectUTub();
      for (const panel of ["utubs", "members", "tags", "urls"]) {
        expect(isGearVisible(panel)).toBe(false);
      }
    });

    it("reveals a per-UTub gear only with a section and an active UTub", () => {
      initPopover();
      registerControlled();

      expect(isGearVisible("urls")).toBe(false);
      selectUTub();
      expect(isGearVisible("urls")).toBe(true);
      expect(isGearVisible("members")).toBe(false);

      setState({ activeUTubID: null });
      expect(isGearVisible("urls")).toBe(false);
    });

    it("reveals the UTubs gear without an active UTub", () => {
      initPopover();
      registerControlled({
        id: "utubs-pref",
        panel: "utubs",
        scope: "user",
        userKind: "global",
      });
      expect(isGearVisible("utubs")).toBe(true);
    });

    it("reveals a gear for a section registered before init", () => {
      registerControlled({
        id: "utubs-pref",
        panel: "utubs",
        scope: "user",
        userKind: "global",
      });
      initPopover();
      expect(isGearVisible("utubs")).toBe(true);
    });

    it("keeps the gear visible across the breakpoint and points aria-controls at the active surface", () => {
      initPopover();
      registerControlled({
        id: "utubs-pref",
        panel: "utubs",
        scope: "user",
        userKind: "global",
      });
      expect(isGearVisible("utubs")).toBe(true);
      expect(gear("utubs").getAttribute("aria-controls")).toBe(
        "panelSettingsPopover",
      );

      breakpoint.cross({ matches: true });
      expect(isGearVisible("utubs")).toBe(true);
      expect(gear("utubs").getAttribute("aria-controls")).toBe(
        "panelSettingsSheet",
      );

      breakpoint.cross({ matches: false });
      expect(isGearVisible("utubs")).toBe(true);
      expect(gear("utubs").getAttribute("aria-controls")).toBe(
        "panelSettingsPopover",
      );
    });

    it("never uses the visible classes, and re-fits the header on a change", () => {
      initPopover();
      vi.mocked(fitUTubHeaderAndSubheader).mockClear();
      registerControlled({
        id: "utubs-pref",
        panel: "utubs",
        scope: "user",
        userKind: "global",
      });

      expect(gear("utubs").classList.contains("visible")).toBe(false);
      expect(fitUTubHeaderAndSubheader).toHaveBeenCalledTimes(1);
    });

    it("hides the gear again when its last section unregisters", () => {
      initPopover();
      const harness = registerControlled({
        id: "utubs-pref",
        panel: "utubs",
        scope: "user",
        userKind: "global",
      });
      harness.unregister();
      expect(isGearVisible("utubs")).toBe(false);
    });
  });

  describe("open and close", () => {
    function setupUrls(): Harness {
      initPopover();
      const harness = registerControlled();
      selectUTub();
      return harness;
    }

    it("opens on gear click with the dialog named after the gear", () => {
      setupUrls();
      openGear("urls");

      expect(isOpen()).toBe(true);
      expect(gear("urls").getAttribute("aria-expanded")).toBe("true");
      expect(popover().getAttribute("aria-label")).toBe("URLs settings");
      expect(popover().hasAttribute("aria-labelledby")).toBe(false);
      expect(isPanelSettingsOpen()).toBe(true);
      expect(isPanelSettingsBusy()).toBe(true);
    });

    it("closes row menus, the active tip and the gear tooltip when opening", () => {
      setupUrls();
      openGear("urls");

      expect(closeAllMemberRowMenus).toHaveBeenCalledTimes(1);
      expect(dismissActiveTip).toHaveBeenCalledWith({ markSeen: false });
      expect(hideTooltip).toHaveBeenCalledWith(gear("urls"));
    });

    it("prevents the gear tooltip from re-showing while expanded", () => {
      setupUrls();
      const beforeOpen = new Event("show.bs.tooltip", { cancelable: true });
      gear("urls").dispatchEvent(beforeOpen);
      expect(beforeOpen.defaultPrevented).toBe(false);

      openGear("urls");
      const whileOpen = new Event("show.bs.tooltip", { cancelable: true });
      gear("urls").dispatchEvent(whileOpen);
      expect(whileOpen.defaultPrevented).toBe(true);
    });

    it("renders the section chrome: title, scope label, status slot, note slot", () => {
      setupUrls();
      openGear("urls");

      const wrapper = popover().querySelector(
        '[data-section-id="sort"]',
      ) as HTMLElement;
      expect(wrapper.querySelector("h2")?.textContent).toBe("Sort");
      expect(wrapper.querySelector(".panelSettingsScope")?.textContent).toBe(
        "Shared with this UTub",
      );
      expect(wrapper.querySelector(".panelSettingsStatus")).not.toBeNull();
      expect(
        wrapper.querySelector(".panelSettingsReadOnlyNote"),
      ).not.toBeNull();
    });

    it("labels a user-scope section as just for you", () => {
      initPopover();
      registerControlled({
        id: "utubs-pref",
        panel: "utubs",
        scope: "user",
        userKind: "global",
      });
      openGear("utubs");
      expect(popover().querySelector(".panelSettingsScope")?.textContent).toBe(
        "Just for you",
      );
    });

    it("shows the empty message for a section that renders nothing", () => {
      initPopover();
      registerControlled({ render: vi.fn() });
      selectUTub();
      openGear("urls");
      expect(popover().textContent).toContain("No settings available");
    });

    it("moves focus to the first control on open", () => {
      setupUrls();
      openGear("urls");
      expect(document.activeElement).toBe(el("sort-input"));
    });

    it("moves focus to the dialog when there is no control", () => {
      initPopover();
      registerControlled({
        render: vi.fn(({ container }) => {
          container.textContent = "static";
        }),
      });
      selectUTub();
      openGear("urls");
      expect(document.activeElement).toBe(popover());
    });

    it("toggles closed on a second gear click and returns focus to the gear", () => {
      setupUrls();
      openGear("urls");
      openGear("urls");

      expect(isOpen()).toBe(false);
      expect(gear("urls").getAttribute("aria-expanded")).toBe("false");
      expect(document.activeElement).toBe(gear("urls"));
    });

    it("clears the open flag one tick after close and re-arms the nudges", () => {
      setupUrls();
      openGear("urls");
      openGear("urls");

      expect(isPanelSettingsOpen()).toBe(true);
      vi.advanceTimersByTime(0);
      expect(isPanelSettingsOpen()).toBe(false);
      expect(maybeShowNextTip).toHaveBeenCalledTimes(1);
    });

    it("does not clear the open flag when reopened within the same tick", () => {
      setupUrls();
      openGear("urls");
      openGear("urls");
      openGear("urls");
      vi.advanceTimersByTime(0);
      expect(isPanelSettingsOpen()).toBe(true);
    });

    it("switching gears closes the other popover without announcing", () => {
      initPopover();
      registerControlled();
      registerControlled({ id: "members-pref", panel: "members" });
      selectUTub();
      openGear("urls");
      openGear("members");

      expect(gear("urls").getAttribute("aria-expanded")).toBe("false");
      expect(gear("members").getAttribute("aria-expanded")).toBe("true");
      expect(popover().getAttribute("aria-label")).toBe("Members settings");
      expect(isOpen()).toBe(true);
      expect(announced()).toBe("");
    });

    it("drops a stale aria-label when the opening gear has none", () => {
      setupUrls();
      openGear("urls");
      openGear("urls");
      gear("urls").removeAttribute("aria-label");
      openGear("urls");
      expect(popover().hasAttribute("aria-label")).toBe(false);
    });

    it("calls the section cleanup on re-render and on close", () => {
      const harness = setupUrls();
      openGear("urls");
      expect(harness.cleanup).not.toHaveBeenCalled();

      setState({ isCurrentUTubLocked: true });
      expect(harness.cleanup).toHaveBeenCalledTimes(1);

      openGear("urls");
      expect(harness.cleanup).toHaveBeenCalledTimes(2);
    });

    it("ignores a gear click for a panel with no sections", () => {
      initPopover();
      openGear("tags");
      expect(isOpen()).toBe(false);
    });

    it("announces nothing for a user-initiated close", () => {
      setupUrls();
      openGear("urls");
      openGear("urls");
      expect(announced()).toBe("");
    });
  });

  describe("positioning", () => {
    function placeGear({
      right,
      bottom,
    }: {
      right: number;
      bottom: number;
    }): void {
      vi.spyOn(gear("urls"), "getBoundingClientRect").mockReturnValue({
        right,
        bottom,
        left: right - 30,
        top: bottom - 30,
        width: 30,
        height: 30,
        x: right - 30,
        y: bottom - 30,
        toJSON: () => ({}),
      });
    }

    function sizePopover({
      width,
      height,
    }: {
      width: number;
      height: number;
    }): void {
      Object.defineProperty(popover(), "offsetWidth", {
        configurable: true,
        value: width,
      });
      Object.defineProperty(popover(), "offsetHeight", {
        configurable: true,
        value: height,
      });
    }

    beforeEach(() => {
      initPopover();
      registerControlled();
      selectUTub();
      Object.defineProperty(window, "innerWidth", {
        configurable: true,
        value: 1280,
      });
      Object.defineProperty(window, "innerHeight", {
        configurable: true,
        value: 800,
      });
      sizePopover({ width: 340, height: 200 });
    });

    it("sits below the gear, right edges aligned", () => {
      placeGear({ right: 900, bottom: 100 });
      openGear("urls");
      expect(popover().style.left).toBe("560px");
      expect(popover().style.top).toBe("106px");
    });

    it("clamps into the viewport on every side", () => {
      placeGear({ right: 100, bottom: 790 });
      openGear("urls");
      expect(popover().style.left).toBe("8px");
      expect(popover().style.top).toBe("592px");
    });

    it("repositions on window resize", () => {
      placeGear({ right: 900, bottom: 100 });
      openGear("urls");

      placeGear({ right: 700, bottom: 120 });
      window.dispatchEvent(new Event("resize"));
      expect(popover().style.left).toBe("360px");
      expect(popover().style.top).toBe("126px");
    });
  });

  describe("keyboard", () => {
    function setupTwoControls(): void {
      initPopover();
      registerControlled({
        render: vi.fn(({ container }) => {
          container.innerHTML =
            '<input id="first-input" /><input id="last-input" />';
        }),
      });
      selectUTub();
      openGear("urls");
    }

    it("wraps Tab from the last control to the first", () => {
      setupTwoControls();
      el("last-input").focus();
      const event = pressKey({ key: "Tab", target: el("last-input") });
      expect(event.defaultPrevented).toBe(true);
      expect(document.activeElement).toBe(el("first-input"));
    });

    it("wraps Shift+Tab from the first control to the last", () => {
      setupTwoControls();
      el("first-input").focus();
      const event = pressKey({
        key: "Tab",
        shiftKey: true,
        target: el("first-input"),
      });
      expect(event.defaultPrevented).toBe(true);
      expect(document.activeElement).toBe(el("last-input"));
    });

    it("leaves Tab between inner controls alone", () => {
      setupTwoControls();
      el("first-input").focus();
      const event = pressKey({ key: "Tab", target: el("first-input") });
      expect(event.defaultPrevented).toBe(false);
    });

    it("keeps focus on the dialog when there are no focusable descendants", () => {
      initPopover();
      registerControlled({
        render: vi.fn(({ container }) => {
          container.textContent = "static";
        }),
      });
      selectUTub();
      openGear("urls");

      const event = pressKey({ key: "Tab", target: popover() });
      expect(event.defaultPrevented).toBe(true);
      expect(document.activeElement).toBe(popover());
    });

    it("Escape closes, prevents default and returns focus to the gear", () => {
      setupTwoControls();
      const event = pressKey({ key: "Escape", target: el("first-input") });

      expect(event.defaultPrevented).toBe(true);
      expect(isOpen()).toBe(false);
      expect(document.activeElement).toBe(gear("urls"));
    });

    it("skips hidden inputs and CSS-hidden controls when wrapping Tab", () => {
      initPopover();
      registerControlled({
        render: vi.fn(({ container }) => {
          container.innerHTML =
            '<input id="first-input" /><input id="last-input" />' +
            '<input type="hidden" id="hidden-input" />' +
            '<input id="css-hidden-input" class="hidden" />';
        }),
      });
      selectUTub();
      openGear("urls");

      el("last-input").focus();
      const event = pressKey({ key: "Tab", target: el("last-input") });
      expect(event.defaultPrevented).toBe(true);
      expect(document.activeElement).toBe(el("first-input"));
    });

    it("ignores other keys and Escape when closed", () => {
      setupTwoControls();
      const other = pressKey({ key: "a", target: el("first-input") });
      expect(other.defaultPrevented).toBe(false);
      expect(isOpen()).toBe(true);

      openGear("urls");
      const escape = pressKey({ key: "Escape" });
      expect(escape.defaultPrevented).toBe(false);
    });
  });

  describe("escape ordering", () => {
    const seenOpen: boolean[] = [];
    const recordFlag = (): void => {
      seenOpen.push(isPanelSettingsOpen());
    };

    function bindSiblings(): void {
      document.addEventListener("keydown", recordFlag);
      $(document).on("keydown.siblingTest", recordFlag);
    }

    function openWithControl(): void {
      registerControlled();
      selectUTub();
      openGear("urls");
    }

    afterEach(() => {
      document.removeEventListener("keydown", recordFlag);
      $(document).off("keydown.siblingTest");
      seenOpen.length = 0;
    });

    it("sibling handlers bound before the shell still see the open flag", () => {
      bindSiblings();
      initPopover();
      openWithControl();

      pressKey({ key: "Escape", target: el("sort-input") });

      expect(seenOpen).toEqual([true, true]);
      expect(isOpen()).toBe(false);
      vi.advanceTimersByTime(0);
      expect(isPanelSettingsOpen()).toBe(false);
    });

    it("sibling handlers bound after the shell still see the open flag", () => {
      initPopover();
      bindSiblings();
      openWithControl();

      pressKey({ key: "Escape", target: el("sort-input") });

      expect(seenOpen).toEqual([true, true]);
      expect(isOpen()).toBe(false);
      vi.advanceTimersByTime(0);
      expect(isPanelSettingsOpen()).toBe(false);
    });

    it("a nested layer that stops propagation keeps the popover open", () => {
      initPopover();
      openWithControl();
      el("sort-input").addEventListener("keydown", (event) => {
        event.stopPropagation();
      });

      pressKey({ key: "Escape", target: el("sort-input") });

      expect(isOpen()).toBe(true);
    });
  });

  describe("outside pointerdown", () => {
    beforeEach(() => {
      initPopover();
      registerControlled();
      selectUTub();
      openGear("urls");
    });

    function pointerDown(target: HTMLElement): void {
      target.dispatchEvent(new Event("pointerdown", { bubbles: true }));
    }

    it("closes when the pointer goes down outside", () => {
      pointerDown(el("outside"));
      expect(isOpen()).toBe(false);
      expect(announced()).toBe("");
    });

    it("closes even when the target stops pointerdown propagation (a row-menu kebab)", () => {
      el("outside").addEventListener("pointerdown", (event) => {
        event.stopPropagation();
      });
      pointerDown(el("outside"));
      expect(isOpen()).toBe(false);
    });

    it("stays open for a drag that starts inside and is released outside", () => {
      pointerDown(el("sort-input"));
      el("outside").dispatchEvent(new Event("pointerup", { bubbles: true }));
      el("outside").dispatchEvent(new Event("click", { bubbles: true }));
      expect(isOpen()).toBe(true);
    });

    it("returns focus to the gear when the click lands on blank space", () => {
      pointerDown(document.body);
      expect(isOpen()).toBe(false);
      vi.advanceTimersByTime(0);
      expect(document.activeElement).toBe(gear("urls"));
    });

    it("leaves focus on a focusable control that took it from the click", () => {
      pointerDown(el("outside"));
      el("outside").focus();
      vi.advanceTimersByTime(0);
      expect(document.activeElement).toBe(el("outside"));
    });

    it("stays open for a pointerdown inside the popover", () => {
      pointerDown(el("sort-input"));
      expect(isOpen()).toBe(true);
    });

    it("ignores gear pointerdowns (the gear click toggles)", () => {
      pointerDown(gear("urls"));
      expect(isOpen()).toBe(true);
    });
  });

  describe("forced close triggers", () => {
    function setupUrls(): void {
      initPopover();
      registerControlled();
      selectUTub();
      openGear("urls");
    }

    function expectForcedClose(): void {
      expect(isOpen()).toBe(false);
      expect(announced()).toBe("Settings closed");
    }

    it("closes on UTUB_SELECTED, including a same-id rebuild", () => {
      setupUrls();
      emit(AppEvents.UTUB_SELECTED, {
        utubID: UTUB_ID,
        utubName: "UTub",
        urls: [],
        tags: [],
        members: [],
        utubOwnerID: 1,
        isCurrentUserOwner: true,
        currentUserID: 1,
      });
      expectForcedClose();
    });

    it("closes on UTUB_DELETED", () => {
      setupUrls();
      emit(AppEvents.UTUB_DELETED, { utubID: UTUB_ID });
      expectForcedClose();
    });

    it("closes when the active UTub becomes null", () => {
      setupUrls();
      setState({ activeUTubID: null });
      expectForcedClose();
    });

    it("closes when the active UTub changes", () => {
      setupUrls();
      selectUTub({ utubID: OTHER_UTUB_ID });
      expectForcedClose();
    });

    it("closes on a role flip", () => {
      setupUrls();
      setState({ isCurrentUserOwner: false, isCoCreator: true });
      expectForcedClose();
    });

    it("closes when the settings slice becomes null", () => {
      setupUrls();
      setState({ settings: null });
      expectForcedClose();
    });

    it("closes on an open form, but not on a form closing", () => {
      setupUrls();
      emit(AppEvents.FORM_MODE_CHANGED, { openForm: null });
      expect(isOpen()).toBe(true);
      emit(AppEvents.FORM_MODE_CHANGED, { openForm: "createURL" as never });
      expectForcedClose();
    });

    it("closes when multi-select starts, not when it ends", () => {
      setupUrls();
      emit(AppEvents.URL_MULTISELECT_MODE_CHANGED, { active: false });
      expect(isOpen()).toBe(true);
      emit(AppEvents.URL_MULTISELECT_MODE_CHANGED, { active: true });
      expectForcedClose();
    });

    it("closes when cross-UTub search starts", () => {
      setupUrls();
      emit(AppEvents.CROSS_UTUB_SEARCH_VISIBILITY_CHANGED, { active: true });
      expectForcedClose();
    });

    it("closes on TRASH_OPENED", () => {
      setupUrls();
      emit(AppEvents.TRASH_OPENED);
      expectForcedClose();
    });

    it("closes on a Bootstrap modal opening", () => {
      setupUrls();
      const modal = document.createElement("div");
      document.body.append(modal);
      $(modal).trigger("show.bs.modal");
      expectForcedClose();
    });

    it("closes on left-panel collapse", () => {
      setupUrls();
      emit(AppEvents.LEFT_PANEL_COLLAPSE_CHANGED, { collapsed: true });
      expectForcedClose();
    });

    it("closes when the breakpoint is crossed", () => {
      setupUrls();
      breakpoint.cross({ matches: true });
      expectForcedClose();
    });

    it("closes when the last section unregisters", () => {
      initPopover();
      const harness = registerControlled();
      selectUTub();
      openGear("urls");
      harness.unregister();
      expectForcedClose();
    });

    it("closes only its own deck's popover on a deck collapse", () => {
      initPopover();
      registerControlled({ id: "members-pref", panel: "members" });
      selectUTub();
      openGear("members");

      emit(AppEvents.DECK_COLLAPSE_CHANGED, { deck: "tags", collapsed: true });
      emit(AppEvents.DECK_COLLAPSE_CHANGED, {
        deck: "members",
        collapsed: false,
      });
      expect(isOpen()).toBe(true);

      emit(AppEvents.DECK_COLLAPSE_CHANGED, {
        deck: "members",
        collapsed: true,
      });
      expectForcedClose();
    });

    it("never closes the URLs popover on a deck collapse", () => {
      setupUrls();
      for (const deck of ["utubs", "members", "tags"] as const) {
        emit(AppEvents.DECK_COLLAPSE_CHANGED, { deck, collapsed: true });
      }
      expect(isOpen()).toBe(true);
    });

    it("a lock flip never closes a popover", () => {
      setupUrls();
      setState({ isCurrentUTubLocked: true });
      expect(isOpen()).toBe(true);
    });
  });

  describe("UTubs popover exemptions", () => {
    beforeEach(() => {
      initPopover();
      registerControlled({
        id: "utubs-pref",
        panel: "utubs",
        scope: "user",
        userKind: "global",
      });
      selectUTub();
      openGear("utubs");
    });

    it("ignores UTub selection, deletion, active-UTub, role and lock changes", () => {
      emit(AppEvents.UTUB_SELECTED, {
        utubID: UTUB_ID,
        utubName: "UTub",
        urls: [],
        tags: [],
        members: [],
        utubOwnerID: 1,
        isCurrentUserOwner: true,
        currentUserID: 1,
      });
      emit(AppEvents.UTUB_DELETED, { utubID: UTUB_ID });
      setState({ isCurrentUserOwner: false, isCoCreator: true });
      setState({ isCurrentUTubLocked: true });
      setState({ activeUTubID: null });

      expect(isOpen()).toBe(true);
    });

    it("still closes for an open form", () => {
      emit(AppEvents.FORM_MODE_CHANGED, { openForm: "createURL" as never });
      expect(isOpen()).toBe(false);
    });
  });

  describe("focus rules on a forced close", () => {
    beforeEach(() => {
      initPopover();
      registerControlled();
      selectUTub();
      openGear("urls");
    });

    it("restores focus to the gear when focus was inside the popover", () => {
      el("sort-input").focus();
      emit(AppEvents.TRASH_OPENED);
      expect(document.activeElement).toBe(gear("urls"));
    });

    it("restores focus when focus was on the body", () => {
      (document.activeElement as HTMLElement).blur();
      emit(AppEvents.TRASH_OPENED);
      expect(document.activeElement).toBe(gear("urls"));
    });

    it("leaves focus alone when it moved elsewhere", () => {
      el("outside").focus();
      emit(AppEvents.TRASH_OPENED);
      expect(document.activeElement).toBe(el("outside"));
    });

    it("falls back to the deck header button when the gear is hidden", () => {
      el("sort-input").focus();
      setState({ activeUTubID: null });
      // The gear hid itself with the UTub: URLs falls back to its header button.
      expect(document.activeElement).toBe(el("urlBtnCreate"));
    });

    it("falls back to the deck header button when the last section unregisters", () => {
      const only = registerControlled({ id: "only-members", panel: "members" });
      openGear("members");
      expect(document.activeElement).toBe(el("sort-input"));
      only.unregister();
      expect(isOpen()).toBe(false);
      expect(document.activeElement).toBe(el("MemberDeckHeaderAndCaret"));
    });

    it("restores focus to the still-visible gear when the breakpoint is crossed", () => {
      el("sort-input").focus();
      breakpoint.cross({ matches: true });
      expect(isGearVisible("urls")).toBe(true);
      expect(document.activeElement).toBe(gear("urls"));
    });

    it("leaves focus in the cross-UTub search input when it opens (Ctrl/Cmd+K)", () => {
      const search = document.createElement("input");
      search.id = "crossUtubSearchInput";
      document.body.append(search);
      search.focus();
      emit(AppEvents.CROSS_UTUB_SEARCH_VISIBILITY_CHANGED, { active: true });

      expect(isOpen()).toBe(false);
      expect(document.activeElement).toBe(search);
    });
  });

  describe("lock flip while open", () => {
    beforeEach(() => {
      initPopover();
    });

    it("re-renders read-only with the note, announces, and stays open", () => {
      const harness = registerControlled();
      selectUTub();
      openGear("urls");
      expect(lastCtx(harness).canWrite).toBe(true);

      setState({ isCurrentUTubLocked: true });

      expect(isOpen()).toBe(true);
      expect(lastCtx(harness).canWrite).toBe(false);
      const note = popover().querySelector(
        ".panelSettingsReadOnlyNote",
      ) as HTMLElement;
      expect(note.hidden).toBe(false);
      expect(note.textContent).toBe("UTub is locked");
      expect(announced()).toBe("UTub is locked");
    });

    it("restores write access when the UTub unlocks", () => {
      const harness = registerControlled();
      selectUTub({ locked: true });
      openGear("urls");
      expect(lastCtx(harness).canWrite).toBe(false);

      setState({ isCurrentUTubLocked: false });
      expect(lastCtx(harness).canWrite).toBe(true);
      expect(
        (popover().querySelector(".panelSettingsReadOnlyNote") as HTMLElement)
          .hidden,
      ).toBe(true);
    });

    it("shows the managers-only note to a non-manager", () => {
      registerControlled();
      selectUTub({ owner: false });
      openGear("urls");
      expect(popover().textContent).toContain(
        "Only UTub managers can change this",
      );
    });

    it("keeps the focused control focused across the re-render", () => {
      registerControlled();
      selectUTub();
      openGear("urls");
      el("sort-input").focus();
      setState({ isCurrentUTubLocked: true });
      expect(document.activeElement).toBe(el("sort-input"));
    });

    it("keeps focus inside the popover when the focused control has no id", () => {
      registerControlled({
        render: vi.fn(({ container }) => {
          container.innerHTML = "<button>Go</button>";
        }),
      });
      selectUTub();
      openGear("urls");
      const before = popover().querySelector("button") as HTMLElement;
      before.focus();

      setState({ isCurrentUTubLocked: true });

      const after = popover().querySelector("button") as HTMLElement;
      expect(after).not.toBe(before);
      expect(document.activeElement).toBe(after);
    });

    it("leaves a user-scope section writable under a lock", () => {
      const harness = registerControlled({
        id: "user-pref",
        panel: "urls",
        scope: "user",
        userKind: "global",
      });
      selectUTub();
      openGear("urls");
      setState({ isCurrentUTubLocked: true });
      expect(lastCtx(harness).canWrite).toBe(true);
    });
  });

  describe("queue sink", () => {
    let harness: Harness;

    beforeEach(() => {
      initPopover();
      harness = registerControlled();
      selectUTub();
      openGear("urls");
    });

    function wrapper(): HTMLElement {
      return popover().querySelector('[data-section-id="sort"]') as HTMLElement;
    }

    function status(): HTMLElement {
      return wrapper().querySelector(".panelSettingsStatus") as HTMLElement;
    }

    function edit(patch: SectionPatch = { sort: "new" }): void {
      lastCtx(harness).submit({ patch });
    }

    it("marks the section busy while saving", async () => {
      edit();
      await settle();

      expect(wrapper().getAttribute("aria-busy")).toBe("true");
      expect(status().dataset.state).toBe("saving");
      expect(status().textContent).toBe("Saving…");
      expect(isPanelSettingsBusy()).toBe(true);
    });

    it("keeps controls interactive while a save is in flight", async () => {
      edit();
      await settle();

      const input = el("sort-input") as HTMLInputElement;
      expect(wrapper().getAttribute("aria-busy")).toBe("true");
      expect(input.disabled).toBe(false);
      input.value = "typed during save";
      expect(input.value).toBe("typed during save");
    });

    it("shows Saved, announces it and clears it after the dwell", async () => {
      edit();
      await settle();
      harness.pending[0].resolve({ outcome: "ok" });
      await settle();

      expect(wrapper().hasAttribute("aria-busy")).toBe(false);
      expect(status().dataset.state).toBe("saved");
      expect(announced()).toBe("Sort: Saved");

      await vi.advanceTimersByTimeAsync(1500);
      expect(status().textContent).toBe("");
      expect(status().dataset.state).toBeUndefined();
    });

    it("announces Saved plus the notice as one message, keeping the visible status plain", async () => {
      edit();
      await settle();
      vi.mocked(announceSettingsStatus).mockClear();
      harness.pending[0].resolve({ outcome: "ok", notice: "Reset to https." });
      await settle();

      expect(status().textContent).toBe("Saved");
      expect(announceSettingsStatus).toHaveBeenCalledTimes(1);
      expect(announced()).toBe("Sort: Saved. Reset to https.");
    });

    it("rolls back, shows a persistent message tied to the control, and announces on error", async () => {
      el("sort-input").focus();
      edit();
      await settle();
      harness.pending[0].resolve({ outcome: "error", resync: false });
      await settle();

      expect(status().dataset.state).toBe("error");
      expect(status().textContent).toBe("Couldn't save — reverted");
      expect(status().hasAttribute("role")).toBe(false);
      expect(el("sort-input").getAttribute("aria-describedby")).toBe(
        status().id,
      );
      expect(harness.section.render).toHaveBeenCalledTimes(2);
      expect(document.activeElement).toBe(el("sort-input"));
      expect(announced()).toBe("Sort: Couldn't save");
      expect(wrapper().hasAttribute("aria-busy")).toBe(false);
    });

    it("clears the error on the section's next edit", async () => {
      edit();
      await settle();
      harness.pending[0].resolve({ outcome: "error", resync: false });
      await settle();
      expect(status().dataset.state).toBe("error");

      edit({ sort: "newer" });
      expect(status().dataset.state).not.toBe("error");
      expect(status().textContent).not.toContain("reverted");
      expect(el("sort-input").hasAttribute("aria-describedby")).toBe(false);
    });

    it("clears the error on a successful save", async () => {
      edit();
      await settle();
      harness.pending[0].resolve({ outcome: "error", resync: false });
      await settle();

      edit({ sort: "newer" });
      await settle();
      harness.pending[1].resolve({ outcome: "ok" });
      await settle();
      expect(status().dataset.state).toBe("saved");
    });

    it("drops the error with the popover, so a reopen starts clean", async () => {
      edit();
      await settle();
      harness.pending[0].resolve({ outcome: "error", resync: false });
      await settle();
      const errorStatus = status();
      expect(errorStatus.dataset.state).toBe("error");

      openGear("urls");
      expect(errorStatus.isConnected).toBe(false);
      openGear("urls");
      expect(status()).not.toBe(errorStatus);
      expect(status().textContent).toBe("");
      expect(el("sort-input").hasAttribute("aria-describedby")).toBe(false);
    });

    it("clears the saving indicator on a stale outcome", async () => {
      edit();
      await settle();
      expect(wrapper().getAttribute("aria-busy")).toBe("true");

      // A stale-with-failure answer: the queue reports no terminal status.
      harness.pending[0].resolve({ outcome: "stale", failed: true });
      await vi.advanceTimersByTimeAsync(500);

      expect(wrapper().hasAttribute("aria-busy")).toBe(false);
      expect(status().dataset.state).toBeUndefined();
      expect(announced()).toBe("Sort: Couldn't save");
    });

    it("clears the saving indicator on a locked outcome and goes read-only", async () => {
      edit();
      await settle();
      harness.pending[0].resolve({ outcome: "locked" });
      await settle();

      expect(wrapper().hasAttribute("aria-busy")).toBe(false);
      expect(lastCtx(harness).canWrite).toBe(false);
      expect(
        (wrapper().querySelector(".panelSettingsReadOnlyNote") as HTMLElement)
          .textContent,
      ).toBe("UTub is locked");
      expect(announced()).toBe("UTub is locked");
    });

    it("clears the saving indicator on a forbidden outcome and shows managers-only", async () => {
      edit();
      await settle();
      harness.pending[0].resolve({ outcome: "forbidden" });
      await settle();

      expect(wrapper().hasAttribute("aria-busy")).toBe(false);
      expect(lastCtx(harness).canWrite).toBe(false);
      expect(announced()).toBe("Only UTub managers can change this");
    });

    it("refuses further edits once forced read-only, until the popover closes", async () => {
      edit();
      await settle();
      harness.pending[0].resolve({ outcome: "locked" });
      await settle();

      edit({ sort: "again" });
      await settle();
      expect(harness.section.save).toHaveBeenCalledTimes(1);

      openGear("urls");
      openGear("urls");
      expect(lastCtx(harness).canWrite).toBe(true);
    });

    it("does not announce a second time when the store then reports the lock", async () => {
      edit();
      await settle();
      harness.pending[0].resolve({ outcome: "locked" });
      await settle();
      expect(announced()).toBe("UTub is locked");

      el("PanelSettingsAnnouncement").textContent = "";
      setState({ isCurrentUTubLocked: true });
      expect(announced()).toBe("");
    });

    it("re-renders on resynced even with focus inside, unless the section has work", async () => {
      el("sort-input").focus();
      edit();
      await settle();
      harness.pending[0].resolve({ outcome: "error" });
      await settle();

      // resync ran inside the error path: rendered again (initial, rollback, resync).
      expect(harness.section.render).toHaveBeenCalledTimes(3);
      expect(document.activeElement).toBe(el("sort-input"));
    });

    it("ignores a late outcome from another UTub's save on a newly opened popover", async () => {
      edit();
      await settle();

      // Switching UTubs force-closes (the save for the old UTub stays in flight).
      selectUTub({ utubID: OTHER_UTUB_ID });
      openGear("urls");
      expect(isOpen()).toBe(true);
      const rendersBefore = vi.mocked(harness.section.render).mock.calls.length;

      harness.pending[0].resolve({ outcome: "locked" });
      await settle();

      expect(lastCtx(harness).canWrite).toBe(true);
      expect(
        (wrapper().querySelector(".panelSettingsReadOnlyNote") as HTMLElement)
          .hidden,
      ).toBe(true);
      expect(harness.section.render).toHaveBeenCalledTimes(rendersBefore);
      expect(wrapper().hasAttribute("aria-busy")).toBe(false);
    });

    it("does not show another UTub's late failure as a rollback on the new popover", async () => {
      edit();
      await settle();
      selectUTub({ utubID: OTHER_UTUB_ID });
      openGear("urls");

      harness.pending[0].resolve({ outcome: "error", resync: false });
      await settle();

      expect(status().dataset.state).toBeUndefined();
      expect(announced()).toBe("Sort: Couldn't save");
    });

    it("clears only the stale section's saving state when titles are equal", async () => {
      const otherCtxs: SectionContext[] = [];
      const other = registerControlled({
        id: "other",
        title: "Sort",
        scope: "user",
        userKind: "global",
        render: vi.fn(({ container, ctx }) => {
          otherCtxs.push(ctx);
          container.textContent = "other";
        }),
      });
      edit();
      otherCtxs[otherCtxs.length - 1].submit({ patch: { x: 1 } });
      await settle();
      const otherWrapper = popover().querySelector(
        '[data-section-id="other"]',
      ) as HTMLElement;
      expect(wrapper().getAttribute("aria-busy")).toBe("true");
      expect(otherWrapper.getAttribute("aria-busy")).toBe("true");

      harness.pending[0].resolve({ outcome: "stale", failed: true });
      await vi.advanceTimersByTimeAsync(0);

      expect(wrapper().hasAttribute("aria-busy")).toBe(false);
      expect(otherWrapper.getAttribute("aria-busy")).toBe("true");
      other.pending[0].resolve({ outcome: "ok" });
      await settle();
    });

    it("skips the resync re-render while a newer edit is waiting", async () => {
      let finishResync!: (resynced: boolean) => void;
      vi.mocked(resyncSettings).mockImplementationOnce(
        () =>
          new Promise<boolean>((resolve) => {
            finishResync = resolve;
          }),
      );
      edit();
      await settle();
      harness.pending[0].resolve({ outcome: "error" });
      await settle();

      // The user edits again while the resync is still in flight.
      edit({ sort: "second" });
      finishResync(true);
      await settle();

      // initial + rollback only: the waiting edit blocks the resync render.
      expect(harness.section.render).toHaveBeenCalledTimes(2);
    });
  });

  describe("with no popover attached", () => {
    it("announces a late save failure and renders nothing", async () => {
      initPopover();
      const harness = registerControlled();
      selectUTub();
      openGear("urls");
      lastCtx(harness).submit({ patch: { sort: "new" } });
      await settle();

      openGear("urls");
      const rendersBefore = vi.mocked(harness.section.render).mock.calls.length;
      harness.pending[0].resolve({ outcome: "error", resync: false });
      await settle();

      expect(announced()).toBe("Sort: Couldn't save");
      expect(harness.section.render).toHaveBeenCalledTimes(rendersBefore);
      expect(popover().childElementCount).toBe(0);
    });

    it("announces a late save with a notice once, with title, Saved and notice", async () => {
      initPopover();
      const harness = registerControlled();
      selectUTub();
      openGear("urls");
      lastCtx(harness).submit({ patch: { sort: "new" } });
      await settle();

      openGear("urls");
      vi.mocked(announceSettingsStatus).mockClear();
      harness.pending[0].resolve({ outcome: "ok", notice: "Reset to https." });
      await settle();

      expect(announceSettingsStatus).toHaveBeenCalledTimes(1);
      expect(announced()).toBe("Sort: Saved. Reset to https.");
      expect(popover().childElementCount).toBe(0);
    });

    it("stays silent for a late plain save", async () => {
      initPopover();
      const harness = registerControlled();
      selectUTub();
      openGear("urls");
      lastCtx(harness).submit({ patch: { sort: "new" } });
      await settle();

      openGear("urls");
      vi.mocked(announceSettingsStatus).mockClear();
      harness.pending[0].resolve({ outcome: "ok" });
      await settle();

      expect(announceSettingsStatus).not.toHaveBeenCalled();
    });

    it("treats forced read-only as a no-op", async () => {
      initPopover();
      const harness = registerControlled();
      selectUTub();
      openGear("urls");
      lastCtx(harness).submit({ patch: { sort: "new" } });
      await settle();
      openGear("urls");

      harness.pending[0].resolve({ outcome: "locked" });
      await settle();
      expect(popover().childElementCount).toBe(0);
    });
  });

  describe("settings slice changes while open", () => {
    let harness: Harness;

    beforeEach(() => {
      initPopover();
      harness = registerControlled();
      selectUTub();
      openGear("urls");
    });

    function externalWrite(sort: string): void {
      setState({
        settings: {
          ...SETTINGS,
          urls: { sort },
        } as unknown as ResolvedUtubSettings,
      });
    }

    it("re-renders when the slice differs and the section is idle and unfocused", () => {
      (document.activeElement as HTMLElement).blur();
      externalWrite("changed");
      expect(harness.section.render).toHaveBeenCalledTimes(2);
    });

    it("does not re-render when the value is deep-equal", () => {
      (document.activeElement as HTMLElement).blur();
      externalWrite("old");
      expect(harness.section.render).toHaveBeenCalledTimes(1);
    });

    it("does not re-render with focus inside the section", () => {
      el("sort-input").focus();
      externalWrite("changed");
      expect(harness.section.render).toHaveBeenCalledTimes(1);
    });

    it("does not re-render while the section has queued work", () => {
      (document.activeElement as HTMLElement).blur();
      lastCtx(harness).submit({ patch: { sort: "pending" }, debounce: true });
      externalWrite("changed");
      expect(harness.section.render).toHaveBeenCalledTimes(1);
    });

    it("ignores the shell's own settingsVersion-bumping writes", () => {
      (document.activeElement as HTMLElement).blur();
      setState({
        settings: {
          ...SETTINGS,
          urls: { sort: "mine" },
        } as unknown as ResolvedUtubSettings,
        settingsVersion: 1,
      });
      expect(harness.section.render).toHaveBeenCalledTimes(1);
    });
  });

  describe("normalized-value check after a save", () => {
    let harness: Harness;

    beforeEach(() => {
      initPopover();
      harness = registerControlled();
      selectUTub();
      openGear("urls");
      (document.activeElement as HTMLElement).blur();
    });

    async function saveAndStore({
      stored,
    }: {
      stored: Record<string, unknown>;
    }): Promise<void> {
      lastCtx(harness).submit({ patch: { sort: "typed" } });
      await settle();
      setState({
        settings: { ...SETTINGS, urls: stored } as ResolvedUtubSettings,
        settingsVersion: 1,
      });
      harness.pending[0].resolve({ outcome: "ok" });
      await vi.advanceTimersByTimeAsync(1500);
    }

    it("adopts the value when the server stored exactly what was sent", async () => {
      await saveAndStore({ stored: { sort: "typed" } });
      expect(harness.section.render).toHaveBeenCalledTimes(1);
    });

    it("re-renders when the server normalized the value differently", async () => {
      await saveAndStore({ stored: { sort: "TYPED" } });
      expect(harness.section.render).toHaveBeenCalledTimes(2);
    });

    it("skips the re-render while focus is inside the section", async () => {
      el("sort-input").focus();
      await saveAndStore({ stored: { sort: "TYPED" } });
      expect(harness.section.render).toHaveBeenCalledTimes(1);
    });

    it("skips the re-render while an edit is waiting, and still adopts the stored value", async () => {
      lastCtx(harness).submit({ patch: { sort: "typed" } });
      await settle();
      lastCtx(harness).submit({ patch: { size: 5 } });
      setState({
        settings: {
          ...SETTINGS,
          urls: { sort: "TYPED" },
        } as unknown as ResolvedUtubSettings,
        settingsVersion: 1,
      });
      harness.pending[0].resolve({ outcome: "ok" });
      await settle();

      expect(harness.section.render).toHaveBeenCalledTimes(1);
      // The waiting edit goes out right after the first save settled.
      expect(harness.section.save).toHaveBeenCalledTimes(2);
    });

    it("compares a later external write against the adopted value", async () => {
      el("sort-input").focus();
      await saveAndStore({ stored: { sort: "TYPED" } });
      (document.activeElement as HTMLElement).blur();

      // Equal to the adopted value: nothing to re-render.
      setState({
        settings: {
          ...SETTINGS,
          urls: { sort: "TYPED" },
        } as unknown as ResolvedUtubSettings,
      });
      expect(harness.section.render).toHaveBeenCalledTimes(1);

      setState({
        settings: {
          ...SETTINGS,
          urls: { sort: "other" },
        } as unknown as ResolvedUtubSettings,
      });
      expect(harness.section.render).toHaveBeenCalledTimes(2);
    });

    it("keeps the baseline current across coalesced back-to-back saves", async () => {
      lastCtx(harness).submit({ patch: { size: 1 } });
      await settle();
      lastCtx(harness).submit({ patch: { sort: "next" } });
      setState({
        settings: {
          ...SETTINGS,
          urls: { sort: "old", size: 1 },
        } as unknown as ResolvedUtubSettings,
        settingsVersion: 1,
      });
      harness.pending[0].resolve({ outcome: "ok" });
      await settle();

      setState({
        settings: {
          ...SETTINGS,
          urls: { sort: "next", size: 1 },
        } as unknown as ResolvedUtubSettings,
        settingsVersion: 2,
      });
      harness.pending[1].resolve({ outcome: "ok" });
      await settle();

      expect(harness.section.render).toHaveBeenCalledTimes(1);
    });
  });

  describe("precedence", () => {
    let harness: Harness;

    beforeEach(() => {
      initPopover();
      harness = registerControlled();
      selectUTub();
      openGear("urls");
    });

    it("a removeUTubLocally-shaped setState closes once and drops pending saves before the close flush", async () => {
      lastCtx(harness).submit({ patch: { sort: "new" }, debounce: true });

      setState({
        utubs: summaries([OTHER_UTUB_ID]),
        activeUTubID: null,
        isCurrentUTubLocked: true,
      });
      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS * 2);

      expect(harness.section.save).not.toHaveBeenCalled();
      expect(isOpen()).toBe(false);
      // Closed once, and step 4 (lock announcement / re-render) never ran.
      expect(announceSettingsStatus).toHaveBeenCalledTimes(1);
      expect(announceSettingsStatus).toHaveBeenCalledWith({
        message: "Settings closed",
      });
      expect(harness.section.render).toHaveBeenCalledTimes(1);
    });

    it("an openTrash-shaped setState still flushes the pending edit", async () => {
      lastCtx(harness).submit({ patch: { sort: "new" }, debounce: true });

      setState({ activeUTubID: null });
      await settle();

      expect(isOpen()).toBe(false);
      expect(harness.section.save).toHaveBeenCalledTimes(1);
      expect(harness.section.save).toHaveBeenCalledWith({
        utubID: UTUB_ID,
        patch: { sort: "new" },
      });
    });

    it("UTUB_DELETED is a backstop that drops the UTub's pending saves", async () => {
      lastCtx(harness).submit({ patch: { sort: "new" }, debounce: true });
      emit(AppEvents.UTUB_DELETED, { utubID: UTUB_ID });
      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS * 2);
      expect(harness.section.save).not.toHaveBeenCalled();
    });

    it("switching UTubs keeps the pending save going to its captured UTub", async () => {
      lastCtx(harness).submit({ patch: { sort: "new" }, debounce: true });
      selectUTub({ utubID: OTHER_UTUB_ID });
      await settle();
      expect(harness.section.save).toHaveBeenCalledWith({
        utubID: UTUB_ID,
        patch: { sort: "new" },
      });
    });
  });

  describe("flush", () => {
    let harness: Harness;

    beforeEach(() => {
      initPopover();
      harness = registerControlled();
      selectUTub();
      openGear("urls");
    });

    it("flushes a debounced edit when focus leaves the section", async () => {
      el("sort-input").focus();
      lastCtx(harness).submit({ patch: { sort: "new" }, debounce: true });
      expect(harness.section.save).not.toHaveBeenCalled();

      el("sort-input").dispatchEvent(
        new FocusEvent("focusout", { bubbles: true }),
      );
      await settle();
      expect(harness.section.save).toHaveBeenCalledTimes(1);
    });

    it("flushes on every popover close", async () => {
      lastCtx(harness).submit({ patch: { sort: "new" }, debounce: true });
      openGear("urls");
      await settle();
      expect(harness.section.save).toHaveBeenCalledTimes(1);
    });

    it("keeps the busy signal up until the flushed save settles", async () => {
      lastCtx(harness).submit({ patch: { sort: "new" }, debounce: true });
      openGear("urls");
      vi.advanceTimersByTime(0);
      await settle();
      expect(isPanelSettingsBusy()).toBe(true);

      harness.pending[0].resolve({ outcome: "ok" });
      await settle();
      expect(isPanelSettingsBusy()).toBe(false);
    });
  });

  describe("section lifecycle", () => {
    it("drops the DOM of an unregistered section but lets its pending save finish", async () => {
      initPopover();
      const kept = registerControlled({ id: "kept", title: "Kept" });
      const gone = registerControlled({ id: "gone", title: "Gone" });
      selectUTub();
      openGear("urls");
      lastCtx(gone).submit({ patch: { sort: "new" } });
      await settle();

      gone.unregister();
      expect(popover().querySelector('[data-section-id="gone"]')).toBeNull();
      expect(
        popover().querySelector('[data-section-id="kept"]'),
      ).not.toBeNull();
      expect(gone.cleanup).toHaveBeenCalled();
      expect(isOpen()).toBe(true);

      gone.pending[0].resolve({ outcome: "error", resync: false });
      await settle();
      expect(announced()).toBe("Gone: Couldn't save");
      expect(kept.section.save).not.toHaveBeenCalled();
    });

    it("renders a section registered while open without closing", () => {
      initPopover();
      registerControlled({ id: "first", title: "First" });
      selectUTub();
      openGear("urls");

      registerControlled({ id: "second", title: "Second" });
      expect(
        popover().querySelector('[data-section-id="second"]'),
      ).not.toBeNull();
      expect(isOpen()).toBe(true);
    });

    it("keeps focus, typed text and DOM of existing sections when the registry changes", () => {
      initPopover();
      const first = registerControlled({
        id: "first",
        title: "First",
        render: vi.fn(({ container }) => {
          container.innerHTML = '<input id="first-input" />';
        }),
      });
      selectUTub();
      openGear("urls");
      const input = el("first-input") as HTMLInputElement;
      input.focus();
      input.value = "typed";

      registerControlled({ id: "second", title: "Second" });

      expect(el("first-input")).toBe(input);
      expect(input.value).toBe("typed");
      expect(document.activeElement).toBe(input);
      expect(first.section.render).toHaveBeenCalledTimes(1);
    });

    it("binds no scroll listener anywhere", () => {
      const windowSpy = vi.spyOn(window, "addEventListener");
      const documentSpy = vi.spyOn(document, "addEventListener");
      const jqueryOnSpy = vi.spyOn($.fn, "on");

      initPopover();
      registerControlled();
      selectUTub();
      openGear("urls");

      const events = [
        ...windowSpy.mock.calls.map(([type]) => String(type)),
        ...documentSpy.mock.calls.map(([type]) => String(type)),
        ...jqueryOnSpy.mock.calls.map(([type]) => String(type)),
      ];
      windowSpy.mockRestore();
      documentSpy.mockRestore();
      jqueryOnSpy.mockRestore();

      expect(events.length).toBeGreaterThan(0);
      expect(events.some((type) => type.includes("scroll"))).toBe(false);
    });

    it("re-initialising tears the previous wiring down", () => {
      initPopover();
      registerControlled();
      selectUTub();
      initPopover();
      openGear("urls");
      openGear("urls");
      expect(isOpen()).toBe(false);
    });
  });
});
