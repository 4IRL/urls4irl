import {
  initUTubSelectionIndicator,
  syncUTubSelectionIndicator,
  resetUTubSelectionIndicatorForTests,
} from "../selection-indicator.js";

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
}: {
  row: HTMLElement;
  top: number;
  rendered?: boolean;
}): void {
  Object.defineProperty(row, "offsetTop", { value: top, configurable: true });
  Object.defineProperty(row, "offsetHeight", {
    value: rendered ? ROW_HEIGHT : 0,
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
    <div id="UTubDeckContent">
      <div id="UTubSelectionIndicator" class="utubSelectionIndicator"
           aria-hidden="true" data-selected-label="${LABEL}">
        <div class="utubSelectionBar"></div>
        <div class="utubSelectionShimmerClip"><div class="utubSelectionShimmer"></div></div>
      </div>
      <div id="listUTubs"></div>
    </div>
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

describe("selection-indicator", () => {
  beforeEach(() => {
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
    vi.unstubAllGlobals();
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
