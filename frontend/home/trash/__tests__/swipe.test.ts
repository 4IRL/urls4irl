import { AppEvents, emit } from "../../../lib/event-bus.js";
import { isMobile } from "../../mobile.js";
import { restoreTrashedURL } from "../actions.js";
import { consumeTrashClickSuppression } from "../swipe-click-guard.js";
import { initTrashSwipe, _resetTrashSwipeForTests } from "../swipe.js";

vi.mock("../actions.js", () => ({
  restoreTrashedURL: vi.fn(() => Promise.resolve(true)),
}));
vi.mock("../../mobile.js", () => ({
  isMobile: vi.fn(() => true),
}));

const $ = window.jQuery;

const UTUB_ID = 7;
const UTUB_URL_ID = 42;
// 35% of 200 is the 70px distance-commit threshold.
const REVEAL_WIDTH_PX = 200;
const START_X = 100;
const SPIN_UNTIL_REAL_ELAPSED_SAFETY_CEILING_MS = 1000;

const ROW_HTML = `
  <div class="trashRow trashRowSwipeable" tabindex="-1" data-utub-id="${UTUB_ID}" data-utub-url-id="${UTUB_URL_ID}">
    <div class="trashRowSwipeReveal" aria-hidden="true"></div>
    <div class="trashRowContent">
      <span class="t-title">Title</span>
      <div class="actions">
        <button class="trashBtnRestore"></button>
        <button class="trashBtnPurge"></button>
        <span class="chip chip-origin"></span>
      </div>
    </div>
  </div>
`;

type PointerType =
  | "pointerdown"
  | "pointermove"
  | "pointerup"
  | "pointercancel"
  | "lostpointercapture";

function stubRevealWidth({ row, width }: { row: JQuery; width: number }): void {
  const reveal = row.find(".trashRowSwipeReveal")[0] as HTMLElement;
  reveal.getBoundingClientRect = (): DOMRect =>
    ({
      width,
      height: 44,
      top: 0,
      bottom: 44,
      left: 0,
      right: width,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    }) as DOMRect;
}

function mountRow({ armed = true }: { armed?: boolean } = {}): JQuery {
  const row = $(ROW_HTML);
  if (!armed) row.removeClass("trashRowSwipeable");
  $("#listTrashURLs").append(row);
  stubRevealWidth({ row, width: REVEAL_WIDTH_PX });
  return row;
}

function dispatchPointer({
  target,
  type,
  clientX,
  clientY = 0,
  pointerId = 1,
  pointerType = "touch",
}: {
  target: HTMLElement;
  type: PointerType;
  clientX: number;
  clientY?: number;
  pointerId?: number;
  pointerType?: string;
}): void {
  const event = new Event(type, { bubbles: true, cancelable: true });
  Object.defineProperty(event, "button", { value: 0 });
  Object.defineProperty(event, "pointerId", { value: pointerId });
  Object.defineProperty(event, "clientX", { value: clientX });
  Object.defineProperty(event, "clientY", { value: clientY });
  Object.defineProperty(event, "pointerType", { value: pointerType });
  target.dispatchEvent(event);
}

// Real-clock busy wait so the drag's elapsedMs is never the degenerate same-tick 0.
function spinUntilRealElapsed({
  minElapsedMs,
}: {
  minElapsedMs: number;
}): void {
  const startTimestamp = performance.now();
  while (performance.now() - startTimestamp < minElapsedMs) {
    if (
      performance.now() - startTimestamp >
      SPIN_UNTIL_REAL_ELAPSED_SAFETY_CEILING_MS
    ) {
      throw new Error("spinUntilRealElapsed exceeded its safety ceiling");
    }
  }
}

/** A slow drag from START_X by `deltaX`, released at the end (never a fling). */
function slowDrag({
  target,
  deltaX,
  release = true,
  startX = START_X,
}: {
  target: HTMLElement;
  deltaX: number;
  release?: boolean;
  startX?: number;
}): void {
  dispatchPointer({ target, type: "pointerdown", clientX: startX });
  spinUntilRealElapsed({ minElapsedMs: 80 });
  dispatchPointer({ target, type: "pointermove", clientX: startX + deltaX });
  if (release) {
    dispatchPointer({ target, type: "pointerup", clientX: startX + deltaX });
  }
}

function contentTransform(row: JQuery): string {
  return (row.find(".trashRowContent")[0] as HTMLElement).style.transform;
}

