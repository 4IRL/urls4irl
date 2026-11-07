import type {
  RovingListbox,
  RovingListboxConfig,
} from "../../../lib/roving-listbox.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";
import type { UtubSummaryItem } from "../../../types/utub.js";
import {
  PATCH_TIMEOUT_MS,
  handleActiveUTubGone,
  patchUtubPin,
} from "../../panel-settings/client.js";
import type { PinSaveResult } from "../../panel-settings/client.js";
import { createSaveQueue } from "../../panel-settings/queue.js";
import type { SaveQueue } from "../../panel-settings/queue.js";
import {
  _resetRegistryForTests,
  getSections,
} from "../../panel-settings/registry.js";
import type {
  PanelSection,
  QueueSink,
  SectionContext,
} from "../../panel-settings/types.js";
import { registerUtubPinsSection } from "../pins-section.js";
import { purgeUTubLocally } from "../remove-local.js";
import { setUTubRowPinned } from "../sort.js";
import { getAllUTubs } from "../utils.js";

vi.mock("../../panel-settings/client.js", () => ({
  PATCH_TIMEOUT_MS: 10000,
  handleActiveUTubGone: vi.fn(),
  patchUtubPin: vi.fn(),
}));
vi.mock("../sort.js", () => ({ setUTubRowPinned: vi.fn() }));
vi.mock("../remove-local.js", () => ({ purgeUTubLocally: vi.fn() }));
vi.mock("../utils.js", () => ({ getAllUTubs: vi.fn() }));
const recordedRoving = vi.hoisted((): RovingListbox[] => []);

// Real roving listbox, with detach recorded so cleanup ownership is observable.
vi.mock("../../../lib/roving-listbox.js", async () => {
  const actual = await vi.importActual<
    typeof import("../../../lib/roving-listbox.js")
  >("../../../lib/roving-listbox.js");
  return {
    ...actual,
    createRovingListbox: (config: RovingListboxConfig) => {
      const instance = actual.createRovingListbox(config);
      const wrapped = {
        ...instance,
        detachKeyListeners: vi.fn(instance.detachKeyListeners),
      };
      recordedRoving.push(wrapped);
      return wrapped;
    },
  };
});

const INPUT = "utub-pins-input";

interface PendingSave {
  resolve(result: PinSaveResult): void;
}

function utub({
  id,
  name,
  isPinned,
}: {
  id: number;
  name: string;
  isPinned: boolean;
}): UtubSummaryItem {
  return { id, name, isPinned } as unknown as UtubSummaryItem;
}

function seed(utubs: UtubSummaryItem[]): void {
  setState({ utubs });
}

function input(): HTMLInputElement {
  return document.getElementById(INPUT) as HTMLInputElement;
}

function type(text: string): void {
  const field = input();
  field.value = text;
  field.dispatchEvent(new Event("input", { bubbles: true }));
}

function optionNames(): string[] {
  return Array.from(document.querySelectorAll(".utubPinsOption")).map(
    (option) => option.textContent ?? "",
  );
}

function removeButton(utubID: number): HTMLElement {
  return document.getElementById(`utub-pins-remove-${utubID}`)!;
}

async function settle(): Promise<void> {
  await vi.advanceTimersByTimeAsync(0);
}

function pressKey({
  target,
  key,
  eventType = "keydown",
  isComposing = false,
}: {
  target: Element;
  key: string;
  eventType?: "keydown" | "keyup";
  isComposing?: boolean;
}): void {
  target.dispatchEvent(
    new KeyboardEvent(eventType, { key, bubbles: true, isComposing }),
  );
}

function activeId(): string {
  return document.activeElement?.id ?? "";
}

function storeIds(): number[] {
  return getState().utubs.map((entry) => entry.id);
}

