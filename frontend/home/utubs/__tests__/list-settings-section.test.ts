import { getState, resetStore } from "../../../store/app-store.js";
import {
  handleActiveUTubGone,
  patchUtubListPreferences,
} from "../../panel-settings/client.js";
import type { ListPreferencesSaveResult } from "../../panel-settings/client.js";
import { rerenderSectionIfIdle } from "../../panel-settings/index.js";
import { DEBOUNCE_MS, createSaveQueue } from "../../panel-settings/queue.js";
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
import {
  getPrefsVersion,
  hasOutstandingEdit,
  markEdit,
  recordSavedPreference,
  reseedListPreferences,
  resetListPreferenceTracking,
  setReseedListener,
} from "../list-preferences.js";
import { registerUtubListSettingsSection } from "../list-settings-section.js";
import { reorderUTubDeck, scrollActiveUTubIntoViewIfHidden } from "../sort.js";
import { getAllUTubs } from "../utils.js";

vi.mock("../../panel-settings/client.js", () => ({
  handleActiveUTubGone: vi.fn(),
  resyncSettings: vi.fn(async () => true),
  resyncMemberSettings: vi.fn(async () => true),
  patchUtubListPreferences: vi.fn(),
}));
vi.mock("../../panel-settings/index.js", () => ({
  rerenderSectionIfIdle: vi.fn(),
}));
vi.mock("../../utubs/stale-data.js", () => ({
  updateUTubOnFindingStaleData: vi.fn(async () => {}),
}));
vi.mock("../sort.js", () => ({
  reorderUTubDeck: vi.fn(),
  scrollActiveUTubIntoViewIfHidden: vi.fn(),
}));
vi.mock("../utils.js", () => ({ getAllUTubs: vi.fn() }));

const SORT = "#utub-list-sort";
const ROW_COUNTS = "#utub-list-row-counts";
const TOTALS = "#utub-list-list-totals";

const $ = window.jQuery;

interface Echo {
  utubSort: string;
  showRowCounts: boolean;
  showListTotals: boolean;
}

const BASE_ECHO: Echo = {
  utubSort: "recent_activity",
  showRowCounts: false,
  showListTotals: true,
};

interface PendingSave {
  patch: Record<string, unknown>;
  resolve(result: ListPreferencesSaveResult): void;
}

function ok(overrides: Partial<Echo> = {}): ListPreferencesSaveResult {
  return {
    outcome: "ok",
    preferences: { ...BASE_ECHO, ...overrides } as Echo &
      Extract<ListPreferencesSaveResult, { outcome: "ok" }>["preferences"],
  };
}

function failed(
  outcome: "invalid" | "error" | "forbidden" | "gone",
  timedOut = false,
): ListPreferencesSaveResult {
  return { outcome: "failed", result: { outcome }, timedOut };
}

function sortSelect(): HTMLSelectElement {
  return document.querySelector<HTMLSelectElement>(SORT)!;
}

function switchEl(selector: string): HTMLElement {
  return document.querySelector<HTMLElement>(selector)!;
}

function pickSort(value: string): void {
  const select = sortSelect();
  select.value = value;
  select.dispatchEvent(new Event("change", { bubbles: true }));
}

function flip(selector: string): void {
  switchEl(selector).click();
}

async function settle(): Promise<void> {
  await vi.advanceTimersByTimeAsync(0);
}

async function debounce(): Promise<void> {
  await vi.advanceTimersByTimeAsync(DEBOUNCE_MS);
}

function checked(selector: string): string | null {
  return switchEl(selector).getAttribute("aria-checked");
}

