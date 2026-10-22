import type { Mock } from "vitest";
import {
  IDLE_REARM_MS,
  initUTubSelectionIndicator,
  syncUTubSelectionIndicator,
  resetUTubSelectionIndicatorForTests,
} from "../selection-indicator.js";
import { AppEvents, emit } from "../../../lib/event-bus.js";

const ROW_HEIGHT = 40;
const LABEL = "selected";

type FrameCallback = (time: number) => void;
let frameQueue: Map<number, FrameCallback>;
let nextFrameId: number;

function flushFrames(): void {
  const callbacks = Array.from(frameQueue.values());
  frameQueue.clear();
  for (const callback of callbacks) callback(0);
}

// MutationObserver callbacks are microtasks; await one, then run the rAF.
async function flushObserverAndFrame(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
  flushFrames();
}

function stubGeometry({
  row,
  top,
  rendered = true,
  height = ROW_HEIGHT,
}: {
  row: HTMLElement;
  top: number;
  rendered?: boolean;
  height?: number;
}): void {
  Object.defineProperty(row, "offsetTop", { value: top, configurable: true });
  Object.defineProperty(row, "offsetHeight", {
    value: rendered ? height : 0,
    configurable: true,
  });
  Object.defineProperty(row, "offsetParent", {
    value: rendered ? document.body : null,
    configurable: true,
  });
}

function makeRow({
  utubid,
  index,
  rendered = true,
}: {
  utubid: number;
  index: number;
  rendered?: boolean;
}): HTMLElement {
  const row = document.createElement("span");
  row.className = "UTubSelector";
  row.setAttribute("utubid", String(utubid));
  row.innerHTML = `<b class="UTubName">UTub ${utubid}</b>`;
  stubGeometry({ row, top: index * ROW_HEIGHT, rendered });
  return row;
}

function getList(): HTMLElement {
  return document.getElementById("listUTubs") as HTMLElement;
}

function getRows(): HTMLElement[] {
  return Array.from(getList().querySelectorAll<HTMLElement>(".UTubSelector"));
}

function getIndicator(): HTMLElement {
  return document.getElementById("UTubSelectionIndicator") as HTMLElement;
}

function getBar(): HTMLElement {
  return getIndicator().querySelector(".utubSelectionBar") as HTMLElement;
}

function getClip(): HTMLElement {
  return getIndicator().querySelector(
    ".utubSelectionShimmerClip",
  ) as HTMLElement;
}

function buildFixture(): void {
  document.body.innerHTML = `
    <div id="UTubDeck"><div id="UTubDeckContent">
      <div id="UTubSelectionIndicator" class="utubSelectionIndicator"
           aria-hidden="true" data-selected-label="${LABEL}">
        <div class="utubSelectionBar"></div>
        <div class="utubSelectionShimmerClip"><div class="utubSelectionShimmer"></div></div>
      </div>
      <p id="UTubSearchNoResults" class="hidden"></p>
      <div id="listUTubs"></div>
    </div></div>
    <div id="mainPanel"></div>
    <div id="bulkPicker"><span class="UTubSelector active" utubid="99"></span></div>`;
  getList().append(
    makeRow({ utubid: 1, index: 0 }),
    makeRow({ utubid: 2, index: 1 }),
    makeRow({ utubid: 3, index: 2 }),
  );
}

function announceNodes(): HTMLElement[] {
  return Array.from(
    getList().querySelectorAll<HTMLElement>(".utubSelectedAnnounce"),
  );
}

type FakeAnimation = {
  cancel: ReturnType<typeof vi.fn>;
  finished: Promise<void>;
  resolve: () => void;
  keyframes: Keyframe[];
  options: KeyframeAnimationOptions;
};
let animations: FakeAnimation[];
let reducedMotion: boolean;

function installAnimateStub(): void {
  Object.defineProperty(Element.prototype, "animate", {
    configurable: true,
    writable: true,
    value: vi.fn((keyframes: Keyframe[], options: KeyframeAnimationOptions) => {
      let resolve = (): void => undefined;
      let reject: (reason: unknown) => void = () => undefined;
      const finished = new Promise<void>((res, rej) => {
        resolve = res;
        reject = rej;
      });
      const fake: FakeAnimation = {
        cancel: vi.fn(() => reject(new DOMException("", "AbortError"))),
        finished,
        resolve,
        keyframes,
        options,
      };
      animations.push(fake);
      return fake;
    }),
  });
}

function animateCalls(): number {
  return animations.length;
}

// Computed transform of the bar while a stretch runs (matrix form).
function stubComputedBar({
  top,
  scaleY,
}: {
  top: number;
  scaleY: number;
}): void {
  vi.spyOn(window, "getComputedStyle").mockReturnValue({
    transform: `matrix(1, 0, 0, ${scaleY}, 0, ${top})`,
  } as CSSStyleDeclaration);
}

async function selectRow(row: HTMLElement | undefined): Promise<void> {
  for (const other of getRows()) other.classList.remove("active");
  row?.classList.add("active");
  await flushObserverAndFrame();
}

