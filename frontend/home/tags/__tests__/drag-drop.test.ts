vi.mock("../../mobile.js", () => ({ isMobile: vi.fn(() => false) }));

const TAG_HTML = `
  <div id="TagDeck">
    <div id="listTags">
      <div class="tagFilter" data-utub-tag-id="7"><span>alpha</span><div class="tagMenuWrap hidden"></div></div>
      <div class="tagFilter" data-utub-tag-id="9"><span>beta</span><div class="tagMenuWrap hidden"></div></div>
    </div>
  </div>
  <div class="urlRow" id="card"></div>
`;

const MIME = "application/x-u4i-tag-id";

type DragModule = typeof import("../drag-drop.js");

interface MockMediaQueryList {
  matches: boolean;
  addEventListener: ReturnType<typeof vi.fn>;
  fireChange: () => void;
}

let mql: MockMediaQueryList;
let drag: DragModule;
let setMobile: (value: boolean) => Promise<void>;
let emitDeckSwitched: () => Promise<void>;
let setMultiSelect: (value: boolean) => Promise<void>;

function chip(tagID: number): HTMLElement {
  return document.querySelector(
    `#listTags .tagFilter[data-utub-tag-id="${tagID}"]`,
  ) as HTMLElement;
}

function makeChip(tagID: number, label: string): HTMLElement {
  const node = document.createElement("div");
  node.className = "tagFilter";
  node.setAttribute("data-utub-tag-id", String(tagID));
  node.innerHTML = `<span>${label}</span><div class="tagMenuWrap hidden"></div>`;
  return node;
}

function fireDragStart(target: HTMLElement): {
  event: Event;
  dataTransfer: {
    setData: ReturnType<typeof vi.fn>;
    setDragImage: ReturnType<typeof vi.fn>;
    effectAllowed: string;
  };
} {
  const dataTransfer = {
    setData: vi.fn(),
    setDragImage: vi.fn(),
    effectAllowed: "uninitialized",
  };
  const event = new Event("dragstart", { bubbles: true, cancelable: true });
  Object.defineProperty(event, "dataTransfer", { value: dataTransfer });
  target.dispatchEvent(event);
  return { event, dataTransfer };
}

async function flushObserver(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
}

function addStaleDragMarks(): void {
  const card = document.getElementById("card") as HTMLElement;
  card.classList.add("tagDropTarget", "tagDropInvalid");
  card.setAttribute("data-drop-hint", "x");
}

function expectNoDragResidue(): void {
  const card = document.getElementById("card") as HTMLElement;
  expect(drag.getDraggedTagID()).toBeNull();
  expect(document.querySelector(".tagDragging")).toBeNull();
  expect(card.classList.contains("tagDropTarget")).toBe(false);
  expect(card.classList.contains("tagDropInvalid")).toBe(false);
  expect(card.hasAttribute("data-drop-hint")).toBe(false);
}