describe("UTub list settings section", () => {
  let host: HTMLElement;
  let section: PanelSection;
  let unregister: () => void;
  let queue: SaveQueue;
  let sink: { [Key in keyof QueueSink]: ReturnType<typeof vi.fn> } & QueueSink;
  let pending: PendingSave[];
  let ctx: SectionContext;

  // Stands in for the shell: renders the section, and re-renders it (restoring
  // focus by element id) when a save reports an error.
  function renderSection(): void {
    const focusedId = host.contains(document.activeElement)
      ? (document.activeElement as HTMLElement).id
      : "";
    host.innerHTML = "";
    section.render({ container: host, ctx });
    if (focusedId !== "") document.getElementById(focusedId)?.focus();
  }

  function lastNotice(): string | undefined {
    const savedCalls = sink.report.mock.calls
      .map(([args]) => args as { status: string; notice?: string })
      .filter((args) => args.status === "saved");
    return savedCalls[savedCalls.length - 1]?.notice;
  }

  function deckClass(name: string): boolean {
    return $("#UTubDeck").hasClass(name);
  }

  beforeEach(() => {
    vi.useFakeTimers();
    _resetRegistryForTests();
    resetStore();
    resetListPreferenceTracking();
    setReseedListener(null);
    vi.clearAllMocks();
    document.body.innerHTML = `<div id="UTubDeck"></div>`;
    host = document.createElement("div");
    document.body.append(host);

    pending = [];
    vi.mocked(patchUtubListPreferences).mockImplementation(
      ({ patch }) =>
        new Promise<ListPreferencesSaveResult>((resolve) => {
          pending.push({ patch, resolve });
        }),
    );

    unregister = registerUtubListSettingsSection();
    section = getSections("utubs")[0];

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
      submit: ({ patch, debounce: shouldDebounce }) =>
        queue.enqueue({ section, patch, debounce: shouldDebounce }),
    };
    renderSection();
  });

  afterEach(() => {
    unregister();
    vi.useRealTimers();
    resetStore();
    document.body.innerHTML = "";
  });

  it("registers a global user section on the utubs panel", () => {
    expect(section).toMatchObject({
      id: "utubs-list",
      panel: "utubs",
      scope: "user",
      userKind: "global",
      title: "Your UTub list",
    });
  });

  it("renders the stored values, with accessible names and five sort options", () => {
    unregister();
    recordSavedPreference({ field: "utubSort", value: "name_az" });
    recordSavedPreference({ field: "showRowCounts", value: true });
    recordSavedPreference({ field: "showListTotals", value: false });
    unregister = registerUtubListSettingsSection();
    renderSection();

    expect(sortSelect().value).toBe("name_az");
    expect(sortSelect().options).toHaveLength(5);
    expect(sortSelect().getAttribute("aria-labelledby")).toBeTruthy();
    expect(checked(ROW_COUNTS)).toBe("true");
    expect(checked(TOTALS)).toBe("false");
    expect(
      document.getElementById(switchEl(TOTALS).getAttribute("aria-labelledby")!)
        ?.textContent,
    ).toBe("Show list totals");
  });

  it("unregister removes the section and clears the reseed listener", () => {
    unregister();
    unregister = () => {};

    expect(getSections("utubs")).toHaveLength(0);
    reseedListPreferences({
      preferences: {
        utubSort: "oldest_created",
        showRowCounts: false,
        showListTotals: true,
      },
      capturedVersion: getPrefsVersion(),
    });
    expect(rerenderSectionIfIdle).not.toHaveBeenCalled();
  });

  it("reads the store on every render, not a closure copy", () => {
    recordSavedPreference({ field: "showRowCounts", value: true });
    renderSection();
    expect(checked(ROW_COUNTS)).toBe("true");
  });

  it("a change sends only that field and success applies it with a notice", async () => {
    flip(ROW_COUNTS);
    await settle();
    expect(pending.map((save) => save.patch)).toEqual([
      { showRowCounts: true },
    ]);

    pending[0].resolve(ok({ showRowCounts: true }));
    await settle();

    expect(getState().preferences.showRowCounts).toBe(true);
    expect(deckClass("showUTubRowCounts")).toBe(true);
    expect(lastNotice()).toBe("Row counts shown");
    expect(hasOutstandingEdit("showRowCounts")).toBe(false);
    expect(handleActiveUTubGone).not.toHaveBeenCalled();
  });

  it("works with no UTub selected and applies only the patched field though the echo carries all three", async () => {
    expect(getState().activeUTubID).toBeNull();
    flip(TOTALS);
    await settle();
    pending[0].resolve(
      ok({ showListTotals: false, showRowCounts: true, utubSort: "name_az" }),
    );
    await settle();

    expect(getState().preferences.showListTotals).toBe(false);
    expect(deckClass("hideListTotals")).toBe(true);
    expect(getState().preferences.showRowCounts).toBe(false);
    expect(getState().preferences.utubSort).toBe("recent_activity");
    expect(reorderUTubDeck).not.toHaveBeenCalled();
    expect(lastNotice()).toBe("List totals hidden");
  });

  it("a sort success reorders the deck, scrolls and announces the spoken option", async () => {
    pickSort("name_az");
    await debounce();
    pending[0].resolve(ok({ utubSort: "name_az" }));
    await settle();

    expect(getState().preferences.utubSort).toBe("name_az");
    expect(reorderUTubDeck).toHaveBeenCalledWith("name_az");
    expect(scrollActiveUTubIntoViewIfHidden).toHaveBeenCalledTimes(1);
    expect(lastNotice()).toBe("Sorted by Name A to Z");
  });

  it("debounces the sort select: a burst sends one PATCH and one notice for the final option", async () => {
    pickSort("last_opened");
    pickSort("newest_created");
    pickSort("oldest_created");
    await settle();
    expect(pending).toHaveLength(0);

    await debounce();
    expect(pending.map((save) => save.patch)).toEqual([
      { utubSort: "oldest_created" },
    ]);

    pending[0].resolve(ok({ utubSort: "oldest_created" }));
    await settle();
    expect(lastNotice()).toBe("Sorted by Oldest created");
    expect(reorderUTubDeck).toHaveBeenCalledTimes(1);
  });

  it("a switch is not debounced", async () => {
    flip(ROW_COUNTS);
    await settle();
    expect(pending).toHaveLength(1);
  });

  describe("failed saves", () => {
    it.each([
      ["400", failed("invalid")],
      ["500", failed("error")],
      ["429", failed("error")],
      ["403", failed("forbidden")],
      ["404", failed("gone")],
      ["405 HTML", failed("error")],
      ["malformed 200", failed("error")],
      ["timeout", failed("error", true)],
    ])(
      "%s clears every token, shows saved values, keeps the deck and never runs UTub-gone handling",
      async (_label, outcome) => {
        vi.mocked(getAllUTubs).mockImplementation(
          () => Promise.reject(new Error("offline")) as never,
        );
        switchEl(ROW_COUNTS).focus();
        flip(ROW_COUNTS);
        await settle();
        expect(checked(ROW_COUNTS)).toBe("true");

        pending[0].resolve(outcome);
        await settle();

        expect(hasOutstandingEdit("showRowCounts")).toBe(false);
        expect(hasOutstandingEdit("utubSort")).toBe(false);
        expect(hasOutstandingEdit("showListTotals")).toBe(false);
        expect(checked(ROW_COUNTS)).toBe("false");
        expect(getState().preferences.showRowCounts).toBe(false);
        expect(deckClass("showUTubRowCounts")).toBe(false);
        expect(reorderUTubDeck).not.toHaveBeenCalled();
        expect(handleActiveUTubGone).not.toHaveBeenCalled();
        expect(document.activeElement?.id).toBe("utub-list-row-counts");
      },
    );

    it("a timeout runs one guarded resync that applies a committed sort without rebuilding the deck", async () => {
      vi.mocked(getAllUTubs).mockResolvedValue({
        preferences: {
          utubSort: "name_az",
          showRowCounts: false,
          showListTotals: true,
        },
      } as never);
      pickSort("name_az");
      await debounce();
      pending[0].resolve(failed("error", true));
      await settle();

      expect(getAllUTubs).toHaveBeenCalledTimes(1);
      expect(getState().preferences.utubSort).toBe("name_az");
      expect(reorderUTubDeck).toHaveBeenCalledWith("name_az");
      expect(scrollActiveUTubIntoViewIfHidden).toHaveBeenCalledTimes(1);
    });

    it("a timeout resync does not undo a save that settles during the request", async () => {
      let respond!: (value: unknown) => void;
      vi.mocked(getAllUTubs).mockReturnValue(
        new Promise((resolve) => {
          respond = resolve;
        }) as never,
      );
      flip(ROW_COUNTS);
      await settle();
      pending[0].resolve(failed("error", true));
      await settle();
      const capturedBefore = getPrefsVersion();

      flip(TOTALS);
      await settle();
      pending[1].resolve(ok({ showListTotals: false }));
      await settle();
      expect(getPrefsVersion()).toBeGreaterThan(capturedBefore);

      respond({
        preferences: {
          utubSort: "recent_activity",
          showRowCounts: false,
          showListTotals: true,
        },
      });
      await settle();
      expect(getState().preferences.showListTotals).toBe(false);
    });

    it.each([
      ["400", failed("invalid")],
      ["500", failed("error")],
      ["403", failed("forbidden")],
      ["404", failed("gone")],
      ["429", failed("error")],
      ["malformed 200", failed("error")],
    ])("%s triggers no resync", async (_label, outcome) => {
      flip(ROW_COUNTS);
      await settle();
      pending[0].resolve(outcome);
      await settle();
      expect(getAllUTubs).not.toHaveBeenCalled();
    });

    it("a failed sort save restores focus to the sort select and shows the saved value", async () => {
      sortSelect().focus();
      pickSort("name_az");
      await debounce();
      pending[0].resolve(failed("error"));
      await settle();

      expect(sortSelect().value).toBe("recent_activity");
      expect(document.activeElement?.id).toBe("utub-list-sort");
    });

    it("a timeout with a superseded save in baselineAhead re-applies the deck from the store, then resyncs", async () => {
      vi.mocked(getAllUTubs).mockResolvedValue({
        preferences: {
          utubSort: "recent_activity",
          showRowCounts: true,
          showListTotals: true,
        },
      } as never);
      flip(ROW_COUNTS);
      await settle();
      flip(ROW_COUNTS);
      await settle();
      pending[0].resolve(ok({ showRowCounts: true }));
      await settle();
      expect(deckClass("showUTubRowCounts")).toBe(false);

      pending[1].resolve(failed("error", true));
      await settle();

      expect(deckClass("showUTubRowCounts")).toBe(true);
      expect(getState().preferences.showRowCounts).toBe(true);
      expect(getAllUTubs).toHaveBeenCalledTimes(1);
    });

    it("a timeout resync skips a field with a new outstanding edit and does not re-render the open section", async () => {
      let respond!: (value: unknown) => void;
      vi.mocked(getAllUTubs).mockReturnValue(
        new Promise((resolve) => {
          respond = resolve;
        }) as never,
      );
      flip(ROW_COUNTS);
      await settle();
      pending[0].resolve(failed("error", true));
      await settle();

      flip(TOTALS);
      await settle();
      respond({
        preferences: {
          utubSort: "recent_activity",
          showRowCounts: true,
          showListTotals: false,
        },
      });
      await settle();

      expect(getState().preferences.showRowCounts).toBe(true);
      expect(getState().preferences.showListTotals).toBe(true);
      expect(hasOutstandingEdit("showListTotals")).toBe(true);
      expect(rerenderSectionIfIdle).not.toHaveBeenCalled();
    });

    it("a save whose field was never marked fails closed: the baseline is recorded but the deck and notice are not applied", async () => {
      const savePromise = section.save({
        utubID: null,
        patch: { showRowCounts: true },
      });
      pending[0].resolve(ok({ showRowCounts: true }));
      const result = await savePromise;

      expect(getState().preferences.showRowCounts).toBe(true);
      expect(deckClass("showUTubRowCounts")).toBe(false);
      expect(result).toEqual({ outcome: "ok" });
    });

    it("a failed first save with a queued second change clears both tokens and shows both saved values", async () => {
      flip(ROW_COUNTS);
      await settle();
      flip(TOTALS);
      await settle();
      expect(pending).toHaveLength(1);
      expect(hasOutstandingEdit("showListTotals")).toBe(true);

      pending[0].resolve(failed("invalid"));
      await settle();

      expect(pending).toHaveLength(1);
      expect(hasOutstandingEdit("showRowCounts")).toBe(false);
      expect(hasOutstandingEdit("showListTotals")).toBe(false);
      expect(checked(ROW_COUNTS)).toBe("false");
      expect(checked(TOTALS)).toBe("true");
    });
  });

  describe("overlapping edits", () => {
    it("two quick changes to different controls both persist, each sending only its field", async () => {
      flip(ROW_COUNTS);
      await settle();
      flip(TOTALS);
      await settle();
      expect(pending.map((save) => save.patch)).toEqual([
        { showRowCounts: true },
      ]);

      pending[0].resolve(ok({ showRowCounts: true, showListTotals: true }));
      await settle();
      // The first echo must not overwrite the second control.
      expect(checked(TOTALS)).toBe("false");
      expect(getState().preferences.showListTotals).toBe(true);

      expect(pending.map((save) => save.patch)).toEqual([
        { showRowCounts: true },
        { showListTotals: false },
      ]);
      pending[1].resolve(ok({ showRowCounts: true, showListTotals: false }));
      await settle();

      expect(getState().preferences.showRowCounts).toBe(true);
      expect(getState().preferences.showListTotals).toBe(false);
      expect(deckClass("hideListTotals")).toBe(true);
    });

    it("a superseded echo is recorded but not applied, and its notice is withheld", async () => {
      pickSort("name_az");
      await debounce();
      pickSort("newest_created");
      await debounce();
      expect(pending).toHaveLength(1);

      const versionBefore = getPrefsVersion();
      pending[0].resolve(ok({ utubSort: "name_az" }));
      await settle();

      expect(getState().preferences.utubSort).toBe("name_az");
      expect(reorderUTubDeck).not.toHaveBeenCalled();
      expect(sortSelect().value).toBe("newest_created");
      expect(getPrefsVersion()).toBe(versionBefore + 1);
      expect(hasOutstandingEdit("utubSort")).toBe(true);
      expect(lastNotice()).toBeUndefined();

      pending[1].resolve(ok({ utubSort: "newest_created" }));
      await settle();

      expect(reorderUTubDeck).toHaveBeenCalledTimes(1);
      expect(reorderUTubDeck).toHaveBeenCalledWith("newest_created");
      expect(lastNotice()).toBe("Sorted by Newest created");
      expect(hasOutstandingEdit("utubSort")).toBe(false);
    });

    it("a superseded save followed by a failing one leaves store, control and deck on the first value", async () => {
      pickSort("name_az");
      await debounce();
      pickSort("newest_created");
      await debounce();
      pending[0].resolve(ok({ utubSort: "name_az" }));
      await settle();
      pending[1].resolve(failed("error"));
      await settle();

      expect(hasOutstandingEdit("utubSort")).toBe(false);
      expect(getState().preferences.utubSort).toBe("name_az");
      expect(sortSelect().value).toBe("name_az");
      expect(reorderUTubDeck).toHaveBeenCalledTimes(1);
      expect(reorderUTubDeck).toHaveBeenCalledWith("name_az");
    });

    it("a superseded toggle that then fails is re-applied to the deck from the store", async () => {
      flip(ROW_COUNTS);
      await settle();
      flip(ROW_COUNTS);
      await settle();
      pending[0].resolve(ok({ showRowCounts: true }));
      await settle();
      expect(deckClass("showUTubRowCounts")).toBe(false);

      pending[1].resolve(failed("error"));
      await settle();

      expect(getState().preferences.showRowCounts).toBe(true);
      expect(deckClass("showUTubRowCounts")).toBe(true);
      expect(checked(ROW_COUNTS)).toBe("true");
    });

    it("a coalesced two-field patch sends both fields and joins the notices in fixed order", async () => {
      flip(TOTALS);
      await settle();
      pickSort("name_az");
      flip(ROW_COUNTS);
      await settle();
      pending[0].resolve(ok({ showListTotals: false }));
      await settle();

      expect(pending[1].patch).toEqual({
        utubSort: "name_az",
        showRowCounts: true,
      });
      pending[1].resolve(
        ok({
          utubSort: "name_az",
          showRowCounts: true,
          showListTotals: false,
        }),
      );
      await settle();

      expect(lastNotice()).toBe("Sorted by Name A to Z. Row counts shown");
    });

    it("a multi-field patch with one superseded field announces only the applied field", async () => {
      flip(TOTALS);
      await settle();
      pickSort("name_az");
      flip(ROW_COUNTS);
      await settle();
      pending[0].resolve(ok({ showListTotals: false }));
      await settle();
      // Newer sort edit while the two-field patch is in flight.
      pickSort("oldest_created");
      pending[1].resolve(
        ok({
          utubSort: "name_az",
          showRowCounts: true,
          showListTotals: false,
        }),
      );
      await settle();

      expect(lastNotice()).toBe("Row counts shown");
      expect(reorderUTubDeck).not.toHaveBeenCalled();
    });

    it("a sort change then a switch flip before the debounce fires persists both and settles the sort once", async () => {
      pickSort("name_az");
      flip(ROW_COUNTS);
      await settle();

      expect(pending.map((save) => save.patch)).toEqual([
        { utubSort: "name_az", showRowCounts: true },
      ]);
      const versionBefore = getPrefsVersion();
      pending[0].resolve(ok({ utubSort: "name_az", showRowCounts: true }));
      await settle();

      expect(reorderUTubDeck).toHaveBeenCalledTimes(1);
      expect(getPrefsVersion()).toBe(versionBefore + 2);
      expect(hasOutstandingEdit("utubSort")).toBe(false);
      expect(hasOutstandingEdit("showRowCounts")).toBe(false);
      await debounce();
      expect(pending).toHaveLength(1);
    });
  });

  describe("rebuild reseed", () => {
    const SERVER_PREFS = {
      utubSort: "oldest_created",
      showRowCounts: false,
      showListTotals: true,
    };

    it("re-renders the open section through the shell when a reseed changed a value", () => {
      reseedListPreferences({
        preferences: SERVER_PREFS,
        capturedVersion: getPrefsVersion(),
      });

      expect(rerenderSectionIfIdle).toHaveBeenCalledWith({
        sectionId: "utubs-list",
      });
    });

    it("does not re-render while a field has an outstanding edit, and does not overwrite it", () => {
      markEdit("utubSort");
      reseedListPreferences({
        preferences: { ...SERVER_PREFS, showRowCounts: true },
        capturedVersion: getPrefsVersion(),
      });

      expect(getState().preferences.utubSort).toBe("recent_activity");
      expect(getState().preferences.showRowCounts).toBe(true);
      expect(rerenderSectionIfIdle).not.toHaveBeenCalled();
    });
  });
});