describe("selection-indicator", () => {
  beforeEach(() => {
    animations = [];
    reducedMotion = false;
    installAnimateStub();
    vi.stubGlobal("matchMedia", () => ({ matches: reducedMotion }));
    frameQueue = new Map();
    nextFrameId = 1;
    vi.stubGlobal("requestAnimationFrame", (callback: FrameCallback) => {
      const id = nextFrameId++;
      frameQueue.set(id, callback);
      return id;
    });
    vi.stubGlobal("cancelAnimationFrame", (id: number) => {
      frameQueue.delete(id);
    });
    buildFixture();
  });

  afterEach(() => {
    resetUTubSelectionIndicatorForTests();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    Reflect.deleteProperty(Element.prototype, "animate");
    Reflect.deleteProperty(document, "hidden");
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  async function initAndSettle(): Promise<void> {
    initUTubSelectionIndicator();
    await flushObserverAndFrame();
  }

  it("has no isVisible class with no active row", async () => {
    await initAndSettle();
    expect(getIndicator().classList.contains("isVisible")).toBe(false);
  });

  it("places the bar and clip on a newly active row", async () => {
    await initAndSettle();
    getRows()[1].classList.add("active");
    await flushObserverAndFrame();

    expect(getIndicator().classList.contains("isVisible")).toBe(true);
    expect(getBar().style.height).toBe(`${ROW_HEIGHT}px`);
    expect(getBar().style.transform).toBe(
      `translateY(${ROW_HEIGHT}px) scaleY(1)`,
    );
    expect(getClip().style.height).toBe(`${ROW_HEIGHT}px`);
    expect(getClip().style.transform).toBe(`translateY(${ROW_HEIGHT}px)`);
  });

  it("follows .active moving from row A to row B through a class change", async () => {
    await initAndSettle();
    const [rowA, rowB] = getRows();
    rowA.classList.add("active");
    await flushObserverAndFrame();
    expect(getBar().style.transform).toBe("translateY(0px) scaleY(1)");

    rowA.classList.remove("active");
    rowB.classList.add("active");
    await flushObserverAndFrame();
    expect(getBar().style.transform).toBe(
      `translateY(${ROW_HEIGHT}px) scaleY(1)`,
    );
    expect(rowA.hasAttribute("aria-current")).toBe(false);
    expect(rowB.getAttribute("aria-current")).toBe("true");
  });

  it("survives the list being emptied and rebuilt", async () => {
    await initAndSettle();
    getRows()[0].classList.add("active");
    await flushObserverAndFrame();

    getList().replaceChildren();
    await flushObserverAndFrame();
    expect(getIndicator().classList.contains("isVisible")).toBe(false);

    const rebuilt = [
      makeRow({ utubid: 1, index: 0 }),
      makeRow({ utubid: 2, index: 1 }),
    ];
    rebuilt[1].classList.add("active");
    getList().append(...rebuilt);
    await flushObserverAndFrame();

    expect(document.body.contains(getIndicator())).toBe(true);
    expect(getIndicator().classList.contains("isVisible")).toBe(true);
    expect(getBar().style.transform).toBe(
      `translateY(${ROW_HEIGHT}px) scaleY(1)`,
    );
    expect(getRows()[1].getAttribute("aria-current")).toBe("true");
  });

  it("hides and resets when the active row is not rendered", async () => {
    await initAndSettle();
    const row = getRows()[2];
    row.classList.add("active");
    await flushObserverAndFrame();
    expect(getIndicator().classList.contains("isVisible")).toBe(true);
    expect(getBar().style.height).toBe(`${ROW_HEIGHT}px`);

    stubGeometry({ row, top: 2 * ROW_HEIGHT, rendered: false });
    row.classList.add("hidden");
    await flushObserverAndFrame();

    expect(getIndicator().classList.contains("isVisible")).toBe(false);
    expect(getBar().style.transform).toBe("translateY(0)");
    expect(getClip().style.transform).toBe("translateY(0)");
    expect(getBar().style.height).toBe("");
    expect(getClip().style.height).toBe("");
    expect(announceNodes()).toHaveLength(0);
    expect(row.getAttribute("aria-current")).toBe("true");
  });

  it("snaps (no stale state) on the next placement after a hide", async () => {
    await initAndSettle();
    const rows = getRows();
    rows[0].classList.add("active");
    await flushObserverAndFrame();
    rows[0].classList.remove("active");
    await flushObserverAndFrame();
    expect(getIndicator().classList.contains("isVisible")).toBe(false);

    rows[2].classList.add("active");
    await flushObserverAndFrame();
    expect(getBar().style.transform).toBe(
      `translateY(${2 * ROW_HEIGHT}px) scaleY(1)`,
    );
    expect(animateCalls()).toBe(0);
  });

  it("keeps aria-current on only the active row, none when nothing is active", async () => {
    await initAndSettle();
    const rows = getRows();
    rows[0].classList.add("active");
    await flushObserverAndFrame();
    expect(rows.map((row) => row.getAttribute("aria-current"))).toEqual([
      "true",
      null,
      null,
    ]);

    rows[0].classList.remove("active");
    await flushObserverAndFrame();
    expect(rows.every((row) => !row.hasAttribute("aria-current"))).toBe(true);
  });

  it("keeps exactly one hidden 'selected' node inside the active row and moves it", async () => {
    await initAndSettle();
    const rows = getRows();
    rows[0].classList.add("active");
    await flushObserverAndFrame();
    expect(announceNodes()).toHaveLength(1);
    expect(announceNodes()[0].parentElement).toBe(rows[0]);
    expect(announceNodes()[0].textContent).toBe(LABEL);
    expect(announceNodes()[0].classList.contains("visually-hidden")).toBe(true);
    expect(rows[0].querySelector(".UTubName")?.textContent).toBe("UTub 1");

    rows[0].classList.remove("active");
    rows[1].classList.add("active");
    await flushObserverAndFrame();
    expect(announceNodes()).toHaveLength(1);
    expect(announceNodes()[0].parentElement).toBe(rows[1]);

    rows[1].classList.remove("active");
    await flushObserverAndFrame();
    expect(announceNodes()).toHaveLength(0);
  });

  it("reaches a fixed point: the node's own insertion triggers no further changes", async () => {
    await initAndSettle();
    getRows()[0].classList.add("active");
    await flushObserverAndFrame();
    const node = announceNodes()[0];

    await flushObserverAndFrame();
    await flushObserverAndFrame();
    expect(announceNodes()).toHaveLength(1);
    expect(announceNodes()[0]).toBe(node);
    expect(frameQueue.size).toBe(0);
  });

  it("ignores .UTubSelector.active outside #listUTubs", async () => {
    await initAndSettle();
    const outside = document.querySelector("#bulkPicker .UTubSelector");
    outside?.classList.remove("active");
    outside?.classList.add("active");
    await flushObserverAndFrame();
    expect(getIndicator().classList.contains("isVisible")).toBe(false);
    expect(outside?.hasAttribute("aria-current")).toBe(false);
  });

  it("coalesces several requests in one frame into one sync", async () => {
    await initAndSettle();
    getRows()[0].classList.add("active");
    syncUTubSelectionIndicator({ animate: false });
    syncUTubSelectionIndicator({ animate: true });
    await Promise.resolve();
    await Promise.resolve();
    expect(frameQueue.size).toBe(1);
    flushFrames();
    expect(frameQueue.size).toBe(0);
    expect(getIndicator().classList.contains("isVisible")).toBe(true);
  });

  describe("stretch", () => {
    async function startOn(index: number): Promise<void> {
      await initAndSettle();
      await selectRow(getRows()[index]);
    }

    it("never animates the first placement", async () => {
      await startOn(0);
      expect(animateCalls()).toBe(0);
      expect(getBar().style.transform).toBe("translateY(0px) scaleY(1)");
    });

    it("stretches to a different UTub with three keyframes and the contract options", async () => {
      await startOn(0);
      await selectRow(getRows()[2]);

      expect(animateCalls()).toBe(1);
      const { keyframes, options } = animations[0];
      expect(keyframes).toEqual([
        { transform: "translateY(0px) scaleY(1)" },
        { transform: "translateY(0px) scaleY(3)", offset: 0.45 },
        { transform: `translateY(${2 * ROW_HEIGHT}px) scaleY(1)` },
      ]);
      expect(options).toEqual({
        duration: 420,
        easing: "cubic-bezier(.5, 0, .2, 1)",
      });
      expect(getBar().style.transform).toBe(
        `translateY(${2 * ROW_HEIGHT}px) scaleY(1)`,
      );
      expect(getClip().style.transform).toBe(`translateY(${2 * ROW_HEIGHT}px)`);
    });

    it("uses the union box (min top, spanning both rows) when moving upward", async () => {
      await startOn(2);
      await selectRow(getRows()[0]);

      expect(animations[0].keyframes[1]).toEqual({
        transform: "translateY(0px) scaleY(3)",
        offset: 0.45,
      });
    });

    it("never animates the first placement after a hide", async () => {
      await startOn(0);
      await selectRow(undefined);
      expect(getIndicator().classList.contains("isVisible")).toBe(false);
      await selectRow(getRows()[2]);
      expect(animateCalls()).toBe(0);
    });

    it("snaps without animate() under reduced motion", async () => {
      reducedMotion = true;
      await startOn(0);
      await selectRow(getRows()[2]);

      expect(animateCalls()).toBe(0);
      expect(getBar().style.transform).toBe(
        `translateY(${2 * ROW_HEIGHT}px) scaleY(1)`,
      );
    });

    it("snaps (no stretch) on animate:false with a different UTub and cancels a running stretch", async () => {
      await startOn(0);
      await selectRow(getRows()[1]);
      expect(animateCalls()).toBe(1);
      // Drain the aria-node insertion's follow-up sync (animate:true).
      await flushObserverAndFrame();

      for (const row of getRows()) row.classList.remove("active");
      getRows()[2].classList.add("active");
      // Run the frame before the MutationObserver microtask, so only the
      // animate:false request is in it.
      syncUTubSelectionIndicator({ animate: false });
      flushFrames();
      await flushObserverAndFrame();

      expect(animateCalls()).toBe(1);
      expect(animations[0].cancel).toHaveBeenCalledTimes(1);
      expect(getBar().style.transform).toBe(
        `translateY(${2 * ROW_HEIGHT}px) scaleY(1)`,
      );
    });

    it("starts a stretch when animate:true and animate:false coalesce, in either order", async () => {
      await startOn(0);
      const rows = getRows();
      rows[0].classList.remove("active");
      rows[1].classList.add("active");
      syncUTubSelectionIndicator({ animate: false });
      await flushObserverAndFrame();
      expect(animateCalls()).toBe(1);

      rows[1].classList.remove("active");
      syncUTubSelectionIndicator({ animate: false });
      rows[2].classList.add("active");
      await flushObserverAndFrame();
      expect(animateCalls()).toBe(2);
    });

    it("starts a stretch when animate:true is requested before animate:false in one frame", async () => {
      await startOn(0);
      const rows = getRows();
      syncUTubSelectionIndicator({ animate: true });
      rows[0].classList.remove("active");
      rows[1].classList.add("active");
      syncUTubSelectionIndicator({ animate: false });
      await flushObserverAndFrame();
      expect(animateCalls()).toBe(1);
    });

    it("is a no-op for coalesced true and false requests on an unchanged target", async () => {
      await startOn(0);
      await flushObserverAndFrame();
      syncUTubSelectionIndicator({ animate: true });
      syncUTubSelectionIndicator({ animate: false });
      flushFrames();
      expect(animateCalls()).toBe(0);
      expect(getBar().style.transform).toBe("translateY(0px) scaleY(1)");
    });

    it("treats a re-sync with an unchanged target as a no-op during a stretch", async () => {
      await startOn(0);
      await selectRow(getRows()[2]);
      expect(animateCalls()).toBe(1);

      syncUTubSelectionIndicator({ animate: false });
      flushFrames();
      syncUTubSelectionIndicator({ animate: true });
      flushFrames();

      expect(animateCalls()).toBe(1);
      expect(animations[0].cancel).not.toHaveBeenCalled();
    });

    it("never stretches for the same UTub with changed geometry: cancels and snaps", async () => {
      await startOn(0);
      await selectRow(getRows()[1]);
      expect(animateCalls()).toBe(1);

      stubGeometry({ row: getRows()[1], top: 5 * ROW_HEIGHT });
      syncUTubSelectionIndicator({ animate: true });
      flushFrames();

      expect(animateCalls()).toBe(1);
      expect(animations[0].cancel).toHaveBeenCalledTimes(1);
      expect(getBar().style.transform).toBe(
        `translateY(${5 * ROW_HEIGHT}px) scaleY(1)`,
      );
    });

    it("never stretches when the row elements of the same UTub are replaced", async () => {
      await startOn(1);
      getList().replaceChildren(
        makeRow({ utubid: 1, index: 0 }),
        makeRow({ utubid: 2, index: 1 }),
        makeRow({ utubid: 3, index: 2 }),
      );
      getRows()[1].classList.add("active");
      await flushObserverAndFrame();

      expect(animateCalls()).toBe(0);
      expect(getIndicator().classList.contains("isVisible")).toBe(true);
    });

    it("restarts an interrupted stretch from the bar's computed box", async () => {
      await startOn(0);
      await selectRow(getRows()[2]);
      expect(animateCalls()).toBe(1);

      stubComputedBar({ top: 20, scaleY: 2 });
      await selectRow(getRows()[1]);

      expect(animations[0].cancel).toHaveBeenCalledTimes(1);
      expect(animateCalls()).toBe(2);
      expect(animations[1].keyframes[0]).toEqual({
        transform: "translateY(20px) scaleY(2)",
      });
    });

    it("uses the rendered height of the interrupted bar when the new row's height differs", async () => {
      await startOn(0);
      await selectRow(getRows()[2]);
      stubGeometry({ row: getRows()[1], top: ROW_HEIGHT, height: 60 });

      stubComputedBar({ top: 20, scaleY: 2 });
      await selectRow(getRows()[1]);

      // Rendered height is scaleY(2) * inline 40px = 80px, relative to new 60px.
      expect(animations[1].keyframes[0]).toEqual({
        transform: `translateY(20px) scaleY(${80 / 60})`,
      });
      expect(animations[1].keyframes[2]).toEqual({
        transform: `translateY(${ROW_HEIGHT}px) scaleY(1)`,
      });
    });

    it("measures the previous row fresh when it is still rendered", async () => {
      await startOn(0);
      stubGeometry({ row: getRows()[0], top: 3 * ROW_HEIGHT });
      await selectRow(getRows()[2]);

      expect(animations[0].keyframes[0]).toEqual({
        transform: `translateY(${3 * ROW_HEIGHT}px) scaleY(1)`,
      });
    });

    it("falls back to lastPlaced when the previous row is gone", async () => {
      await startOn(0);
      const target = getRows()[1];
      getRows()[0].remove();
      await selectRow(target);

      expect(animateCalls()).toBe(1);
      expect(animations[0].keyframes[0]).toEqual({
        transform: "translateY(0px) scaleY(1)",
      });
    });

    it("ignores the AbortError rejection of a cancelled stretch", async () => {
      await startOn(0);
      await selectRow(getRows()[1]);
      await selectRow(getRows()[2]);
      await selectRow(undefined);
      await Promise.resolve();
      await Promise.resolve();

      expect(animateCalls()).toBe(2);
      expect(animations[1].cancel).toHaveBeenCalledTimes(1);
    });

    it("starts from a fresh row measure once the previous stretch finished", async () => {
      await startOn(0);
      await selectRow(getRows()[2]);
      animations[0].resolve();
      await Promise.resolve();
      await Promise.resolve();

      // A finished stretch is no longer "running": the stale computed box is ignored.
      stubComputedBar({ top: 999, scaleY: 9 });
      await selectRow(getRows()[1]);

      expect(animations[1].keyframes[0]).toEqual({
        transform: `translateY(${2 * ROW_HEIGHT}px) scaleY(1)`,
      });
      expect(animations[0].cancel).not.toHaveBeenCalled();
    });

    it("cancels a running stretch on teardown", async () => {
      await startOn(0);
      await selectRow(getRows()[1]);
      resetUTubSelectionIndicatorForTests();
      expect(animations[0].cancel).toHaveBeenCalledTimes(1);
    });

    it("does not schedule a frame before init", () => {
      syncUTubSelectionIndicator({ animate: true });
      expect(frameQueue.size).toBe(0);
    });
  });

  describe("idle shimmer", () => {
    const isIdle = (): boolean => getIndicator().classList.contains("isIdle");

    async function flushMicrotasks(): Promise<void> {
      await Promise.resolve();
      await Promise.resolve();
    }

    function setHidden(hidden: boolean): void {
      Object.defineProperty(document, "hidden", {
        configurable: true,
        get: () => hidden,
      });
      document.dispatchEvent(new Event("visibilitychange"));
    }

    async function startSelected(index = 0): Promise<void> {
      vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
      await initAndSettle();
      await selectRow(getRows()[index]);
    }

    function expandDeck(): void {
      emit(AppEvents.DECK_COLLAPSE_CHANGED, {
        deck: "utubs",
        collapsed: false,
      });
    }

    function collapseDeck(): void {
      emit(AppEvents.DECK_COLLAPSE_CHANGED, { deck: "utubs", collapsed: true });
    }

    it("is idle right after the first snap and not before anything is selected", async () => {
      vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
      await initAndSettle();
      expect(isIdle()).toBe(false);
      await selectRow(getRows()[0]);
      expect(isIdle()).toBe(true);
    });

    it("drops isIdle while a stretch runs and re-adds it when that stretch finishes", async () => {
      await startSelected(0);
      await selectRow(getRows()[2]);
      expect(animateCalls()).toBe(1);
      expect(isIdle()).toBe(false);

      animations[0].resolve();
      await flushMicrotasks();
      expect(isIdle()).toBe(true);
    });

    it("only the latest stretch's completion counts; a cancelled one adds nothing", async () => {
      await startSelected(0);
      await selectRow(getRows()[1]);
      await selectRow(getRows()[2]);
      expect(animateCalls()).toBe(2);

      await flushMicrotasks();
      expect(isIdle()).toBe(false);
      animations[0].resolve();
      await flushMicrotasks();
      expect(isIdle()).toBe(false);
      animations[1].resolve();
      await flushMicrotasks();
      expect(isIdle()).toBe(true);
    });

    it("removes isIdle when the indicator hides", async () => {
      await startSelected(0);
      expect(isIdle()).toBe(true);
      await selectRow(undefined);
      expect(isIdle()).toBe(false);
    });

    it("removes isIdle on deck collapse and re-adds it IDLE_REARM_MS after expand", async () => {
      await startSelected(0);
      collapseDeck();
      expect(isIdle()).toBe(false);

      expandDeck();
      expect(isIdle()).toBe(false);
      vi.advanceTimersByTime(IDLE_REARM_MS - 1);
      expect(isIdle()).toBe(false);
      vi.advanceTimersByTime(1);
      expect(isIdle()).toBe(true);
    });

    it("ignores collapse events for other decks", async () => {
      await startSelected(0);
      emit(AppEvents.DECK_COLLAPSE_CHANGED, {
        deck: "members",
        collapsed: true,
      });
      emit(AppEvents.DECK_COLLAPSE_CHANGED, { deck: "tags", collapsed: false });
      expect(isIdle()).toBe(true);
      expect(vi.getTimerCount()).toBe(0);
    });

    it("handles the left panel the same way", async () => {
      await startSelected(0);
      emit(AppEvents.LEFT_PANEL_COLLAPSE_CHANGED, { collapsed: true });
      expect(isIdle()).toBe(false);
      emit(AppEvents.LEFT_PANEL_COLLAPSE_CHANGED, { collapsed: false });
      expect(isIdle()).toBe(false);
      vi.advanceTimersByTime(IDLE_REARM_MS);
      expect(isIdle()).toBe(true);
    });

    it("a re-collapse before the timer fires cancels it", async () => {
      await startSelected(0);
      collapseDeck();
      expandDeck();
      vi.advanceTimersByTime(IDLE_REARM_MS - 10);
      collapseDeck();
      expect(vi.getTimerCount()).toBe(0);
      vi.advanceTimersByTime(IDLE_REARM_MS * 2);
      expect(isIdle()).toBe(false);
    });

    it("a second expand replaces the pending timer", async () => {
      await startSelected(0);
      collapseDeck();
      expandDeck();
      vi.advanceTimersByTime(IDLE_REARM_MS - 10);
      expandDeck();
      expect(vi.getTimerCount()).toBe(1);
      vi.advanceTimersByTime(IDLE_REARM_MS - 1);
      expect(isIdle()).toBe(false);
      vi.advanceTimersByTime(1);
      expect(isIdle()).toBe(true);
    });

    it("the settle fire re-syncs with animate:false and starts no stretch", async () => {
      await startSelected(0);
      collapseDeck();
      expandDeck();
      stubGeometry({ row: getRows()[0], top: 3 * ROW_HEIGHT });
      vi.advanceTimersByTime(IDLE_REARM_MS);

      expect(animateCalls()).toBe(0);
      expect(getBar().style.transform).toBe(
        `translateY(${3 * ROW_HEIGHT}px) scaleY(1)`,
      );
      expect(isIdle()).toBe(true);
    });

    it("removes isIdle while the document is hidden and re-adds it when visible", async () => {
      await startSelected(0);
      setHidden(true);
      expect(isIdle()).toBe(false);
      setHidden(false);
      expect(isIdle()).toBe(true);
    });

    it("a stretch finishing while the document is hidden does not add isIdle", async () => {
      await startSelected(0);
      await selectRow(getRows()[1]);
      setHidden(true);
      animations[0].resolve();
      await flushMicrotasks();
      expect(isIdle()).toBe(false);
      setHidden(false);
      expect(isIdle()).toBe(true);
    });

    it("runs a pending sync before recomputing when the document becomes visible", async () => {
      await startSelected(0);
      setHidden(true);
      getRows()[0].classList.remove("active");
      getRows()[1].classList.add("active");
      await flushMicrotasks();
      expect(frameQueue.size).toBe(1);

      setHidden(false);
      expect(frameQueue.size).toBe(0);
      expect(getBar().style.transform).toBe(
        `translateY(${ROW_HEIGHT}px) scaleY(1)`,
      );
    });

    it("a snap or stretch finish while the deck is collapsed does not add isIdle", async () => {
      await startSelected(0);
      collapseDeck();
      await selectRow(getRows()[1]);
      animations[0]?.resolve();
      await flushMicrotasks();
      expect(isIdle()).toBe(false);
    });

    it("seeds deckCollapsed from #UTubDeck.collapsed at init, then expand re-adds isIdle", async () => {
      document.getElementById("UTubDeck")?.classList.add("collapsed");
      await startSelected(0);
      expect(isIdle()).toBe(false);

      document.getElementById("UTubDeck")?.classList.remove("collapsed");
      expandDeck();
      vi.advanceTimersByTime(IDLE_REARM_MS);
      expect(isIdle()).toBe(true);
    });

    it("seeds leftPanelCollapsed from #mainPanel.lhs-collapsed at init", async () => {
      document.getElementById("mainPanel")?.classList.add("lhs-collapsed");
      await startSelected(0);
      expect(isIdle()).toBe(false);

      document.getElementById("mainPanel")?.classList.remove("lhs-collapsed");
      emit(AppEvents.LEFT_PANEL_COLLAPSE_CHANGED, { collapsed: false });
      vi.advanceTimersByTime(IDLE_REARM_MS);
      expect(isIdle()).toBe(true);
    });

    it("re-seeds both flags from the DOM on the settle fire (stale flag corrected)", async () => {
      await startSelected(0);
      // The class flips with no collapse event, so the flag is stale (false).
      document.getElementById("mainPanel")?.classList.add("lhs-collapsed");
      expandDeck();
      vi.advanceTimersByTime(IDLE_REARM_MS);
      expect(isIdle()).toBe(false);

      // And the other way: a stale true flag is cleared by the next re-seed.
      document.getElementById("mainPanel")?.classList.remove("lhs-collapsed");
      expandDeck();
      vi.advanceTimersByTime(IDLE_REARM_MS);
      expect(isIdle()).toBe(true);
    });

    it("a hide during settling keeps the timer; a placement inside the window stays non-idle until the fire", async () => {
      await startSelected(0);
      collapseDeck();
      expandDeck();
      await selectRow(undefined);
      expect(vi.getTimerCount()).toBe(1);

      vi.advanceTimersByTime(IDLE_REARM_MS - 100);
      await selectRow(getRows()[1]);
      expect(getIndicator().classList.contains("isVisible")).toBe(true);
      expect(isIdle()).toBe(false);

      vi.advanceTimersByTime(100);
      expect(isIdle()).toBe(true);
    });

    it("a visibilitychange back to visible during settling does not add isIdle", async () => {
      await startSelected(0);
      collapseDeck();
      expandDeck();
      setHidden(true);
      setHidden(false);
      expect(isIdle()).toBe(false);
      vi.advanceTimersByTime(IDLE_REARM_MS);
      expect(isIdle()).toBe(true);
    });

    it("a stretch finish inside the settle window does not add isIdle", async () => {
      await startSelected(0);
      await selectRow(getRows()[1]);
      collapseDeck();
      expandDeck();
      animations[0].resolve();
      await flushMicrotasks();
      expect(isIdle()).toBe(false);
      vi.advanceTimersByTime(IDLE_REARM_MS);
      expect(isIdle()).toBe(true);
    });

    it("registers each Step 3 subscription once for a double init on the same list", async () => {
      vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
      const addSpy = vi.spyOn(document, "addEventListener");
      await initAndSettle();
      initUTubSelectionIndicator();
      const visibilityAdds = addSpy.mock.calls.filter(
        ([type]) => type === "visibilitychange",
      );
      expect(visibilityAdds).toHaveLength(1);

      const timeoutSpy = vi.spyOn(globalThis, "setTimeout");
      expandDeck();
      emit(AppEvents.LEFT_PANEL_COLLAPSE_CHANGED, { collapsed: false });
      expect(timeoutSpy).toHaveBeenCalledTimes(2);
      expect(vi.getTimerCount()).toBe(1);
    });

    it("rebinds the registrations when #listUTubs is replaced and releases the old ones", async () => {
      await startSelected(0);
      const removeSpy = vi.spyOn(document, "removeEventListener");
      const replacement = document.createElement("div");
      replacement.id = "listUTubs";
      getList().replaceWith(replacement);
      initUTubSelectionIndicator();
      flushFrames();
      expect(
        removeSpy.mock.calls.filter(([type]) => type === "visibilitychange"),
      ).toHaveLength(1);

      const timeoutSpy = vi.spyOn(globalThis, "setTimeout");
      expandDeck();
      expect(timeoutSpy).toHaveBeenCalledTimes(1);

      const row = makeRow({ utubid: 9, index: 0 });
      row.classList.add("active");
      replacement.append(row);
      await flushObserverAndFrame();
      expect(isIdle()).toBe(false);
      vi.advanceTimersByTime(IDLE_REARM_MS);
      expect(isIdle()).toBe(true);
    });

    it("reset releases subscriptions and listener, clears the timer, settling and classes", async () => {
      await startSelected(0);
      const removeSpy = vi.spyOn(document, "removeEventListener");
      collapseDeck();
      expandDeck();
      expect(vi.getTimerCount()).toBe(1);

      resetUTubSelectionIndicatorForTests();
      expect(vi.getTimerCount()).toBe(0);
      expect(
        removeSpy.mock.calls.filter(([type]) => type === "visibilitychange"),
      ).toHaveLength(1);
      expect(isIdle()).toBe(false);
      expect(getIndicator().classList.contains("isVisible")).toBe(false);

      const timeoutSpy = vi.spyOn(globalThis, "setTimeout");
      expandDeck();
      collapseDeck();
      setHidden(true);
      setHidden(false);
      expect(timeoutSpy).not.toHaveBeenCalled();

      // settling was cleared: a fresh init places idle immediately.
      await initAndSettle();
      await selectRow(getRows()[0]);
      expect(isIdle()).toBe(true);
    });

    it("teardown by re-init on a replaced list cancels a running stretch and resets state", async () => {
      await startSelected(0);
      await selectRow(getRows()[1]);
      expect(animateCalls()).toBe(1);
      collapseDeck();
      expandDeck();

      const replacement = document.createElement("div");
      replacement.id = "listUTubs";
      getList().replaceWith(replacement);
      initUTubSelectionIndicator();
      await flushMicrotasks();

      expect(animations[0].cancel).toHaveBeenCalledTimes(1);
      expect(vi.getTimerCount()).toBe(0);
      expect(isIdle()).toBe(false);
      expect(getIndicator().classList.contains("isVisible")).toBe(false);

      // lastPlaced/pending animate flag cleared: the next placement snaps,
      // and settling is false so it is idle straight away.
      flushFrames();
      const row = makeRow({ utubid: 5, index: 2 });
      row.classList.add("active");
      replacement.append(row);
      await flushObserverAndFrame();
      expect(animateCalls()).toBe(1);
      expect(isIdle()).toBe(true);
    });
  });

  describe("layout re-sync", () => {
    type FakeResizeObserver = {
      callback: () => void;
      observed: Element[];
      disconnect: Mock<() => void>;
    };
    let observers: FakeResizeObserver[];
    const isIdle = (): boolean => getIndicator().classList.contains("isIdle");

    async function flushMicrotasks(): Promise<void> {
      await Promise.resolve();
      await Promise.resolve();
    }

    function fireResize(): void {
      for (const observer of observers) observer.callback();
    }

    beforeEach(() => {
      observers = [];
      vi.stubGlobal(
        "ResizeObserver",
        class {
          private fake: FakeResizeObserver;
          constructor(callback: () => void) {
            this.fake = {
              callback,
              observed: [],
              disconnect: vi.fn<() => void>(),
            };
            observers.push(this.fake);
          }
          observe(target: Element): void {
            this.fake.observed.push(target);
          }
          disconnect(): void {
            this.fake.disconnect();
          }
        },
      );
    });

    async function startOn(index: number): Promise<void> {
      vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
      await initAndSettle();
      await selectRow(getRows()[index]);
    }

    it("observes the list, the scroller and the blocks above the list", async () => {
      await initAndSettle();
      expect(observers).toHaveLength(1);
      const ids = observers[0].observed.map((el) => el.id);
      expect(ids).toEqual(
        expect.arrayContaining([
          "listUTubs",
          "UTubDeckContent",
          "UTubSearchNoResults",
        ]),
      );
      expect(ids).not.toContain("UTubSelectionIndicator");
    });

    it("a resize re-places the bar on the shifted active row without a stretch", async () => {
      await startOn(1);
      for (const [index, row] of getRows().entries())
        stubGeometry({ row, top: index * 60 + 20, height: 60 });
      fireResize();
      flushFrames();
      expect(getBar().style.transform).toBe("translateY(80px) scaleY(1)");
      expect(getBar().style.height).toBe("60px");
      expect(getClip().style.transform).toBe("translateY(80px)");
      expect(animateCalls()).toBe(0);
    });

    it("a selection change after a resize still stretches", async () => {
      await startOn(0);
      fireResize();
      flushFrames();
      await selectRow(getRows()[2]);
      expect(animateCalls()).toBe(1);
    });

    it("MOBILE_DECK_SWITCHED re-places the bar without a stretch", async () => {
      await startOn(0);
      stubGeometry({ row: getRows()[0], top: 0, height: 66 });
      emit(AppEvents.MOBILE_DECK_SWITCHED, { target: "utub-deck" });
      flushFrames();
      expect(getBar().style.height).toBe("66px");
      expect(animateCalls()).toBe(0);
    });

    it("hides when the active row stops rendering and snaps back when it returns", async () => {
      await startOn(1);
      stubGeometry({ row: getRows()[1], top: 40, rendered: false });
      fireResize();
      flushFrames();
      expect(getIndicator().classList.contains("isVisible")).toBe(false);
      expect(isIdle()).toBe(false);

      stubGeometry({ row: getRows()[1], top: 40 });
      fireResize();
      flushFrames();
      expect(getIndicator().classList.contains("isVisible")).toBe(true);
      expect(getBar().style.transform).toBe("translateY(40px) scaleY(1)");
      expect(animateCalls()).toBe(0);
    });

    it("removing a non-active row shifts the active row without a stretch", async () => {
      await startOn(2);
      getRows()[0].remove();
      for (const [index, row] of getRows().entries())
        stubGeometry({ row, top: index * ROW_HEIGHT });
      await flushObserverAndFrame();
      expect(getBar().style.transform).toBe(
        `translateY(${ROW_HEIGHT}px) scaleY(1)`,
      );
      expect(animateCalls()).toBe(0);
    });

    it("a geometry-neutral resize or deck switch leaves a running stretch alone", async () => {
      await startOn(0);
      await selectRow(getRows()[2]);
      expect(animateCalls()).toBe(1);
      fireResize();
      emit(AppEvents.MOBILE_DECK_SWITCHED, { target: "utub-deck" });
      flushFrames();
      expect(animations[0].cancel).not.toHaveBeenCalled();
      expect(animateCalls()).toBe(1);
    });

    it("collapse and expand settle with an animate:false re-sync and no stretch", async () => {
      await startOn(1);
      emit(AppEvents.DECK_COLLAPSE_CHANGED, { deck: "utubs", collapsed: true });
      emit(AppEvents.DECK_COLLAPSE_CHANGED, {
        deck: "utubs",
        collapsed: false,
      });
      stubGeometry({ row: getRows()[1], top: 55 });
      vi.advanceTimersByTime(IDLE_REARM_MS);
      expect(getBar().style.transform).toBe("translateY(55px) scaleY(1)");
      expect(animateCalls()).toBe(0);
      expect(isIdle()).toBe(true);

      emit(AppEvents.LEFT_PANEL_COLLAPSE_CHANGED, { collapsed: true });
      emit(AppEvents.LEFT_PANEL_COLLAPSE_CHANGED, { collapsed: false });
      stubGeometry({ row: getRows()[1], top: 70 });
      vi.advanceTimersByTime(IDLE_REARM_MS);
      expect(getBar().style.transform).toBe("translateY(70px) scaleY(1)");
      expect(animateCalls()).toBe(0);
    });

    it("re-seeds the flags from the DOM on a resize with no event emitted", async () => {
      await startOn(0);
      expect(isIdle()).toBe(true);
      document.getElementById("mainPanel")?.classList.add("lhs-collapsed");
      fireResize();
      await flushMicrotasks();
      expect(isIdle()).toBe(false);
      document.getElementById("mainPanel")?.classList.remove("lhs-collapsed");
      fireResize();
      flushFrames();
      expect(isIdle()).toBe(true);

      document.getElementById("UTubDeck")?.classList.add("collapsed");
      emit(AppEvents.MOBILE_DECK_SWITCHED, { target: "utub-deck" });
      expect(isIdle()).toBe(false);
      document.getElementById("UTubDeck")?.classList.remove("collapsed");
      emit(AppEvents.MOBILE_DECK_SWITCHED, { target: "utub-deck" });
      expect(isIdle()).toBe(true);
    });

    it("registers once for a double init, rebinds on a replaced list, and reset releases", async () => {
      await initAndSettle();
      initUTubSelectionIndicator();
      expect(observers).toHaveLength(1);

      const replacement = document.createElement("div");
      replacement.id = "listUTubs";
      getList().replaceWith(replacement);
      initUTubSelectionIndicator();
      expect(observers[0].disconnect).toHaveBeenCalledTimes(1);
      expect(observers).toHaveLength(2);
      flushFrames();

      // One resync per emit reads #UTubDeck exactly once (no duplicate
      // subscription from the double init or the rebind).
      const lookupSpy = vi.spyOn(document, "getElementById");
      emit(AppEvents.MOBILE_DECK_SWITCHED, { target: "utub-deck" });
      const deckLookups = (): number =>
        lookupSpy.mock.calls.filter(([id]) => id === "UTubDeck").length;
      expect(deckLookups()).toBe(1);

      resetUTubSelectionIndicatorForTests();
      expect(observers[1].disconnect).toHaveBeenCalledTimes(1);
      lookupSpy.mockClear();
      emit(AppEvents.MOBILE_DECK_SWITCHED, { target: "utub-deck" });
      expect(deckLookups()).toBe(0);
    });

    it("does not throw when ResizeObserver is undefined", () => {
      vi.stubGlobal("ResizeObserver", undefined);
      expect(() => initUTubSelectionIndicator()).not.toThrow();
    });
  });

  describe("init and teardown", () => {
    it("registers one MutationObserver for a double init and one sync per change", async () => {
      const observeSpy = vi.spyOn(MutationObserver.prototype, "observe");
      initUTubSelectionIndicator();
      initUTubSelectionIndicator();
      expect(observeSpy).toHaveBeenCalledTimes(1);
      flushFrames();

      expect(frameQueue.size).toBe(0);
      getRows()[0].classList.add("active");
      await Promise.resolve();
      await Promise.resolve();
      expect(frameQueue.size).toBe(1);
      observeSpy.mockRestore();
    });

    it("tears down and rebinds when #listUTubs is replaced, so the next placement snaps", async () => {
      await initAndSettle();
      getRows()[0].classList.add("active");
      await flushObserverAndFrame();
      expect(getIndicator().classList.contains("isVisible")).toBe(true);

      const oldList = getList();
      const replacement = document.createElement("div");
      replacement.id = "listUTubs";
      oldList.replaceWith(replacement);
      const disconnectSpy = vi.spyOn(MutationObserver.prototype, "disconnect");
      initUTubSelectionIndicator();
      expect(disconnectSpy).toHaveBeenCalledTimes(1);
      expect(getIndicator().classList.contains("isVisible")).toBe(false);
      flushFrames();

      const row = makeRow({ utubid: 7, index: 4 });
      row.classList.add("active");
      replacement.append(row);
      await flushObserverAndFrame();
      expect(getBar().style.transform).toBe(
        `translateY(${4 * ROW_HEIGHT}px) scaleY(1)`,
      );
      disconnectSpy.mockRestore();
    });

    it("reset releases the observer, cancels the pending frame and removes classes", async () => {
      await initAndSettle();
      getRows()[0].classList.add("active");
      await flushObserverAndFrame();
      getRows()[1].classList.add("active");
      await Promise.resolve();
      await Promise.resolve();
      expect(frameQueue.size).toBe(1);

      resetUTubSelectionIndicatorForTests();
      expect(frameQueue.size).toBe(0);
      expect(getIndicator().classList.contains("isVisible")).toBe(false);
      expect(getIndicator().classList.contains("isIdle")).toBe(false);

      getRows()[2].classList.add("active");
      await flushObserverAndFrame();
      expect(getIndicator().classList.contains("isVisible")).toBe(false);
    });

    it("is a no-op when the indicator or #listUTubs is absent", () => {
      document.body.innerHTML = "";
      expect(() => initUTubSelectionIndicator()).not.toThrow();
      expect(() => syncUTubSelectionIndicator({ animate: true })).not.toThrow();
      expect(frameQueue.size).toBe(0);
    });

    it("does not throw when MutationObserver is undefined", () => {
      vi.stubGlobal("MutationObserver", undefined);
      expect(() => initUTubSelectionIndicator()).not.toThrow();
    });
  });
});