describe("tag drag-and-drop source", () => {
  beforeEach(async () => {
    vi.resetModules();
    document.body.innerHTML = TAG_HTML;

    const listeners: Array<() => void> = [];
    mql = {
      matches: true,
      addEventListener: vi.fn((_type: string, handler: () => void) => {
        listeners.push(handler);
      }),
      fireChange: () => listeners.forEach((handler) => handler()),
    };
    window.matchMedia = vi.fn(() => mql) as unknown as typeof window.matchMedia;

    const mobile = await import("../../mobile.js");
    const eventBus = await import("../../../lib/event-bus.js");
    const store = await import("../../../store/app-store.js");
    setMobile = async (value: boolean) => {
      (mobile.isMobile as ReturnType<typeof vi.fn>).mockReturnValue(value);
    };
    emitDeckSwitched = async () => {
      eventBus.emit(eventBus.AppEvents.MOBILE_DECK_SWITCHED, {
        target: "desktop",
      });
    };
    setMultiSelect = async (value: boolean) => {
      store.setState({ multiSelectMode: value });
    };
    await setMobile(false);
    await setMultiSelect(false);

    drag = await import("../drag-drop.js");
  });

  afterEach(() => {
    document.body.innerHTML = "";
    vi.restoreAllMocks();
  });

  describe("gate", () => {
    it("is enabled when matchMedia matches and isMobile is false", () => {
      expect(drag.isTagDragEnabled()).toBe(true);
    });

    it("is disabled when matchMedia does not match", () => {
      mql.matches = false;
      expect(drag.isTagDragEnabled()).toBe(false);
    });

    it("is disabled when isMobile is true even if matchMedia matches", async () => {
      await setMobile(true);
      expect(drag.isTagDragEnabled()).toBe(false);
    });
  });

  describe("draggable attribute", () => {
    it("sets draggable on chips only when enabled", () => {
      drag.initTagDragDrop();
      expect(chip(7).getAttribute("draggable")).toBe("true");
      expect(chip(9).getAttribute("draggable")).toBe("true");
    });

    it("does not set draggable when the gate is off", () => {
      mql.matches = false;
      drag.initTagDragDrop();
      expect(chip(7).hasAttribute("draggable")).toBe(false);
    });

    it("re-applies draggable to a chip appended after init", async () => {
      drag.initTagDragDrop();
      const added = makeChip(11, "gamma");
      document.getElementById("listTags")!.appendChild(added);
      await flushObserver();
      expect(added.getAttribute("draggable")).toBe("true");
    });

    it("re-applies draggable to chips re-created after emptying #listTags", async () => {
      drag.initTagDragDrop();
      const list = document.getElementById("listTags") as HTMLElement;
      list.innerHTML = "";
      list.appendChild(makeChip(7, "alpha"));
      await flushObserver();
      expect(chip(7).getAttribute("draggable")).toBe("true");
    });

    it("re-syncs on MOBILE_DECK_SWITCHED without a matchMedia change", async () => {
      drag.initTagDragDrop();
      await setMobile(true);
      await emitDeckSwitched();
      expect(chip(7).hasAttribute("draggable")).toBe(false);

      await setMobile(false);
      await emitDeckSwitched();
      expect(chip(7).getAttribute("draggable")).toBe("true");
    });

    it("re-syncs on a matchMedia change event", () => {
      drag.initTagDragDrop();
      mql.matches = false;
      mql.fireChange();
      expect(chip(7).hasAttribute("draggable")).toBe(false);
      mql.matches = true;
      mql.fireChange();
      expect(chip(7).getAttribute("draggable")).toBe("true");
    });

    it("removes draggable in edit-all-tags mode and restores it after", () => {
      drag.initTagDragDrop();
      document
        .querySelectorAll("#listTags .tagMenuWrap")
        .forEach((wrap) => wrap.classList.remove("hidden"));
      drag.syncTagDragState();
      expect(chip(7).hasAttribute("draggable")).toBe(false);

      document
        .querySelectorAll("#listTags .tagMenuWrap")
        .forEach((wrap) => wrap.classList.add("hidden"));
      drag.syncTagDragState();
      expect(chip(7).getAttribute("draggable")).toBe("true");
    });
  });

  describe("dragstart / dragend", () => {
    it("sets the tag ID payload, copy effect, drag image and module state", () => {
      drag.initTagDragDrop();
      const { event, dataTransfer } = fireDragStart(chip(7));

      expect(event.defaultPrevented).toBe(false);
      expect(dataTransfer.setData).toHaveBeenCalledWith(MIME, "7");
      expect(dataTransfer.effectAllowed).toBe("copy");
      expect(dataTransfer.setDragImage).toHaveBeenCalledTimes(1);
      expect(drag.getDraggedTagID()).toBe(7);
      expect(chip(7).classList.contains("tagDragging")).toBe(true);
    });

    it("dragend clears the state and the tagDragging class", () => {
      drag.initTagDragDrop();
      fireDragStart(chip(7));
      addStaleDragMarks();

      document
        .getElementById("TagDeck")!
        .dispatchEvent(new Event("dragend", { bubbles: true }));

      expectNoDragResidue();
    });

    it("cancels dragstart when the gate is off", () => {
      mql.matches = false;
      drag.initTagDragDrop();
      const { event, dataTransfer } = fireDragStart(chip(7));

      expect(event.defaultPrevented).toBe(true);
      expect(dataTransfer.setData).not.toHaveBeenCalled();
      expect(drag.getDraggedTagID()).toBeNull();
    });

    it("cancels dragstart when isMobile is true", async () => {
      drag.initTagDragDrop();
      await setMobile(true);
      const { event } = fireDragStart(chip(7));
      expect(event.defaultPrevented).toBe(true);
      expect(drag.getDraggedTagID()).toBeNull();
    });

    it("cancels dragstart in edit-all-tags mode", () => {
      drag.initTagDragDrop();
      document
        .querySelectorAll("#listTags .tagMenuWrap")
        .forEach((wrap) => wrap.classList.remove("hidden"));
      const { event } = fireDragStart(chip(7));
      expect(event.defaultPrevented).toBe(true);
      expect(drag.getDraggedTagID()).toBeNull();
    });

    it("cancels dragstart in multi-select mode and leaves draggable unchanged", async () => {
      drag.initTagDragDrop();
      await setMultiSelect(true);
      const { event } = fireDragStart(chip(7));
      expect(event.defaultPrevented).toBe(true);
      expect(drag.getDraggedTagID()).toBeNull();
      expect(chip(7).getAttribute("draggable")).toBe("true");
    });

    it.each([
      ["missing", null],
      ["non-numeric", "abc"],
    ])(
      "fails closed when the chip's data-utub-tag-id is %s",
      (_label, value) => {
        drag.initTagDragDrop();
        const target = chip(7);
        if (value === null) target.removeAttribute("data-utub-tag-id");
        else target.setAttribute("data-utub-tag-id", value);

        const { event, dataTransfer } = fireDragStart(target);

        expect(event.defaultPrevented).toBe(true);
        expect(dataTransfer.setData).not.toHaveBeenCalled();
        expect(drag.getDraggedTagID()).toBeNull();
        expect(target.classList.contains("tagDragging")).toBe(false);
      },
    );

    it("fails closed when the event has no dataTransfer", () => {
      drag.initTagDragDrop();
      const event = new Event("dragstart", { bubbles: true, cancelable: true });
      chip(7).dispatchEvent(event);

      expect(event.defaultPrevented).toBe(true);
      expect(drag.getDraggedTagID()).toBeNull();
      expect(chip(7).classList.contains("tagDragging")).toBe(false);
    });
  });

  describe("mid-drag cleanup", () => {
    it("clears the drag when a matchMedia change fires and re-syncs draggable", () => {
      drag.initTagDragDrop();
      fireDragStart(chip(7));
      addStaleDragMarks();

      mql.matches = false;
      mql.fireChange();

      expectNoDragResidue();
      expect(chip(7).hasAttribute("draggable")).toBe(false);
    });

    it("clears the drag when the gate turns off via MOBILE_DECK_SWITCHED", async () => {
      drag.initTagDragDrop();
      fireDragStart(chip(7));
      addStaleDragMarks();

      await setMobile(true);
      await emitDeckSwitched();

      expectNoDragResidue();
    });

    it("clears the drag when #listTags is emptied mid-drag", async () => {
      drag.initTagDragDrop();
      fireDragStart(chip(7));
      addStaleDragMarks();

      document.getElementById("listTags")!.innerHTML = "";
      await flushObserver();

      expectNoDragResidue();
    });

    it("clears the drag when the chip is replaced by a rebuilt node with the same tag ID", async () => {
      drag.initTagDragDrop();
      fireDragStart(chip(7));
      addStaleDragMarks();

      chip(7).replaceWith(makeChip(7, "alpha"));
      await flushObserver();

      expectNoDragResidue();
    });

    it("keeps the drag when the same chip node is merely re-appended by a re-sort", async () => {
      drag.initTagDragDrop();
      const dragged = chip(7);
      fireDragStart(dragged);

      const list = document.getElementById("listTags") as HTMLElement;
      dragged.remove();
      list.appendChild(dragged);
      await flushObserver();

      expect(drag.getDraggedTagID()).toBe(7);
      expect(dragged.classList.contains("tagDragging")).toBe(true);
    });
  });
});