describe("trash swipe-right-to-restore", () => {
  beforeEach(() => {
    _resetTrashSwipeForTests();
    document.body.innerHTML = `
      <div id="TrashPanel">
        <div id="listTrashURLs"></div>
      </div>
      <div id="outside"></div>
    `;
    vi.clearAllMocks();
    vi.mocked(isMobile).mockReturnValue(true);
    vi.mocked(restoreTrashedURL).mockImplementation(() =>
      Promise.resolve(true),
    );
    initTrashSwipe();
  });

  afterEach(() => {
    vi.useRealTimers();
    _resetTrashSwipeForTests();
  });

  describe("commit", () => {
    it("a rightward drag past 35% restores once with the row's ids and swipe flag", () => {
      const row = mountRow();

      slowDrag({ target: row[0], deltaX: 80 });

      expect(restoreTrashedURL).toHaveBeenCalledTimes(1);
      expect(restoreTrashedURL).toHaveBeenCalledWith({
        utubID: UTUB_ID,
        utubUrlID: UTUB_URL_ID,
        destUtubID: undefined,
        viaSwipe: true,
      });
      expect(row.hasClass("swipe-committed")).toBe(true);
      expect(row.hasClass("swipe-dragging")).toBe(false);
      expect(contentTransform(row)).toBe("");
    });

    it("a fast short fling commits on velocity alone", () => {
      const row = mountRow();

      // 25px in 10ms = 2.5 px/ms, deterministic regardless of host speed.
      let now = 1000;
      const clock = vi.spyOn(performance, "now").mockImplementation(() => now);
      dispatchPointer({
        target: row[0],
        type: "pointerdown",
        clientX: START_X,
      });
      now = 1010;
      dispatchPointer({
        target: row[0],
        type: "pointermove",
        clientX: START_X + 25,
      });
      dispatchPointer({
        target: row[0],
        type: "pointerup",
        clientX: START_X + 25,
      });
      clock.mockRestore();

      expect(restoreTrashedURL).toHaveBeenCalledTimes(1);
    });

    it("a net-leftward release never commits, even with a positive last velocity sample", () => {
      const row = mountRow();
      let now = 1000;
      const clock = vi.spyOn(performance, "now").mockImplementation(() => now);
      dispatchPointer({
        target: row[0],
        type: "pointerdown",
        clientX: START_X,
      });
      now = 1010;
      dispatchPointer({
        target: row[0],
        type: "pointermove",
        clientX: START_X - 50,
      });
      now = 1020;
      dispatchPointer({
        target: row[0],
        type: "pointermove",
        clientX: START_X - 40,
      });
      dispatchPointer({
        target: row[0],
        type: "pointerup",
        clientX: START_X - 40,
      });
      clock.mockRestore();

      expect(restoreTrashedURL).not.toHaveBeenCalled();
      expect(row.hasClass("swipe-committed")).toBe(false);
    });

    it("a row detached mid-drag (no events on it) does not block the next swipe", () => {
      const row = mountRow();
      slowDrag({ target: row[0], deltaX: 60, release: false });
      row.remove();

      const next = mountRow();
      slowDrag({ target: next[0], deltaX: 90 });

      expect(restoreTrashedURL).toHaveBeenCalledTimes(1);
    });

    it("tracks the finger rightward and clamps movement to [0, revealWidth]", () => {
      const row = mountRow();

      slowDrag({ target: row[0], deltaX: 50, release: false });
      expect(contentTransform(row)).toBe("translateX(50px)");
      expect(row.hasClass("swipe-dragging")).toBe(true);

      dispatchPointer({
        target: row[0],
        type: "pointermove",
        clientX: START_X + 500,
      });
      expect(contentTransform(row)).toBe(`translateX(${REVEAL_WIDTH_PX}px)`);

      dispatchPointer({
        target: row[0],
        type: "pointermove",
        clientX: START_X - 40,
      });
      expect(contentTransform(row)).toBe("translateX(0px)");
    });
  });

  describe("never restores", () => {
    it("a sub-threshold slow drag snaps back", () => {
      const row = mountRow();

      slowDrag({ target: row[0], deltaX: 30 });

      expect(restoreTrashedURL).not.toHaveBeenCalled();
      expect(row.hasClass("swipe-dragging")).toBe(false);
      expect(row.hasClass("swipe-committed")).toBe(false);
      expect(contentTransform(row)).toBe("");
    });

    it("a tap (no movement) is left to the click handlers", () => {
      const row = mountRow();

      dispatchPointer({
        target: row[0],
        type: "pointerdown",
        clientX: START_X,
      });
      dispatchPointer({ target: row[0], type: "pointerup", clientX: START_X });

      expect(restoreTrashedURL).not.toHaveBeenCalled();
      expect(row.hasClass("swipe-dragging")).toBe(false);
    });

    it("a leftward drag never restores", () => {
      const row = mountRow();

      slowDrag({ target: row[0], deltaX: -90 });

      expect(restoreTrashedURL).not.toHaveBeenCalled();
      expect(contentTransform(row)).toBe("");
    });

    it("a vertical-dominant drag lets native scroll win", () => {
      const row = mountRow();

      dispatchPointer({
        target: row[0],
        type: "pointerdown",
        clientX: START_X,
      });
      dispatchPointer({
        target: row[0],
        type: "pointermove",
        clientX: START_X + 12,
        clientY: 60,
      });
      dispatchPointer({
        target: row[0],
        type: "pointerup",
        clientX: START_X + 120,
        clientY: 60,
      });

      expect(restoreTrashedURL).not.toHaveBeenCalled();
      expect(row.hasClass("swipe-dragging")).toBe(false);
    });

    it("pointercancel resets the row", () => {
      const row = mountRow();

      slowDrag({ target: row[0], deltaX: 60, release: false });
      dispatchPointer({
        target: row[0],
        type: "pointercancel",
        clientX: START_X + 60,
      });

      expect(row.hasClass("swipe-dragging")).toBe(false);
      expect(contentTransform(row)).toBe("");
      expect(restoreTrashedURL).not.toHaveBeenCalled();
    });

    it("a second pointer mid-drag neither starts nor moves a drag", () => {
      const row = mountRow();

      slowDrag({ target: row[0], deltaX: 20, release: false });
      dispatchPointer({
        target: row[0],
        type: "pointerdown",
        clientX: 150,
        pointerId: 2,
      });
      dispatchPointer({
        target: row[0],
        type: "pointermove",
        clientX: 190,
        pointerId: 2,
      });
      dispatchPointer({
        target: row[0],
        type: "pointerup",
        clientX: 190,
        pointerId: 2,
      });

      expect(contentTransform(row)).toBe("translateX(20px)");
      expect(restoreTrashedURL).not.toHaveBeenCalled();
    });

    it("a mouse pointer never begins a drag", () => {
      const row = mountRow();
      dispatchPointer({
        target: row[0],
        type: "pointerdown",
        clientX: START_X,
        pointerType: "mouse",
      });
      dispatchPointer({
        target: row[0],
        type: "pointermove",
        clientX: START_X + 150,
        pointerType: "mouse",
      });
      dispatchPointer({
        target: row[0],
        type: "pointerup",
        clientX: START_X + 150,
        pointerType: "mouse",
      });

      expect(restoreTrashedURL).not.toHaveBeenCalled();
      expect(row.hasClass("swipe-dragging")).toBe(false);
    });

    it("a desktop width never begins a drag", () => {
      vi.mocked(isMobile).mockReturnValue(false);
      const row = mountRow();

      slowDrag({ target: row[0], deltaX: 120 });

      expect(restoreTrashedURL).not.toHaveBeenCalled();
      expect(row.hasClass("swipe-dragging")).toBe(false);
    });

    it("an unarmed row (no .trashRowSwipeable) never begins a drag", () => {
      const row = mountRow({ armed: false });

      slowDrag({ target: row[0], deltaX: 120 });

      expect(restoreTrashedURL).not.toHaveBeenCalled();
      expect(row.hasClass("swipe-dragging")).toBe(false);
    });
  });

  describe("press guards", () => {
    it("a press within 16px of the viewport left edge yields to the OS back-swipe", () => {
      const row = mountRow();

      slowDrag({ target: row[0], deltaX: 120, startX: 10 });

      expect(restoreTrashedURL).not.toHaveBeenCalled();
      expect(row.hasClass("swipe-dragging")).toBe(false);
    });

    it("a press just outside the left-edge band can drag", () => {
      const row = mountRow();

      slowDrag({ target: row[0], deltaX: 120, startX: 16 });

      expect(restoreTrashedURL).toHaveBeenCalledTimes(1);
    });

    it("a busy row (restore aria-disabled) never begins a drag", () => {
      const row = mountRow();
      row.find(".trashBtnRestore").attr("aria-disabled", "true");

      slowDrag({ target: row[0], deltaX: 120 });

      expect(restoreTrashedURL).not.toHaveBeenCalled();
    });

    it.each([".trashBtnRestore", ".trashBtnPurge", ".chip"])(
      "a press inside %s never begins a drag",
      (selector) => {
        const row = mountRow();

        slowDrag({
          target: row.find(selector)[0] as HTMLElement,
          deltaX: 120,
        });

        expect(restoreTrashedURL).not.toHaveBeenCalled();
        expect(row.hasClass("swipe-dragging")).toBe(false);
      },
    );

    it("a press inside the destination picker never begins a drag", () => {
      const row = mountRow();
      row
        .find(".trashRowContent")
        .append(
          '<div class="trashDestinationPicker"><span class="o"></span></div>',
        );

      slowDrag({
        target: row.find(".trashDestinationPicker .o")[0] as HTMLElement,
        deltaX: 120,
      });

      expect(restoreTrashedURL).not.toHaveBeenCalled();
    });

    it("an open picker on the row blocks a drag begun elsewhere on the row", () => {
      const row = mountRow();
      row
        .find(".trashRowContent")
        .append('<div class="trashDestinationPicker"></div>');

      slowDrag({ target: row.find(".t-title")[0] as HTMLElement, deltaX: 120 });

      expect(restoreTrashedURL).not.toHaveBeenCalled();
    });

    it("a row that is not laid out (zero reveal width) is treated as a tap", () => {
      const row = mountRow();
      stubRevealWidth({ row, width: 0 });

      slowDrag({ target: row[0], deltaX: 120 });

      expect(restoreTrashedURL).not.toHaveBeenCalled();
      expect(row.hasClass("swipe-dragging")).toBe(false);
    });
  });

  describe("drag state never outlives its context", () => {
    it.each([
      ["MOBILE_DECK_SWITCHED", AppEvents.MOBILE_DECK_SWITCHED],
      ["TRASH_CLOSED", AppEvents.TRASH_CLOSED],
    ] as const)("%s resets an in-flight drag", (_name, event) => {
      const row = mountRow();

      slowDrag({ target: row[0], deltaX: 60, release: false });
      expect(row.hasClass("swipe-dragging")).toBe(true);
      emit(event);

      expect(row.hasClass("swipe-dragging")).toBe(false);
      expect(contentTransform(row)).toBe("");
      dispatchPointer({
        target: row[0],
        type: "pointerup",
        clientX: START_X + 150,
      });
      expect(restoreTrashedURL).not.toHaveBeenCalled();
    });

    it("a row removed mid-drag leaves no swipe-dragging class and no live state", () => {
      const row = mountRow();
      const rowElement = row[0];

      slowDrag({ target: rowElement, deltaX: 60, release: false });
      row.remove();
      dispatchPointer({
        target: rowElement,
        type: "pointermove",
        clientX: START_X + 100,
      });

      expect(row.hasClass("swipe-dragging")).toBe(false);
      expect(contentTransform(row)).toBe("");

      // Live state is gone: a fresh row can start a drag immediately.
      const next = mountRow();
      slowDrag({ target: next[0], deltaX: 90 });
      expect(restoreTrashedURL).toHaveBeenCalledTimes(1);
    });

    it("a row removed before release does not restore on pointerup", () => {
      const row = mountRow();
      const rowElement = row[0];

      slowDrag({ target: rowElement, deltaX: 90, release: false });
      row.remove();
      dispatchPointer({
        target: rowElement,
        type: "pointerup",
        clientX: START_X + 90,
      });

      expect(restoreTrashedURL).not.toHaveBeenCalled();
      expect(row.hasClass("swipe-dragging")).toBe(false);
    });

    it("lostpointercapture resets the drag", () => {
      const row = mountRow();

      slowDrag({ target: row[0], deltaX: 60, release: false });
      dispatchPointer({
        target: row[0],
        type: "lostpointercapture",
        clientX: START_X + 60,
      });

      expect(row.hasClass("swipe-dragging")).toBe(false);
      expect(contentTransform(row)).toBe("");
    });
  });

  describe("restore outcome", () => {
    it("stays committed while the restore succeeds (the row is removed by the action)", async () => {
      const row = mountRow();

      slowDrag({ target: row[0], deltaX: 90 });
      await Promise.resolve();

      expect(row.hasClass("swipe-committed")).toBe(true);
    });

    it.each(["403 locked", "404 not in Trash", "network failure"])(
      "snaps the row back when the restore resolves false (%s)",
      async () => {
        vi.mocked(restoreTrashedURL).mockResolvedValue(false);
        const row = mountRow();

        slowDrag({ target: row[0], deltaX: 90 });
        expect(row.hasClass("swipe-committed")).toBe(true);
        await Promise.resolve();
        await Promise.resolve();

        expect(row.hasClass("swipe-committed")).toBe(false);
        expect(contentTransform(row)).toBe("");
      },
    );

    it("does not throw on snap-back when the row was detached meanwhile", async () => {
      let resolveRestore: (restored: boolean) => void = () => undefined;
      vi.mocked(restoreTrashedURL).mockImplementation(
        () =>
          new Promise<boolean>((resolve) => {
            resolveRestore = resolve;
          }),
      );
      const row = mountRow();

      slowDrag({ target: row[0], deltaX: 90 });
      row.remove();
      resolveRestore(false);
      await Promise.resolve();
      await Promise.resolve();

      expect(restoreTrashedURL).toHaveBeenCalledTimes(1);
      // The detached row is left untouched rather than snapped back.
      expect(row.hasClass("swipe-committed")).toBe(true);
    });

    it("a second gesture with a restore in flight issues no second request", () => {
      vi.mocked(restoreTrashedURL).mockImplementation(() => {
        // The real action disables the row's buttons synchronously.
        $(".trashBtnRestore").attr("aria-disabled", "true");
        return new Promise<boolean>(() => undefined);
      });
      const row = mountRow();

      slowDrag({ target: row[0], deltaX: 90 });
      slowDrag({ target: row[0], deltaX: 90 });

      expect(restoreTrashedURL).toHaveBeenCalledTimes(1);
    });
  });

  describe("trailing click suppression", () => {
    it("is armed by a committed swipe and consumed once", () => {
      const row = mountRow();

      slowDrag({ target: row[0], deltaX: 90 });

      expect(consumeTrashClickSuppression()).toBe(true);
      expect(consumeTrashClickSuppression()).toBe(false);
    });

    it("is not armed by a snapped-back drag", () => {
      const row = mountRow();

      slowDrag({ target: row[0], deltaX: 20 });

      expect(consumeTrashClickSuppression()).toBe(false);
    });

    it("is cleared by the next pointerdown in #TrashPanel", () => {
      const row = mountRow();
      slowDrag({ target: row[0], deltaX: 90 });

      dispatchPointer({
        target: $("#listTrashURLs")[0],
        type: "pointerdown",
        clientX: 50,
      });

      expect(consumeTrashClickSuppression()).toBe(false);
    });

    it("is cleared by any keydown in #TrashPanel", () => {
      const row = mountRow();
      slowDrag({ target: row[0], deltaX: 90 });

      row
        .find(".trashBtnRestore")[0]
        .dispatchEvent(
          new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
        );

      expect(consumeTrashClickSuppression()).toBe(false);
    });

    it("is not cleared by a keydown outside #TrashPanel", () => {
      const row = mountRow();
      slowDrag({ target: row[0], deltaX: 90 });

      $("#outside")[0].dispatchEvent(
        new KeyboardEvent("keydown", { key: "a", bubbles: true }),
      );

      expect(consumeTrashClickSuppression()).toBe(true);
    });

    it("expires on its own ~350ms after the committing pointerup", () => {
      vi.useFakeTimers();
      const row = mountRow();
      slowDragWithFakeClock({ target: row[0] });

      vi.advanceTimersByTime(350);

      expect(consumeTrashClickSuppression()).toBe(false);
    });

    it("is still armed before the timer fires", () => {
      vi.useFakeTimers();
      const row = mountRow();
      slowDragWithFakeClock({ target: row[0] });

      vi.advanceTimersByTime(200);

      expect(consumeTrashClickSuppression()).toBe(true);
    });
  });
});

/** Distance-committed swipe that needs no real elapsed time (fake-timer safe). */
function slowDragWithFakeClock({ target }: { target: HTMLElement }): void {
  dispatchPointer({ target, type: "pointerdown", clientX: START_X });
  dispatchPointer({ target, type: "pointermove", clientX: START_X + 90 });
  dispatchPointer({ target, type: "pointerup", clientX: START_X + 90 });
}
