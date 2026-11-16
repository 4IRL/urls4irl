import {
  setDisabledReason,
  showDisabledReasonNote,
} from "../disabled-reason.js";

const REASON = "Only the owner and co-owners can create tags in this UTub.";

function stubPointers({
  coarse,
  fine,
}: {
  coarse: boolean;
  fine: boolean;
}): void {
  window.matchMedia = vi.fn((query: string) => ({
    matches:
      (query === "(any-pointer: coarse)" && coarse) ||
      (query === "(any-pointer: fine)" && fine),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

function button(): HTMLElement {
  return document.getElementById("btn") as HTMLElement;
}

function noteOf(): HTMLElement | null {
  return document.querySelector(".disabledReasonNote");
}

describe("setDisabledReason", () => {
  let clicked = vi.fn<() => void>();

  beforeEach(() => {
    vi.useFakeTimers();
    document.body.innerHTML = `<div id="wrap"><button id="btn" tabindex="0">Add</button></div>`;
    clicked = vi.fn<() => void>();
    button().addEventListener("click", () => clicked());
    stubPointers({ coarse: false, fine: true });
  });

  afterEach(() => {
    setDisabledReason({ element: button(), reason: null });
    vi.useRealTimers();
  });

  it("marks the control aria-disabled and keeps it focusable", () => {
    setDisabledReason({ element: button(), reason: REASON });
    expect(button().getAttribute("aria-disabled")).toBe("true");
    expect(button().getAttribute("tabindex")).toBe("0");
    expect(button().hasAttribute("disabled")).toBe(false);
  });

  it("suppresses click and Enter/Space before existing handlers run", () => {
    setDisabledReason({ element: button(), reason: REASON });
    button().click();
    const enter = new KeyboardEvent("keydown", {
      key: "Enter",
      bubbles: true,
      cancelable: true,
    });
    button().dispatchEvent(enter);
    const space = new KeyboardEvent("keyup", {
      key: " ",
      bubbles: true,
      cancelable: true,
    });
    button().dispatchEvent(space);
    expect(clicked).not.toHaveBeenCalled();
    expect(enter.defaultPrevented).toBe(true);
    expect(space.defaultPrevented).toBe(true);
  });

  it("fine pointer only: tooltip surface, empty collapsed note, no glyph", () => {
    setDisabledReason({ element: button(), reason: REASON });
    const tooltip = document.querySelector('[role="tooltip"]') as HTMLElement;
    expect(tooltip.textContent).toBe(REASON);
    expect(button().getAttribute("aria-describedby")).toBe(tooltip.id);
    expect(document.querySelector(".disabledReasonLock")).toBeNull();
    const note = noteOf() as HTMLElement;
    expect(note.getAttribute("role")).toBe("status");
    expect(note.textContent).toBe("");

    button().click();
    expect(note.textContent).toBe("");
  });

  it("shows the tooltip on hover and hides it on mouseleave, blur and Escape", () => {
    setDisabledReason({ element: button(), reason: REASON });
    const tooltip = document.querySelector('[role="tooltip"]') as HTMLElement;
    const visible = (): boolean =>
      tooltip.classList.contains("disabledReasonTooltipVisible");

    button().dispatchEvent(new Event("mouseenter"));
    expect(visible()).toBe(true);
    button().dispatchEvent(new Event("mouseleave"));
    expect(visible()).toBe(false);

    button().dispatchEvent(new Event("mouseenter"));
    button().dispatchEvent(new Event("blur"));
    expect(visible()).toBe(false);

    button().dispatchEvent(new Event("mouseenter"));
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    expect(visible()).toBe(false);
  });

  it("Escape is not stopped, and an owning layer still receives it", () => {
    setDisabledReason({ element: button(), reason: REASON });
    const owner = vi.fn();
    document.addEventListener("keydown", owner);
    button().dispatchEvent(new Event("mouseenter"));
    const escape = new KeyboardEvent("keydown", {
      key: "Escape",
      bubbles: true,
      cancelable: true,
    });
    button().dispatchEvent(escape);
    document.removeEventListener("keydown", owner);
    expect(owner).toHaveBeenCalledTimes(1);
    expect(escape.defaultPrevented).toBe(false);
  });

  it("shows the tooltip on keyboard focus", () => {
    setDisabledReason({ element: button(), reason: REASON });
    const tooltip = document.querySelector('[role="tooltip"]') as HTMLElement;
    button().focus();
    expect(tooltip.classList.contains("disabledReasonTooltipVisible")).toBe(
      true,
    );
    button().blur();
    expect(tooltip.classList.contains("disabledReasonTooltipVisible")).toBe(
      false,
    );
  });

  it("coarse pointer only: lock glyph and tap note, no tooltip", () => {
    stubPointers({ coarse: true, fine: false });
    setDisabledReason({ element: button(), reason: REASON });
    expect(document.querySelector(".disabledReasonLock")).not.toBeNull();
    expect(document.querySelector('[role="tooltip"]')).toBeNull();
    const note = noteOf() as HTMLElement;
    expect(note.textContent).toBe("");

    button().click();
    expect(note.textContent).toBe(REASON);
    expect(clicked).not.toHaveBeenCalled();
  });

  it("hybrid device: both the touch surface and the tooltip", () => {
    stubPointers({ coarse: true, fine: true });
    setDisabledReason({ element: button(), reason: REASON });
    expect(document.querySelector(".disabledReasonLock")).not.toBeNull();
    expect(document.querySelector('[role="tooltip"]')).not.toBeNull();
    button().click();
    expect((noteOf() as HTMLElement).textContent).toBe(REASON);
  });

  it("clears the note after 4s and on an outside tap", () => {
    stubPointers({ coarse: true, fine: false });
    setDisabledReason({ element: button(), reason: REASON });
    button().click();
    vi.advanceTimersByTime(3999);
    expect((noteOf() as HTMLElement).textContent).toBe(REASON);
    vi.advanceTimersByTime(1);
    expect((noteOf() as HTMLElement).textContent).toBe("");

    button().click();
    document.body.dispatchEvent(new Event("pointerdown", { bubbles: true }));
    expect((noteOf() as HTMLElement).textContent).toBe("");
  });

  it("keeps a single note: a second control's note replaces the first", () => {
    stubPointers({ coarse: true, fine: false });
    document
      .getElementById("wrap")!
      .insertAdjacentHTML("beforeend", `<button id="other">Other</button>`);
    const other = document.getElementById("other") as HTMLElement;
    setDisabledReason({ element: button(), reason: REASON });
    setDisabledReason({ element: other, reason: "Other reason" });
    button().click();
    other.click();
    const notes = Array.from(document.querySelectorAll(".disabledReasonNote"));
    expect(notes.map((note) => note.textContent)).toEqual(["", "Other reason"]);
    setDisabledReason({ element: other, reason: null });
  });

  it("is idempotent for a repeat call with the same reason", () => {
    setDisabledReason({ element: button(), reason: REASON });
    setDisabledReason({ element: button(), reason: REASON });
    expect(document.querySelectorAll(".disabledReasonNote")).toHaveLength(1);
    expect(document.querySelectorAll('[role="tooltip"]')).toHaveLength(1);
    button().click();
    expect(clicked).not.toHaveBeenCalled();
  });

  it("restores the original attributes and listeners when the reason clears", () => {
    stubPointers({ coarse: true, fine: true });
    button().setAttribute("aria-describedby", "orig");
    button().setAttribute("aria-disabled", "false");
    setDisabledReason({ element: button(), reason: REASON });
    setDisabledReason({ element: button(), reason: null });

    expect(button().getAttribute("aria-disabled")).toBe("false");
    expect(button().getAttribute("aria-describedby")).toBe("orig");
    expect(document.querySelector(".disabledReasonNote")).toBeNull();
    expect(document.querySelector(".disabledReasonLock")).toBeNull();
    expect(document.querySelector('[role="tooltip"]')).toBeNull();
    expect(button().classList.contains("disabledReasonControl")).toBe(false);
    button().click();
    expect(clicked).toHaveBeenCalledTimes(1);
  });

  it("removes aria-disabled entirely when it was absent before", () => {
    setDisabledReason({ element: button(), reason: REASON });
    setDisabledReason({ element: button(), reason: null });
    expect(button().hasAttribute("aria-disabled")).toBe(false);
    expect(button().hasAttribute("aria-describedby")).toBe(false);
  });

  it("does not clobber a collapse-disable tabindex in either order", () => {
    setDisabledReason({ element: button(), reason: REASON });
    button().setAttribute("tabindex", "-1");
    setDisabledReason({ element: button(), reason: null });
    expect(button().getAttribute("tabindex")).toBe("-1");

    button().setAttribute("tabindex", "-1");
    setDisabledReason({ element: button(), reason: REASON });
    button().setAttribute("tabindex", "0");
    expect(button().getAttribute("aria-disabled")).toBe("true");
    setDisabledReason({ element: button(), reason: null });
    expect(button().getAttribute("tabindex")).toBe("0");
  });
});

describe("showDisabledReasonNote", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    document.body.innerHTML = `<div><button id="btn">Add</button></div>`;
    stubPointers({ coarse: false, fine: true });
  });

  afterEach(() => {
    setDisabledReason({ element: button(), reason: null });
    vi.useRealTimers();
  });

  it("sets the text on a blocked fine-pointer control, replaces it, clears after 4s", () => {
    setDisabledReason({ element: button(), reason: REASON });
    showDisabledReasonNote({ element: button(), reason: "first" });
    expect((noteOf() as HTMLElement).textContent).toBe("first");
    showDisabledReasonNote({ element: button(), reason: "second" });
    expect((noteOf() as HTMLElement).textContent).toBe("second");
    vi.advanceTimersByTime(4000);
    expect((noteOf() as HTMLElement).textContent).toBe("");
  });

  it("is a no-op on an unblocked element", () => {
    showDisabledReasonNote({ element: button(), reason: "x" });
    expect(noteOf()).toBeNull();
  });
});