function seedPinned({
  pinnedCount,
  unpinned,
}: {
  pinnedCount: number;
  unpinned: string[];
}): void {
  const pinnedUtubs = Array.from({ length: pinnedCount }, (_unused, index) =>
    utub({ id: index + 1, name: `Pinned${index + 1}`, isPinned: true }),
  );
  const rest = unpinned.map((name, index) =>
    utub({ id: pinnedCount + index + 1, name, isPinned: false }),
  );
  seed([...pinnedUtubs, ...rest]);
}

describe("Pinned UTubs section", () => {
  let host: HTMLElement;
  let section: PanelSection;
  let unregister: () => void;
  let queue: SaveQueue;
  let sink: { [Key in keyof QueueSink]: ReturnType<typeof vi.fn> } & QueueSink;
  let pending: PendingSave[];
  let ctx: SectionContext;

  function renderSection(): void {
    host.innerHTML = "";
    section.render({ container: host, ctx });
  }

  // The section's render returns its disposer; the shared type allows void.
  function renderWithDisposer({
    container,
  }: {
    container: HTMLElement;
  }): () => void {
    return section.render({ container, ctx }) as () => void;
  }

  function lastNotice(): string | undefined {
    const savedCalls = sink.report.mock.calls
      .map(([args]) => args as { status: string; notice?: string })
      .filter((args) => args.status === "saved" || args.status === "error");
    return savedCalls[savedCalls.length - 1]?.notice;
  }

  beforeEach(() => {
    vi.useFakeTimers();
    _resetRegistryForTests();
    resetStore();
    vi.clearAllMocks();
    document.body.innerHTML = "";
    host = document.createElement("div");
    document.body.append(host);

    seed([
      utub({ id: 1, name: "Alpha", isPinned: true }),
      utub({ id: 2, name: "Beta", isPinned: false }),
      utub({ id: 3, name: "Gamma", isPinned: false }),
    ]);

    // Store-mutating stand-ins, as the real ones are: the section reads the
    // store after them, so an ordering regression shows up in the rendered DOM.
    vi.mocked(purgeUTubLocally).mockImplementation(({ utubID }) => {
      setState({
        utubs: getState().utubs.filter((entry) => entry.id !== utubID),
      });
    });
    vi.mocked(setUTubRowPinned).mockImplementation(
      ({ utubID, isPinned }: { utubID: number; isPinned: boolean }) => {
        setState({
          utubs: getState().utubs.map((entry) =>
            entry.id === utubID ? { ...entry, isPinned } : entry,
          ),
        });
      },
    );
    vi.mocked(getAllUTubs).mockReset();

    recordedRoving.length = 0;
    pending = [];
    vi.mocked(patchUtubPin).mockImplementation(
      () =>
        new Promise<PinSaveResult>((resolve) => {
          pending.push({ resolve });
        }),
    );

    unregister = registerUtubPinsSection();
    section = getSections("utubs").find((entry) => entry.id === "utubs-pins")!;

    sink = {
      report: vi.fn(({ status }: { status: string }) => {
        if (status === "error") renderSection();
      }),
      forceReadOnly: vi.fn(),
      announce: vi.fn(),
      resynced: vi.fn(),
      isForcedReadOnly: vi.fn(() => false),
    } as typeof sink;
    queue = createSaveQueue({ sink });
    ctx = {
      settings: null,
      canWrite: true,
      submit: ({ patch, debounce }) =>
        queue.enqueue({ section, patch, debounce }),
    };
    renderSection();
  });

  afterEach(() => {
    unregister();
    vi.useRealTimers();
    resetStore();
    document.body.innerHTML = "";
  });

  it("registers a global user section titled Pinned UTubs", () => {
    expect(section).toMatchObject({
      id: "utubs-pins",
      panel: "utubs",
      scope: "user",
      userKind: "global",
      title: "Pinned UTubs",
    });
  });

  it("renders the counter and one row per pinned UTub with a named remove button", () => {
    expect(host.querySelector(".utubPinsCounter")?.textContent).toBe("1 of 5");
    expect(host.querySelectorAll(".utubPinsItem")).toHaveLength(1);
    expect(removeButton(1).getAttribute("aria-label")).toBe("Unpin Alpha");
  });

  it("shows the empty hint when nothing is pinned", () => {
    seed([utub({ id: 2, name: "Beta", isPinned: false })]);
    renderSection();

    expect(host.textContent).toContain("No pinned UTubs yet.");
  });

  it("filters the picker to unpinned UTubs matching the text", () => {
    type("a");

    expect(optionNames()).toEqual(["Beta", "Gamma"]);
    type("gam");
    expect(optionNames()).toEqual(["Gamma"]);
  });

  it("shows the no-match status when nothing matches", () => {
    type("zzz");

    expect(optionNames()).toEqual([]);
    expect(host.querySelector(".utubPinsNoMatch")?.textContent).toBe(
      "No UTubs match.",
    );
  });

  it("tells the user there is nothing left to pin", () => {
    seed([utub({ id: 1, name: "Alpha", isPinned: true })]);
    renderSection();

    expect(host.textContent).toContain("No UTubs left to pin.");
  });

  it("disables the picker and shows the cap note at the cap", () => {
    seed(
      [1, 2, 3, 4, 5, 6].map((id) =>
        utub({ id, name: `U${id}`, isPinned: id <= 5 }),
      ),
    );
    renderSection();

    expect(input().getAttribute("aria-disabled")).toBe("true");
    expect(host.querySelector(".utubPinsCapNote")?.textContent).toBe(
      "You can pin up to 5 UTubs. Unpin one to pin another.",
    );
    type("U");
    expect(optionNames()).toEqual([]);
  });

  it("pins the first match on Enter and sends one immediate patch", async () => {
    type("beta");
    input().dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
    );
    await settle();

    expect(pending).toHaveLength(1);
    expect(patchUtubPin).toHaveBeenCalledWith({ utubID: 2, pinned: true });
  });

  it("drops a second activation while a write is in flight", async () => {
    removeButton(1).click();
    removeButton(1).click();
    await settle();

    expect(patchUtubPin).toHaveBeenCalledTimes(1);
    expect(removeButton(1).getAttribute("aria-disabled")).toBe("true");
  });

  it("applies an ok result: row flipped, notice announced, filter cleared", async () => {
    type("beta");
    input().dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
    );
    await settle();
    pending[0].resolve({ outcome: "ok", isPinned: true, pinnedCount: 2 });
    await settle();
    await vi.advanceTimersByTimeAsync(1);

    expect(setUTubRowPinned).toHaveBeenCalledWith({
      utubID: 2,
      isPinned: true,
    });
    expect(lastNotice()).toBe("Beta pinned. 2 of 5");
    expect(input().value).toBe("");
  });

  it("appends the cap note to the notice when the response reaches the cap", async () => {
    removeButton(1).click();
    await settle();
    pending[0].resolve({ outcome: "ok", isPinned: true, pinnedCount: 5 });
    await settle();

    expect(lastNotice()).toContain("You can pin up to 5 UTubs");
  });

  it("uses the shell's own error text for a plain failure and changes nothing", async () => {
    removeButton(1).click();
    await settle();
    pending[0].resolve({ outcome: "error" });
    await settle();
    await vi.advanceTimersByTimeAsync(1);

    expect(setUTubRowPinned).not.toHaveBeenCalled();
    expect(getAllUTubs).not.toHaveBeenCalled();
    expect(lastNotice()).toBeUndefined();
    expect(removeButton(1).getAttribute("aria-disabled")).toBe("false");
  });

  it("reseeds on a stale-tab cap, flipping differing pins", async () => {
    vi.mocked(getAllUTubs).mockResolvedValue({
      utubs: [
        { id: 1, isPinned: false },
        { id: 2, isPinned: true },
        { id: 3, isPinned: false },
      ],
    } as unknown as Awaited<ReturnType<typeof getAllUTubs>>);
    type("beta");
    input().dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
    );
    await settle();
    pending[0].resolve({ outcome: "cap" });
    await settle();

    expect(setUTubRowPinned).toHaveBeenCalledWith({
      utubID: 1,
      isPinned: false,
    });
    expect(setUTubRowPinned).toHaveBeenCalledWith({
      utubID: 2,
      isPinned: true,
    });
    expect(lastNotice()).toContain("You can pin up to 5 UTubs");
  });

  it("purges an absent UTub on gone and runs the removal contract only for the active one", async () => {
    seed([
      utub({ id: 1, name: "Alpha", isPinned: true }),
      utub({ id: 2, name: "Beta", isPinned: false }),
      utub({ id: 3, name: "Gamma", isPinned: true }),
    ]);
    renderSection();
    setState({ activeUTubID: 3 });
    vi.mocked(getAllUTubs).mockResolvedValue({
      utubs: [{ id: 1, isPinned: true }],
    } as unknown as Awaited<ReturnType<typeof getAllUTubs>>);
    type("beta");
    input().dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
    );
    await settle();
    pending[0].resolve({ outcome: "gone" });
    await settle();

    expect(purgeUTubLocally).toHaveBeenCalledWith({ utubID: 2 });
    expect(purgeUTubLocally).toHaveBeenCalledWith({ utubID: 3 });
    expect(handleActiveUTubGone).toHaveBeenCalledTimes(1);
    expect(handleActiveUTubGone).toHaveBeenCalledWith({ utubID: 3 });
    expect(lastNotice()).toContain("no longer available");
  });

  it("leaves the store alone when the reseed fetch fails", async () => {
    vi.mocked(getAllUTubs).mockRejectedValue(new Error("offline"));
    removeButton(1).click();
    await settle();
    pending[0].resolve({ outcome: "cap" });
    await settle();

    expect(setUTubRowPinned).not.toHaveBeenCalled();
    expect(purgeUTubLocally).not.toHaveBeenCalled();
  });

  it("clears the filter on the first Escape and lets the second pass through", () => {
    const outer = vi.fn();
    document.addEventListener("keydown", outer);
    type("be");

    input().dispatchEvent(
      new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
    );
    expect(input().value).toBe("");
    expect(outer).not.toHaveBeenCalled();

    input().dispatchEvent(
      new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
    );
    expect(outer).toHaveBeenCalledTimes(1);
    document.removeEventListener("keydown", outer);
  });

  it("does nothing when the section is read-only", async () => {
    ctx = { ...ctx, canWrite: false };
    renderSection();
    removeButton(1).click();
    await settle();

    expect(patchUtubPin).not.toHaveBeenCalled();
  });

  it("keeps a UTub name that looks like a placeholder literal in the label", () => {
    seed([utub({ id: 9, name: "{count} $& {max}", isPinned: true })]);
    renderSection();

    expect(removeButton(9).getAttribute("aria-label")).toBe(
      "Unpin {count} $& {max}",
    );
  });

  it("renders the pin icon on each pinned row", () => {
    const item = host.querySelector(".utubPinsItem")!;

    expect(item.querySelector("svg.UTubPinIcon")).not.toBeNull();
  });

  it("rejects a non-pin patch without calling the client", async () => {
    const result = await section.save({
      utubID: null,
      patch: { unrelated: true } as unknown as Parameters<
        typeof section.save
      >[0]["patch"],
    });

    expect(result).toEqual({ outcome: "error", resync: false });
    expect(patchUtubPin).not.toHaveBeenCalled();
  });

  describe("picker semantics", () => {
    it("exposes combobox semantics that follow the option list", () => {
      const listbox = host.querySelector(".utubPinsOptions")!;

      expect(input().getAttribute("role")).toBe("combobox");
      expect(input().getAttribute("aria-autocomplete")).toBe("list");
      expect(input().getAttribute("aria-controls")).toBe(listbox.id);
      expect(input().getAttribute("aria-expanded")).toBe("false");
      type("beta");
      expect(input().getAttribute("aria-expanded")).toBe("true");
      type("zzz");
      expect(input().getAttribute("aria-expanded")).toBe("false");
    });

    it("shows no option list for empty input and the hint when nothing is left", () => {
      expect(optionNames()).toEqual([]);
      seed([utub({ id: 1, name: "Alpha", isPinned: true })]);
      renderSection();

      expect(input().getAttribute("aria-describedby")).toBe(
        "utub-pins-none-left",
      );
      expect(document.getElementById("utub-pins-none-left")).not.toBeNull();
      expect(host.querySelector(".utubPinsNoMatch")?.textContent).toBe("");
    });

    it("ignores Enter while an IME composition is active", async () => {
      type("beta");
      pressKey({ target: input(), key: "Enter", isComposing: true });
      await settle();

      expect(patchUtubPin).not.toHaveBeenCalled();
    });

    it("ignores typing, Enter and the list at the cap and reports 5 of 5", async () => {
      seedPinned({ pinnedCount: 5, unpinned: ["Sixth"] });
      renderSection();

      expect(host.querySelector(".utubPinsCounter")?.textContent).toBe(
        "5 of 5",
      );
      expect(input().getAttribute("aria-describedby")).toBe(
        "utub-pins-cap-note",
      );
      type("six");
      expect(input().value).toBe("");
      pressKey({ target: input(), key: "Enter" });
      await settle();
      expect(patchUtubPin).not.toHaveBeenCalled();
    });

    it("shows the real count and no picker list for more than 5 pinned", () => {
      seedPinned({ pinnedCount: 6, unpinned: ["Seventh"] });
      renderSection();

      expect(host.querySelector(".utubPinsCounter")?.textContent).toBe(
        "6 of 5",
      );
      expect(input().getAttribute("aria-disabled")).toBe("true");
      type("sev");
      expect(optionNames()).toEqual([]);
    });

    it("shows 2 of 5 for two pinned UTubs", () => {
      seedPinned({ pinnedCount: 2, unpinned: ["Third"] });
      renderSection();

      expect(host.querySelector(".utubPinsCounter")?.textContent).toBe(
        "2 of 5",
      );
    });

    it("scrolls the input into view on focus and focuses nothing on open", () => {
      expect(document.activeElement).toBe(document.body);
      const scroll = vi.fn();
      input().scrollIntoView = scroll;
      input().focus();

      expect(scroll).toHaveBeenCalledWith({ block: "nearest" });
    });

    it("moves through options with the arrows and pins with Space", async () => {
      type("a");
      pressKey({ target: input(), key: "ArrowDown" });
      expect(document.activeElement?.textContent).toBe("Beta");
      pressKey({ target: document.activeElement!, key: "ArrowDown" });
      expect(document.activeElement?.textContent).toBe("Gamma");
      pressKey({ target: document.activeElement!, key: "ArrowUp" });
      expect(document.activeElement?.textContent).toBe("Beta");

      pressKey({
        target: document.activeElement!,
        key: " ",
        eventType: "keyup",
      });
      await settle();

      expect(patchUtubPin).toHaveBeenCalledWith({ utubID: 2, pinned: true });
    });

    it("drops a second same-tick Enter", async () => {
      type("beta");
      pressKey({ target: input(), key: "Enter" });
      pressKey({ target: input(), key: "Enter" });
      await settle();

      expect(patchUtubPin).toHaveBeenCalledTimes(1);
    });

    it("pins a clicked option", async () => {
      type("gam");
      (document.querySelector(".utubPinsOption") as HTMLElement).click();
      await settle();

      expect(patchUtubPin).toHaveBeenCalledWith({ utubID: 3, pinned: true });
    });

    it("stops the first Escape from an option, then lets the next pass", () => {
      const outer = vi.fn();
      document.addEventListener("keydown", outer);
      type("a");
      pressKey({ target: input(), key: "ArrowDown" });
      outer.mockClear();

      pressKey({ target: document.activeElement!, key: "Escape" });
      expect(outer).not.toHaveBeenCalled();
      expect(input().value).toBe("");
      expect(document.activeElement).toBe(input());

      pressKey({ target: input(), key: "Escape" });
      expect(outer).toHaveBeenCalledTimes(1);
      document.removeEventListener("keydown", outer);
    });
  });

  describe("filter text", () => {
    it("survives a re-render", () => {
      type("be");
      renderSection();

      expect(input().value).toBe("be");
      expect(optionNames()).toEqual(["Beta"]);
    });

    it("is kept when the user typed more while the write was in flight", async () => {
      type("beta");
      pressKey({ target: input(), key: "Enter" });
      await settle();
      type("betax");
      pending[0].resolve({ outcome: "ok", isPinned: true, pinnedCount: 2 });
      await vi.advanceTimersByTimeAsync(5);

      expect(input().value).toBe("betax");
    });

    it("is kept, with its selection, when the save fails", async () => {
      input().focus();
      type("beta");
      pressKey({ target: input(), key: "Enter" });
      await settle();
      input().setSelectionRange(1, 2);
      input().dispatchEvent(new Event("select", { bubbles: true }));
      pending[0].resolve({ outcome: "error" });
      await vi.advanceTimersByTimeAsync(5);

      expect(input().value).toBe("beta");
      expect(input().selectionStart).toBe(1);
      expect(input().selectionEnd).toBe(2);
      expect(activeId()).toBe(INPUT);
    });

    it("is cleared after a cap-reaching pin", async () => {
      seedPinned({ pinnedCount: 4, unpinned: ["Echo"] });
      renderSection();
      input().focus();
      type("echo");
      pressKey({ target: input(), key: "Enter" });
      await settle();
      pending[0].resolve({ outcome: "ok", isPinned: true, pinnedCount: 5 });
      await vi.advanceTimersByTimeAsync(5);

      expect(input().value).toBe("");
      expect(input().getAttribute("aria-disabled")).toBe("true");
      expect(input().getAttribute("aria-describedby")).toBe(
        "utub-pins-cap-note",
      );
      expect(activeId()).toBe(INPUT);
    });

    it("is cleared after a cap reseed fills the pins", async () => {
      seedPinned({ pinnedCount: 4, unpinned: ["Echo"] });
      renderSection();
      vi.mocked(getAllUTubs).mockResolvedValue({
        utubs: [1, 2, 3, 4, 5].map((id) => ({ id, isPinned: true })),
      } as unknown as Awaited<ReturnType<typeof getAllUTubs>>);
      type("echo");
      pressKey({ target: input(), key: "Enter" });
      await settle();
      pending[0].resolve({ outcome: "cap" });
      await vi.advanceTimersByTimeAsync(5);

      expect(input().value).toBe("");
      expect(input().getAttribute("aria-disabled")).toBe("true");
    });

    it("is cleared when the popover really closes", async () => {
      const dispose = renderWithDisposer({ container: host });
      type("be");
      dispose();
      await Promise.resolve();
      renderSection();

      expect(input().value).toBe("");
    });
  });

  describe("focus after a write", () => {
    beforeEach(() => {
      seedPinned({ pinnedCount: 3, unpinned: ["Delta"] });
      renderSection();
    });

    async function unpin({
      utubID,
      result,
    }: {
      utubID: number;
      result: PinSaveResult;
    }): Promise<void> {
      removeButton(utubID).click();
      await settle();
      pending[0].resolve(result);
      await vi.advanceTimersByTimeAsync(5);
    }

    const UNPINNED: PinSaveResult = {
      outcome: "ok",
      isPinned: false,
      pinnedCount: 2,
    };

    it("moves to the next remove button after unpinning a middle row", async () => {
      await unpin({ utubID: 2, result: UNPINNED });

      expect(activeId()).toBe("utub-pins-remove-3");
    });

    it("moves to the previous remove button after unpinning the last row", async () => {
      await unpin({ utubID: 3, result: UNPINNED });

      expect(activeId()).toBe("utub-pins-remove-2");
    });

    it("falls back to the picker input after unpinning the only row", async () => {
      seedPinned({ pinnedCount: 1, unpinned: ["Delta"] });
      renderSection();
      await unpin({ utubID: 1, result: UNPINNED });

      expect(activeId()).toBe(INPUT);
    });

    it("keeps focus on the input when it held focus", async () => {
      input().focus();
      removeButton(2).click();
      await settle();
      pending[0].resolve(UNPINNED);
      await vi.advanceTimersByTimeAsync(5);

      expect(activeId()).toBe(INPUT);
    });

    it("re-focuses the same remove button after a failed unpin", async () => {
      await unpin({ utubID: 2, result: { outcome: "error" } });

      expect(activeId()).toBe("utub-pins-remove-2");
    });

    it("lands on the next remove button when a 404 drops the acted row", async () => {
      vi.mocked(getAllUTubs).mockResolvedValue({
        utubs: [1, 3].map((id) => ({ id, isPinned: true })),
      } as unknown as Awaited<ReturnType<typeof getAllUTubs>>);
      await unpin({ utubID: 2, result: { outcome: "gone" } });

      expect(storeIds()).not.toContain(2);
      expect(activeId()).toBe("utub-pins-remove-3");
    });

    it("lands on the previous remove button when the reseed also drops the next", async () => {
      vi.mocked(getAllUTubs).mockResolvedValue({
        utubs: [
          { id: 1, isPinned: true },
          { id: 4, isPinned: false },
        ],
      } as unknown as Awaited<ReturnType<typeof getAllUTubs>>);
      await unpin({ utubID: 2, result: { outcome: "gone" } });

      expect(storeIds()).toEqual([1, 4]);
      expect(activeId()).toBe("utub-pins-remove-1");
    });

    it("keeps focus on the input after a pin", async () => {
      input().focus();
      type("delta");
      pressKey({ target: input(), key: "Enter" });
      await settle();
      pending[0].resolve({ outcome: "ok", isPinned: true, pinnedCount: 4 });
      await vi.advanceTimersByTimeAsync(5);

      expect(activeId()).toBe(INPUT);
      expect(activeId()).not.toBe("");
    });
  });

  describe("store ordering and reseed scope", () => {
    it("drops the 404 target first, so a never-settling reseed still removes it", async () => {
      vi.mocked(getAllUTubs).mockReturnValue(
        new Promise(() => {}) as unknown as ReturnType<typeof getAllUTubs>,
      );
      removeButton(1).click();
      await settle();
      pending[0].resolve({ outcome: "gone" });
      await vi.advanceTimersByTimeAsync(PATCH_TIMEOUT_MS);
      await vi.advanceTimersByTimeAsync(5);

      expect(storeIds()).toEqual([2, 3]);
      expect(removeButton(1)).toBeNull();
      expect(lastNotice()).toContain("no longer available");
      expect(input().getAttribute("aria-disabled")).toBe("false");
      expect(handleActiveUTubGone).not.toHaveBeenCalled();
    });

    it("runs the removal contract for an active 404 target even when the reseed fails", async () => {
      setState({ activeUTubID: 2 });
      vi.mocked(getAllUTubs).mockRejectedValue(new Error("offline"));
      type("beta");
      pressKey({ target: input(), key: "Enter" });
      await settle();
      pending[0].resolve({ outcome: "gone" });
      await vi.advanceTimersByTimeAsync(5);

      expect(handleActiveUTubGone).toHaveBeenCalledTimes(1);
      expect(handleActiveUTubGone).toHaveBeenCalledWith({ utubID: 2 });
      expect(storeIds()).toEqual([1, 3]);
      expect(lastNotice()).toContain("no longer available");
    });

    it("keeps an unpinned UTub the server response omits", async () => {
      vi.mocked(getAllUTubs).mockResolvedValue({
        utubs: [
          { id: 1, isPinned: true },
          { id: 2, isPinned: false },
        ],
      } as unknown as Awaited<ReturnType<typeof getAllUTubs>>);
      type("beta");
      pressKey({ target: input(), key: "Enter" });
      await settle();
      pending[0].resolve({ outcome: "cap" });
      await vi.advanceTimersByTimeAsync(5);

      expect(storeIds()).toEqual([1, 2, 3]);
      expect(purgeUTubLocally).not.toHaveBeenCalled();
    });

    it("purges a store-pinned UTub the server no longer lists", async () => {
      seedPinned({ pinnedCount: 2, unpinned: ["Gamma"] });
      renderSection();
      vi.mocked(getAllUTubs).mockResolvedValue({
        utubs: [
          { id: 1, isPinned: true },
          { id: 3, isPinned: false },
        ],
      } as unknown as Awaited<ReturnType<typeof getAllUTubs>>);
      type("gamma");
      pressKey({ target: input(), key: "Enter" });
      await settle();
      pending[0].resolve({ outcome: "cap" });
      await vi.advanceTimersByTimeAsync(5);

      expect(storeIds()).toEqual([1, 3]);
      expect(removeButton(2)).toBeNull();
      expect(handleActiveUTubGone).not.toHaveBeenCalled();
    });

    it("never runs the removal contract for a plain error", async () => {
      removeButton(1).click();
      await settle();
      pending[0].resolve({ outcome: "error" });
      await vi.advanceTimersByTimeAsync(5);

      expect(handleActiveUTubGone).not.toHaveBeenCalled();
      expect(purgeUTubLocally).not.toHaveBeenCalled();
    });
  });

  describe("in-flight flag and cleanup", () => {
    it("keeps the controls disabled across a rebuild and clears them after the save", async () => {
      removeButton(1).click();
      await settle();
      renderSection();

      expect(removeButton(1).getAttribute("aria-disabled")).toBe("true");
      expect(input().getAttribute("aria-disabled")).toBe("true");
      pending[0].resolve({ outcome: "error" });
      await vi.advanceTimersByTimeAsync(5);

      expect(removeButton(1).getAttribute("aria-disabled")).toBe("false");
      expect(input().getAttribute("aria-disabled")).toBe("false");
    });

    it("clears the flag even when the popover closed before the save settled", async () => {
      removeButton(1).click();
      await settle();
      host.remove();
      pending[0].resolve({ outcome: "ok", isPinned: false, pinnedCount: 0 });
      await vi.advanceTimersByTimeAsync(5);
      document.body.append(host);
      renderSection();

      expect(input().getAttribute("aria-disabled")).toBe("false");
    });

    it("recovers when the shell refuses the submit", async () => {
      const submit = vi.fn(() => {
        throw new Error("queue refused");
      });
      ctx = { ...ctx, submit };
      renderSection();
      removeButton(1).click();

      expect(removeButton(1).getAttribute("aria-disabled")).toBe("false");
      removeButton(1).click();
      expect(submit).toHaveBeenCalledTimes(2);
    });

    it("disposes the live render once and never double-disposes a stale one", () => {
      const first = document.createElement("div");
      const second = document.createElement("div");
      document.body.append(first, second);
      const initial = recordedRoving.length;

      const disposeFirst = renderWithDisposer({ container: first });
      const disposeSecond = renderWithDisposer({ container: second });
      const [beforeFirst, firstRender, secondRender] = [
        recordedRoving[initial - 1],
        recordedRoving[initial],
        recordedRoving[initial + 1],
      ];

      expect(beforeFirst.detachKeyListeners).toHaveBeenCalledTimes(1);
      expect(firstRender.detachKeyListeners).toHaveBeenCalledTimes(1);
      disposeFirst();
      expect(secondRender.detachKeyListeners).toHaveBeenCalledTimes(1);
      disposeSecond();
      expect(secondRender.detachKeyListeners).toHaveBeenCalledTimes(1);
      expect(firstRender.detachKeyListeners).toHaveBeenCalledTimes(1);
    });
  });
});
