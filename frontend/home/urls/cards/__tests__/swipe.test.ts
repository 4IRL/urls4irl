import {
  bindURLRowSwipeGesture,
  triggerURLSwipeNudgeIfEligible,
  _consumeSwipeClickSuppression,
  _resetURLSwipeGestureForTests,
} from "../swipe.js";
import { deleteURLShowModal } from "../delete.js";
import { isMobile, isCoarsePointer } from "../../../mobile.js";

vi.mock("../delete.js", () => ({ deleteURLShowModal: vi.fn() }));
vi.mock("../../../mobile.js", () => ({
  isMobile: vi.fn(() => true),
  isCoarsePointer: vi.fn(() => true),
}));

const $ = window.jQuery;

const UTUB_URL_ID = 42;
const UTUB_ID = 7;
// 84px mirrors the --url-swipe-reveal-width fallback in styles/home/urls.css;
// 35% of it (~29.4px) is the distance-commit threshold.
const REVEAL_WIDTH_PX = 84;
const NUDGE_SESSION_STORAGE_KEY = "u4i:urlSwipeNudgeShown";

const SWIPE_IGNORE_SELECTORS = [
  ".tagBadge",
  ".urlOptions",
  ".urlTagCombobox",
  ".urlTitleBtnUpdate",
  ".urlStringBtnUpdate",
  ".updateUrlTitleWrap",
  ".updateUrlStringWrap",
  ".goToUrlIcon",
];

const URL_ROW_HTML = `
  <div class="urlRow" utuburlid="${UTUB_URL_ID}">
    <div class="urlRowSwipeReveal"></div>
    <div class="urlRowContent">
      <span class="tagBadge"></span>
      <div class="urlOptions"></div>
      <div class="urlTagCombobox"></div>
      <button class="urlTitleBtnUpdate"></button>
      <button class="urlStringBtnUpdate"></button>
      <div class="updateUrlTitleWrap"></div>
      <div class="updateUrlStringWrap"></div>
      <span class="goToUrlIcon"></span>
    </div>
  </div>
`;

function stubRevealWidth({ row, width }: { row: JQuery; width: number }): void {
  const revealElement = row.find(".urlRowSwipeReveal")[0] as HTMLElement;
  revealElement.getBoundingClientRect = (): DOMRect =>
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

// Builds and attaches a `.urlRow` fixture, stubs the reveal panel's measured
// width (happy-dom returns a zero rect by default), and binds the gesture —
// mirroring how createURLBlock() wires bindURLRowSwipeGesture in production.
function mountURLRow(): JQuery {
  const row = $(URL_ROW_HTML);
  $(document.body).append(row);
  stubRevealWidth({ row, width: REVEAL_WIDTH_PX });
  bindURLRowSwipeGesture({
    urlRow: row,
    utubUrlID: UTUB_URL_ID,
    utubID: UTUB_ID,
  });
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
  type: "pointerdown" | "pointermove" | "pointerup" | "pointercancel";
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

// Mirrors splash/scroll-reveal.test.ts's matchMedia-mocking convention.
function setReducedMotion({ reduce }: { reduce: boolean }): void {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: reduce,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

describe("swipe gesture", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    vi.clearAllMocks();
    _resetURLSwipeGestureForTests();
    sessionStorage.removeItem(NUDGE_SESSION_STORAGE_KEY);
    vi.mocked(isMobile).mockReturnValue(true);
    vi.mocked(isCoarsePointer).mockReturnValue(true);
  });

  it("a tap (pointerdown + pointerup with no move) does not call deleteURLShowModal or add drag classes", () => {
    const row = mountURLRow();
    const rowElement = row[0];

    dispatchPointer({ target: rowElement, type: "pointerdown", clientX: 100 });
    dispatchPointer({ target: rowElement, type: "pointerup", clientX: 100 });

    expect(deleteURLShowModal).not.toHaveBeenCalled();
    expect(row.hasClass("swipe-dragging")).toBe(false);
    expect(row.hasClass("swipe-committed")).toBe(false);
  });

  it("a drag past the commit threshold calls deleteURLShowModal once with (utubUrlID, urlRow, utubID) and marks the row swipe-committed", () => {
    vi.useFakeTimers();
    try {
      const row = mountURLRow();
      const rowElement = row[0];

      // 40px left of 84px reveal width => fraction ~0.476, past the 0.35
      // distance-commit threshold regardless of velocity.
      dispatchPointer({
        target: rowElement,
        type: "pointerdown",
        clientX: 100,
      });
      dispatchPointer({ target: rowElement, type: "pointermove", clientX: 60 });
      dispatchPointer({ target: rowElement, type: "pointerup", clientX: 60 });

      expect(deleteURLShowModal).toHaveBeenCalledTimes(1);
      const [calledUtubUrlID, calledUrlRow, calledUtubID] =
        vi.mocked(deleteURLShowModal).mock.calls[0];
      expect(calledUtubUrlID).toBe(UTUB_URL_ID);
      expect(calledUrlRow).toBe(row);
      expect(calledUtubID).toBe(UTUB_ID);
      expect(row.hasClass("swipe-committed")).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  it("a drag past the commit threshold arms swipe-click suppression, and consuming it is one-shot", () => {
    vi.useFakeTimers();
    try {
      const row = mountURLRow();
      const rowElement = row[0];

      dispatchPointer({
        target: rowElement,
        type: "pointerdown",
        clientX: 100,
      });
      dispatchPointer({ target: rowElement, type: "pointermove", clientX: 60 });
      dispatchPointer({ target: rowElement, type: "pointerup", clientX: 60 });

      expect(_consumeSwipeClickSuppression()).toBe(true);
      expect(_consumeSwipeClickSuppression()).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });

  it("a drag below the commit threshold does not call deleteURLShowModal and removes swipe-dragging on release (snap-back)", () => {
    // Fake timers freeze performance.now() so velocity sampling is
    // deterministic (same-tick events => dt 0 => velocity stays 0), isolating
    // the distance-only threshold check.
    vi.useFakeTimers();
    try {
      const row = mountURLRow();
      const rowElement = row[0];

      // 15px left of 84px reveal width => fraction ~0.179, below the 0.35
      // distance-commit threshold.
      dispatchPointer({
        target: rowElement,
        type: "pointerdown",
        clientX: 100,
      });
      dispatchPointer({ target: rowElement, type: "pointermove", clientX: 85 });
      dispatchPointer({ target: rowElement, type: "pointerup", clientX: 85 });

      expect(deleteURLShowModal).not.toHaveBeenCalled();
      expect(row.hasClass("swipe-dragging")).toBe(false);
      expect(row.hasClass("swipe-committed")).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });

  it("a rightward drag exceeding the threshold distance does not call deleteURLShowModal since only leftward movement can commit", () => {
    vi.useFakeTimers();
    try {
      const row = mountURLRow();
      const rowElement = row[0];

      // 40px right of the press origin => |deltaX| / 84 ~= 0.476, past the
      // 0.35 distance-commit threshold in magnitude, but a net-rightward
      // release must never commit since only the leftward branch of
      // draggedFraction is nonzero.
      dispatchPointer({
        target: rowElement,
        type: "pointerdown",
        clientX: 100,
      });
      dispatchPointer({
        target: rowElement,
        type: "pointermove",
        clientX: 140,
      });
      dispatchPointer({ target: rowElement, type: "pointerup", clientX: 140 });

      expect(deleteURLShowModal).not.toHaveBeenCalled();
      expect(row.hasClass("swipe-committed")).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });

  it("a primarily-vertical drag locks to native scroll: no transform is applied and swipe-dragging is never added", () => {
    const row = mountURLRow();
    const rowElement = row[0];

    // deltaY (60px) dominates deltaX (20px), so the vertical-lock ratio
    // check (|deltaX| <= 1.5 * |deltaY|) locks the gesture to native scroll
    // instead of treating it as a horizontal swipe.
    dispatchPointer({
      target: rowElement,
      type: "pointerdown",
      clientX: 100,
      clientY: 100,
    });
    dispatchPointer({
      target: rowElement,
      type: "pointermove",
      clientX: 120,
      clientY: 160,
    });

    expect((row.find(".urlRowContent")[0] as HTMLElement).style.transform).toBe(
      "",
    );
    expect(row.hasClass("swipe-dragging")).toBe(false);
    expect(deleteURLShowModal).not.toHaveBeenCalled();
  });

  it("pointercancel mid-drag resets state without calling deleteURLShowModal", () => {
    const row = mountURLRow();
    const rowElement = row[0];

    dispatchPointer({ target: rowElement, type: "pointerdown", clientX: 100 });
    dispatchPointer({ target: rowElement, type: "pointermove", clientX: 50 });
    expect(row.hasClass("swipe-dragging")).toBe(true);

    dispatchPointer({ target: rowElement, type: "pointercancel", clientX: 50 });

    expect(deleteURLShowModal).not.toHaveBeenCalled();
    expect(row.hasClass("swipe-dragging")).toBe(false);
    expect(row.hasClass("swipe-committed")).toBe(false);
    expect((row.find(".urlRowContent")[0] as HTMLElement).style.transform).toBe(
      "",
    );
  });

  it("a second pointerdown with a different pointerId mid-drag never starts a second drag, and stray move/release events for it are ignored", () => {
    vi.useFakeTimers();
    try {
      const row = mountURLRow();
      const rowElement = row[0];

      dispatchPointer({
        target: rowElement,
        type: "pointerdown",
        clientX: 100,
        pointerId: 1,
      });
      dispatchPointer({
        target: rowElement,
        type: "pointermove",
        clientX: 70,
        pointerId: 1,
      });
      expect(row.hasClass("swipe-dragging")).toBe(true);

      // A second finger touches down mid-drag on the same row. _dragState is
      // already owned by pointerId 1, so _beginDrag's `_dragState !== null`
      // guard rejects it outright — no second drag begins.
      dispatchPointer({
        target: rowElement,
        type: "pointerdown",
        clientX: 100,
        pointerId: 2,
      });

      // Move/up/cancel events "from" the rejected second pointer must be
      // ignored too (the `event.pointerId !== _dragState.pointerId` guards
      // in _onDragMove/_endDrag/_cancelDrag), so none of them can perturb or
      // end the first drag.
      dispatchPointer({
        target: rowElement,
        type: "pointermove",
        clientX: 10,
        pointerId: 2,
      });
      dispatchPointer({
        target: rowElement,
        type: "pointerup",
        clientX: 10,
        pointerId: 2,
      });
      dispatchPointer({
        target: rowElement,
        type: "pointercancel",
        clientX: 10,
        pointerId: 2,
      });

      expect(deleteURLShowModal).not.toHaveBeenCalled();
      expect(
        (row.find(".urlRowContent")[0] as HTMLElement).style.transform,
      ).toBe("translateX(-30px)");
      expect(row.hasClass("swipe-dragging")).toBe(true);

      // The original drag (pointerId 1) completes normally past the commit
      // threshold, proving its state was never touched by the second pointer.
      dispatchPointer({
        target: rowElement,
        type: "pointerup",
        clientX: 60,
        pointerId: 1,
      });

      expect(deleteURLShowModal).toHaveBeenCalledTimes(1);
      expect(row.hasClass("swipe-committed")).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  it.each(SWIPE_IGNORE_SELECTORS)(
    "ignores a pointerdown whose target is inside %s (no drag state, no transform on a subsequent move)",
    (ignoredSelector) => {
      const row = mountURLRow();
      const ignoredTargetJQuery = row.find(ignoredSelector);
      expect(ignoredTargetJQuery.length).toBe(1);
      const ignoredTarget = ignoredTargetJQuery[0] as HTMLElement;

      dispatchPointer({
        target: ignoredTarget,
        type: "pointerdown",
        clientX: 100,
      });
      dispatchPointer({
        target: ignoredTarget,
        type: "pointermove",
        clientX: 20,
      });

      expect(
        (row.find(".urlRowContent")[0] as HTMLElement).style.transform,
      ).toBe("");
      expect(row.hasClass("swipe-dragging")).toBe(false);
      expect(deleteURLShowModal).not.toHaveBeenCalled();
    },
  );

  it("ignores a pointerType: 'mouse' pointerdown (desktop/mouse users unaffected)", () => {
    const row = mountURLRow();
    const rowElement = row[0];

    dispatchPointer({
      target: rowElement,
      type: "pointerdown",
      clientX: 100,
      pointerType: "mouse",
    });
    dispatchPointer({
      target: rowElement,
      type: "pointermove",
      clientX: 60,
      pointerType: "mouse",
    });
    dispatchPointer({
      target: rowElement,
      type: "pointerup",
      clientX: 60,
      pointerType: "mouse",
    });

    expect(deleteURLShowModal).not.toHaveBeenCalled();
    expect(row.hasClass("swipe-dragging")).toBe(false);
  });

  it("a zero-width reveal panel (not yet laid out) never enters drag state: no transform is applied and swipe-dragging is never added", () => {
    const row = mountURLRow();
    stubRevealWidth({ row, width: 0 });
    const rowElement = row[0];

    dispatchPointer({ target: rowElement, type: "pointerdown", clientX: 100 });
    dispatchPointer({ target: rowElement, type: "pointermove", clientX: 60 });

    expect((row.find(".urlRowContent")[0] as HTMLElement).style.transform).toBe(
      "",
    );
    expect(row.hasClass("swipe-dragging")).toBe(false);
    expect(deleteURLShowModal).not.toHaveBeenCalled();
  });

  describe("swipe-focus-return suppresses the visual focus ring on programmatic focus-return", () => {
    // #confirmModal must exist before the commit's pointerup fires, since the
    // modal-hidden listener is bound (not delegated) to the element(s)
    // matched by $(CONFIRM_MODAL_SELECTOR) at that moment.
    function mountConfirmModal(): JQuery {
      const modal = $('<div id="confirmModal"></div>');
      $(document.body).append(modal);
      return modal;
    }

    function commitSwipe(rowElement: HTMLElement): void {
      dispatchPointer({
        target: rowElement,
        type: "pointerdown",
        clientX: 100,
      });
      dispatchPointer({ target: rowElement, type: "pointermove", clientX: 60 });
      dispatchPointer({ target: rowElement, type: "pointerup", clientX: 60 });
    }

    it("adds swipe-focus-return to the row immediately after a committed swipe, before the modal-hidden event fires", () => {
      mountConfirmModal();
      const row = mountURLRow();

      commitSwipe(row[0]);

      expect(deleteURLShowModal).toHaveBeenCalledTimes(1);
      expect(row.hasClass("swipe-focus-return")).toBe(true);
    });

    it("keeps swipe-focus-return present after the modal-hidden event fires and focus is re-triggered", () => {
      const modal = mountConfirmModal();
      const row = mountURLRow();

      commitSwipe(row[0]);
      modal.trigger("hidden.bs.modal");

      expect(row.hasClass("swipe-focus-return")).toBe(true);
    });

    it("removes swipe-focus-return once the row is genuinely blurred", () => {
      mountConfirmModal();
      const row = mountURLRow();

      commitSwipe(row[0]);
      expect(row.hasClass("swipe-focus-return")).toBe(true);

      row.trigger("blur");

      expect(row.hasClass("swipe-focus-return")).toBe(false);
    });

    it("re-arms the blur listener on modal-hidden so a second blur removes swipe-focus-return again", () => {
      const modal = mountConfirmModal();
      const row = mountURLRow();

      commitSwipe(row[0]);
      row.trigger("blur");
      expect(row.hasClass("swipe-focus-return")).toBe(false);

      modal.trigger("hidden.bs.modal");
      expect(row.hasClass("swipe-focus-return")).toBe(true);

      row.trigger("blur");
      expect(row.hasClass("swipe-focus-return")).toBe(false);
    });
  });

  describe("triggerURLSwipeNudgeIfEligible", () => {
    it("on first eligible call, peeks .urlRowContent, adds swipe-nudge-peeking, and sets the session flag", () => {
      vi.useFakeTimers();
      try {
        setReducedMotion({ reduce: false });
        const row = mountURLRow();

        expect(sessionStorage.getItem(NUDGE_SESSION_STORAGE_KEY)).toBeNull();

        triggerURLSwipeNudgeIfEligible({ urlRow: row });

        expect(
          (row.find(".urlRowContent")[0] as HTMLElement).style.transform,
        ).toBe("translateX(-12px)");
        expect(row.hasClass("swipe-nudge-peeking")).toBe(true);
        expect(sessionStorage.getItem(NUDGE_SESSION_STORAGE_KEY)).toBe("true");
      } finally {
        vi.useRealTimers();
      }
    });

    it("removes swipe-nudge-peeking once the peek duration elapses", () => {
      vi.useFakeTimers();
      try {
        setReducedMotion({ reduce: false });
        const row = mountURLRow();

        triggerURLSwipeNudgeIfEligible({ urlRow: row });
        expect(row.hasClass("swipe-nudge-peeking")).toBe(true);

        vi.advanceTimersByTime(400);

        expect(row.hasClass("swipe-nudge-peeking")).toBe(false);
        expect(
          (row.find(".urlRowContent")[0] as HTMLElement).style.transform,
        ).toBe("");
      } finally {
        vi.useRealTimers();
      }
    });

    it("does not retrigger the peek animation once the session flag is already set", () => {
      setReducedMotion({ reduce: false });
      const row = mountURLRow();
      sessionStorage.setItem(NUDGE_SESSION_STORAGE_KEY, "true");

      triggerURLSwipeNudgeIfEligible({ urlRow: row });

      expect(
        (row.find(".urlRowContent")[0] as HTMLElement).style.transform,
      ).toBe("");
    });

    it("skips the peek animation and swipe-nudge-peeking class under prefers-reduced-motion but still sets the session flag", () => {
      setReducedMotion({ reduce: true });
      const row = mountURLRow();

      triggerURLSwipeNudgeIfEligible({ urlRow: row });

      expect(
        (row.find(".urlRowContent")[0] as HTMLElement).style.transform,
      ).toBe("");
      expect(row.hasClass("swipe-nudge-peeking")).toBe(false);
      expect(sessionStorage.getItem(NUDGE_SESSION_STORAGE_KEY)).toBe("true");
    });

    it("does not peek or record the session flag when isMobile is false", () => {
      setReducedMotion({ reduce: false });

      vi.mocked(isMobile).mockReturnValue(false);
      const nonMobileRow = mountURLRow();
      triggerURLSwipeNudgeIfEligible({ urlRow: nonMobileRow });
      expect(
        (nonMobileRow.find(".urlRowContent")[0] as HTMLElement).style.transform,
      ).toBe("");
      expect(nonMobileRow.hasClass("swipe-nudge-peeking")).toBe(false);
      expect(sessionStorage.getItem(NUDGE_SESSION_STORAGE_KEY)).toBeNull();
    });

    it("does not peek or record the session flag when isCoarsePointer is false", () => {
      setReducedMotion({ reduce: false });

      vi.mocked(isCoarsePointer).mockReturnValue(false);
      const finePointerRow = mountURLRow();
      triggerURLSwipeNudgeIfEligible({ urlRow: finePointerRow });
      expect(
        (finePointerRow.find(".urlRowContent")[0] as HTMLElement).style
          .transform,
      ).toBe("");
      expect(finePointerRow.hasClass("swipe-nudge-peeking")).toBe(false);
      expect(sessionStorage.getItem(NUDGE_SESSION_STORAGE_KEY)).toBeNull();
    });

    it("returns early when the row has no .urlRowSwipeReveal child", () => {
      setReducedMotion({ reduce: false });
      const row = $(
        `<div class="urlRow" utuburlid="${UTUB_URL_ID}"><div class="urlRowContent"></div></div>`,
      );
      $(document.body).append(row);

      triggerURLSwipeNudgeIfEligible({ urlRow: row });

      expect(
        (row.find(".urlRowContent")[0] as HTMLElement).style.transform,
      ).toBe("");
      expect(row.hasClass("swipe-nudge-peeking")).toBe(false);
      expect(sessionStorage.getItem(NUDGE_SESSION_STORAGE_KEY)).toBeNull();
    });

    it("returns early when the row is below the fold (top >= window.innerHeight)", () => {
      setReducedMotion({ reduce: false });
      const row = mountURLRow();
      const rowElement = row[0] as HTMLElement;
      rowElement.getBoundingClientRect = (): DOMRect =>
        ({
          width: REVEAL_WIDTH_PX,
          height: 44,
          top: window.innerHeight,
          bottom: window.innerHeight + 44,
          left: 0,
          right: REVEAL_WIDTH_PX,
          x: 0,
          y: window.innerHeight,
          toJSON: () => ({}),
        }) as DOMRect;

      triggerURLSwipeNudgeIfEligible({ urlRow: row });

      expect(
        (row.find(".urlRowContent")[0] as HTMLElement).style.transform,
      ).toBe("");
      expect(row.hasClass("swipe-nudge-peeking")).toBe(false);
      expect(sessionStorage.getItem(NUDGE_SESSION_STORAGE_KEY)).toBeNull();
    });
  });
});
