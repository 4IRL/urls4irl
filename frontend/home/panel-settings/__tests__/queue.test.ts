import { resetStore, setState } from "../../../store/app-store.js";
import { updateUTubOnFindingStaleData } from "../../utubs/stale-data.js";
import { handleActiveUTubGone, resyncSettings } from "../client.js";
import { DEBOUNCE_MS, createSaveQueue } from "../queue.js";
import {
  isPanelSettingsBusy,
  setPanelSettingsPendingSaveCount,
} from "../state.js";
import type { PanelSection, SaveResult } from "../types.js";
import { makeSection, makeSink } from "./helpers.js";

vi.mock("../client.js", () => ({
  handleActiveUTubGone: vi.fn(),
  resyncSettings: vi.fn(async () => true),
}));
vi.mock("../../utubs/stale-data.js", () => ({
  updateUTubOnFindingStaleData: vi.fn(async () => {}),
}));

const UTUB_ID = 7;

interface Deferred {
  promise: Promise<SaveResult>;
  resolve: (result: SaveResult) => void;
}

function deferred(): Deferred {
  let resolve!: (result: SaveResult) => void;
  const promise = new Promise<SaveResult>((innerResolve) => {
    resolve = innerResolve;
  });
  return { promise, resolve };
}

async function settle(): Promise<void> {
  await vi.advanceTimersByTimeAsync(0);
}

function saveCalls(section: PanelSection): unknown[] {
  return vi.mocked(section.save).mock.calls.map(([args]) => args);
}

function setup() {
  const sink = makeSink();
  const queue = createSaveQueue({ sink });
  return { sink, queue };
}

// Section whose save() calls are answered one by one through `pending`.
function controlledSection(overrides: Partial<PanelSection> = {}): {
  section: PanelSection;
  pending: Deferred[];
} {
  const pending: Deferred[] = [];
  const section = makeSection({
    save: vi.fn(() => {
      const next = deferred();
      pending.push(next);
      return next.promise;
    }),
    ...overrides,
  });
  return { section, pending };
}

describe("createSaveQueue", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    vi.mocked(resyncSettings).mockResolvedValue(true);
    resetStore();
    setPanelSettingsPendingSaveCount({ count: 0 });
    setState({
      activeUTubID: UTUB_ID,
      isCurrentUserOwner: true,
      isCoCreator: false,
      isCurrentUTubLocked: false,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe("send serialization and coalescing", () => {
    it("sends immediately for a non-debounced submit and reports saving then saved with savedPatch", async () => {
      const { sink, queue } = setup();
      const section = makeSection();

      queue.enqueue({ section, patch: { sort: "a" } });
      await settle();

      expect(saveCalls(section)).toEqual([
        { utubID: UTUB_ID, patch: { sort: "a" } },
      ]);
      expect(sink.report).toHaveBeenNthCalledWith(1, {
        sectionId: section.id,
        utubID: UTUB_ID,
        status: "saving",
      });
      expect(sink.report).toHaveBeenNthCalledWith(2, {
        sectionId: section.id,
        utubID: UTUB_ID,
        status: "saved",
        savedPatch: { sort: "a" },
      });
    });

    it("never has two saves in flight for one key and shallow-merges edits made meanwhile", async () => {
      const { queue } = setup();
      const { section, pending } = controlledSection();

      queue.enqueue({ section, patch: { a: 1 } });
      queue.enqueue({ section, patch: { b: 2 } });
      queue.enqueue({ section, patch: { b: 3, c: 4 } });
      await settle();
      expect(section.save).toHaveBeenCalledTimes(1);

      pending[0].resolve({ outcome: "ok" });
      await settle();

      expect(saveCalls(section)).toEqual([
        { utubID: UTUB_ID, patch: { a: 1 } },
        { utubID: UTUB_ID, patch: { b: 3, c: 4 } },
      ]);
    });

    it("serializes sections of the same panel and sends them FIFO", async () => {
      const { queue } = setup();
      const first = controlledSection({ id: "one" });
      const second = controlledSection({ id: "two" });

      queue.enqueue({ section: first.section, patch: { a: 1 } });
      queue.enqueue({ section: second.section, patch: { b: 1 } });
      await settle();

      expect(first.section.save).toHaveBeenCalledTimes(1);
      expect(second.section.save).not.toHaveBeenCalled();

      first.pending[0].resolve({ outcome: "ok" });
      await settle();
      expect(second.section.save).toHaveBeenCalledTimes(1);
    });

    it("runs sections of different panels in parallel", async () => {
      const { queue } = setup();
      const urls = controlledSection({ id: "u", panel: "urls" });
      const tags = controlledSection({ id: "t", panel: "tags" });

      queue.enqueue({ section: urls.section, patch: { a: 1 } });
      queue.enqueue({ section: tags.section, patch: { b: 1 } });
      await settle();

      expect(urls.section.save).toHaveBeenCalledTimes(1);
      expect(tags.section.save).toHaveBeenCalledTimes(1);
    });

    it("captures the utubID at enqueue time, so a later flush still targets it", async () => {
      const { queue } = setup();
      const section = makeSection();

      queue.enqueue({ section, patch: { a: 1 }, debounce: true });
      setState({ activeUTubID: 99 });
      queue.flush({ sectionId: section.id });
      await settle();

      expect(saveCalls(section)).toEqual([
        { utubID: UTUB_ID, patch: { a: 1 } },
      ]);
    });
  });

  describe("debounce and flush", () => {
    it("sends once, 300ms after the last debounced submit", async () => {
      const { queue } = setup();
      const section = makeSection();

      queue.enqueue({ section, patch: { a: 1 }, debounce: true });
      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS - 1);
      queue.enqueue({ section, patch: { b: 2 }, debounce: true });
      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS - 1);
      expect(section.save).not.toHaveBeenCalled();

      await vi.advanceTimersByTimeAsync(1);
      expect(saveCalls(section)).toEqual([
        { utubID: UTUB_ID, patch: { a: 1, b: 2 } },
      ]);
    });

    it("a non-debounced submit cancels the timer and sends the merged patch", async () => {
      const { queue } = setup();
      const section = makeSection();

      queue.enqueue({ section, patch: { a: 1 }, debounce: true });
      queue.enqueue({ section, patch: { b: 2 } });
      await settle();
      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS * 2);

      expect(saveCalls(section)).toEqual([
        { utubID: UTUB_ID, patch: { a: 1, b: 2 } },
      ]);
    });

    it("flush sends pending edits immediately, for one section or all", async () => {
      const { queue } = setup();
      const one = makeSection({ id: "one", panel: "urls" });
      const two = makeSection({ id: "two", panel: "tags" });

      queue.enqueue({ section: one, patch: { a: 1 }, debounce: true });
      queue.enqueue({ section: two, patch: { b: 1 }, debounce: true });
      queue.flush({ sectionId: "one" });
      await settle();
      expect(one.save).toHaveBeenCalledTimes(1);
      expect(two.save).not.toHaveBeenCalled();

      queue.flush({});
      await settle();
      expect(two.save).toHaveBeenCalledTimes(1);
      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS * 2);
      expect(one.save).toHaveBeenCalledTimes(1);
    });

    it("a pending patch with a running debounce timer waits for the timer after the in-flight save settles", async () => {
      const { queue } = setup();
      const { section, pending } = controlledSection();

      queue.enqueue({ section, patch: { a: 1 } });
      await settle();
      queue.enqueue({ section, patch: { b: 2 }, debounce: true });
      pending[0].resolve({ outcome: "ok" });
      await settle();
      expect(section.save).toHaveBeenCalledTimes(1);

      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS);
      expect(section.save).toHaveBeenCalledTimes(2);
    });
  });

  describe("user scope keys", () => {
    it("a global user key ignores UTub switches and passes utubID null", async () => {
      const { queue } = setup();
      const section = makeSection({
        scope: "user",
        userKind: "global",
        panel: "utubs",
      });
      queue.enqueue({ section, patch: { a: 1 }, debounce: true });
      setState({ activeUTubID: 99 });
      queue.flush({ sectionId: section.id });
      await settle();

      expect(saveCalls(section)).toEqual([{ utubID: null, patch: { a: 1 } }]);
    });

    it("a global user key is sent with no active UTub at all", async () => {
      const { queue } = setup();
      const section = makeSection({
        scope: "user",
        userKind: "global",
        panel: "utubs",
      });
      setState({ activeUTubID: null });

      queue.enqueue({ section, patch: { a: 1 } });
      await settle();

      expect(saveCalls(section)).toEqual([{ utubID: null, patch: { a: 1 } }]);
    });

    it("a per-utub user key converts a late ok to stale with no saved report or announce", async () => {
      const { sink, queue } = setup();
      const { section, pending } = controlledSection({
        scope: "user",
        userKind: "per-utub",
        panel: "members",
      });

      queue.enqueue({ section, patch: { a: 1 } });
      await settle();
      setState({ activeUTubID: 99 });
      pending[0].resolve({ outcome: "ok" });
      await settle();

      expect(sink.report).not.toHaveBeenCalledWith(
        expect.objectContaining({ status: "saved" }),
      );
      expect(sink.announce).not.toHaveBeenCalled();
      expect(isPanelSettingsBusy()).toBe(false);
    });

    it("a per-utub user key is keyed by (id, utubID) and converts a late result to stale", async () => {
      const { sink, queue } = setup();
      const { section, pending } = controlledSection({
        scope: "user",
        userKind: "per-utub",
        panel: "members",
        title: "Member prefs",
      });

      queue.enqueue({ section, patch: { a: 1 } });
      await settle();
      setState({ activeUTubID: 99 });
      pending[0].resolve({ outcome: "error" });
      await settle();

      expect(sink.report).not.toHaveBeenCalledWith(
        expect.objectContaining({ status: "error" }),
      );
      expect(resyncSettings).not.toHaveBeenCalled();
      expect(sink.announce).toHaveBeenCalledWith({
        sectionId: section.id,
        utubID: UTUB_ID,
        message: "Member prefs: Couldn't save",
      });
    });

    it.each(["locked", "forbidden", "gone"] as const)(
      "a global user key treats %s as error",
      async (outcome) => {
        const { sink, queue } = setup();
        const { section, pending } = controlledSection({
          scope: "user",
          userKind: "global",
          panel: "utubs",
        });

        queue.enqueue({ section, patch: { a: 1 } });
        await settle();
        pending[0].resolve({ outcome });
        await settle();

        expect(sink.report).toHaveBeenLastCalledWith({
          sectionId: section.id,
          utubID: null,
          status: "error",
        });
        expect(sink.forceReadOnly).not.toHaveBeenCalled();
        expect(handleActiveUTubGone).not.toHaveBeenCalled();
        expect(updateUTubOnFindingStaleData).not.toHaveBeenCalled();
        expect(resyncSettings).not.toHaveBeenCalled();
      },
    );

    it.each(["locked", "forbidden"] as const)(
      "a per-utub user key treats %s as error with no read-only flip",
      async (outcome) => {
        const { sink, queue } = setup();
        const { section, pending } = controlledSection({
          scope: "user",
          userKind: "per-utub",
          panel: "members",
        });

        queue.enqueue({ section, patch: { a: 1 } });
        await settle();
        pending[0].resolve({ outcome });
        await settle();

        expect(sink.report).toHaveBeenLastCalledWith({
          sectionId: section.id,
          utubID: UTUB_ID,
          status: "error",
        });
        expect(sink.forceReadOnly).not.toHaveBeenCalled();
        expect(updateUTubOnFindingStaleData).not.toHaveBeenCalled();
      },
    );

    it("gone on a per-utub key for the still-active UTub removes it once and drops every key for that UTub", async () => {
      const { sink, queue } = setup();
      const { section, pending } = controlledSection({
        scope: "user",
        userKind: "per-utub",
        panel: "members",
      });
      const sibling = makeSection({ id: "sibling", panel: "tags" });

      queue.enqueue({ section, patch: { a: 1 } });
      await settle();
      queue.enqueue({ section: sibling, patch: { b: 1 }, debounce: true });
      pending[0].resolve({ outcome: "gone" });
      await settle();

      expect(handleActiveUTubGone).toHaveBeenCalledTimes(1);
      expect(handleActiveUTubGone).toHaveBeenCalledWith({ utubID: UTUB_ID });
      expect(sink.report).not.toHaveBeenCalledWith(
        expect.objectContaining({ status: "error" }),
      );
      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS * 2);
      expect(sibling.save).not.toHaveBeenCalled();
    });
  });

  describe("outcomes", () => {
    it("error drops the pending patch, rolls back and resyncs; resynced only when it resolves true", async () => {
      const { sink, queue } = setup();
      const { section, pending } = controlledSection();

      queue.enqueue({ section, patch: { a: 1 } });
      await settle();
      queue.enqueue({ section, patch: { typed: "meanwhile" } });
      pending[0].resolve({ outcome: "error" });
      await settle();

      expect(sink.report).toHaveBeenLastCalledWith({
        sectionId: section.id,
        utubID: UTUB_ID,
        status: "error",
      });
      expect(resyncSettings).toHaveBeenCalledWith({ utubID: UTUB_ID });
      expect(sink.resynced).toHaveBeenCalledWith({
        sectionId: section.id,
        utubID: UTUB_ID,
      });
      expect(section.save).toHaveBeenCalledTimes(1);
    });

    it("does not call resynced when the resync resolves false", async () => {
      vi.mocked(resyncSettings).mockResolvedValue(false);
      const { sink, queue } = setup();
      const { section, pending } = controlledSection();

      queue.enqueue({ section, patch: { a: 1 } });
      await settle();
      pending[0].resolve({ outcome: "error" });
      await settle();

      expect(resyncSettings).toHaveBeenCalledTimes(1);
      expect(sink.resynced).not.toHaveBeenCalled();
    });

    it("a 429-shaped error rolls back with no resync, no resynced and no read-only flip", async () => {
      const { sink, queue } = setup();
      const { section, pending } = controlledSection();

      queue.enqueue({ section, patch: { a: 1 } });
      await settle();
      pending[0].resolve({ outcome: "error", resync: false });
      await settle();

      expect(sink.report).toHaveBeenLastCalledWith({
        sectionId: section.id,
        utubID: UTUB_ID,
        status: "error",
      });
      expect(resyncSettings).not.toHaveBeenCalled();
      expect(sink.resynced).not.toHaveBeenCalled();
      expect(sink.forceReadOnly).not.toHaveBeenCalled();
    });

    it("invalid drops the pending patch and reports error without a resync", async () => {
      const { sink, queue } = setup();
      const { section, pending } = controlledSection();

      queue.enqueue({ section, patch: { a: 1 } });
      await settle();
      queue.enqueue({ section, patch: { b: 1 } });
      pending[0].resolve({ outcome: "invalid" });
      await settle();

      expect(sink.report).toHaveBeenLastCalledWith({
        sectionId: section.id,
        utubID: UTUB_ID,
        status: "error",
      });
      expect(resyncSettings).not.toHaveBeenCalled();
      expect(section.save).toHaveBeenCalledTimes(1);
    });

    it("releases the lane and busy flag when the sink throws on saving", async () => {
      const sink = makeSink({
        report: vi.fn(({ status }: { status: string }) => {
          if (status === "saving") throw new Error("sink boom");
        }),
      });
      const queue = createSaveQueue({ sink });
      const section = makeSection();

      queue.enqueue({ section, patch: { a: 1 } });
      await settle();

      expect(isPanelSettingsBusy()).toBe(false);
      expect(queue.hasWork({ sectionId: section.id })).toBe(false);

      // The lane is free again: a later submit is sent.
      queue.enqueue({ section, patch: { b: 1 } });
      await settle();
      expect(sink.report).toHaveBeenCalledTimes(2);
    });

    it("a thrown save is treated as an error outcome", async () => {
      const { sink, queue } = setup();
      const section = makeSection({
        save: vi.fn(async () => {
          throw new Error("boom");
        }),
      });

      queue.enqueue({ section, patch: { a: 1 } });
      await settle();

      expect(sink.report).toHaveBeenLastCalledWith({
        sectionId: section.id,
        utubID: UTUB_ID,
        status: "error",
      });
      expect(isPanelSettingsBusy()).toBe(false);
    });

    it.each(["locked", "forbidden"] as const)(
      "%s flips read-only, drops every scope-utub pending patch of the UTub and converges the store once",
      async (outcome) => {
        const { sink, queue } = setup();
        const { section, pending } = controlledSection({
          id: "a",
          panel: "urls",
        });
        const other = makeSection({ id: "b", panel: "tags" });
        const userSection = makeSection({
          id: "u",
          panel: "members",
          scope: "user",
          userKind: "global",
        });

        queue.enqueue({ section, patch: { a: 1 } });
        await settle();
        queue.enqueue({ section, patch: { more: 1 } });
        queue.enqueue({ section: other, patch: { b: 1 }, debounce: true });
        queue.enqueue({
          section: userSection,
          patch: { c: 1 },
          debounce: true,
        });
        pending[0].resolve({ outcome });
        await settle();

        expect(sink.forceReadOnly).toHaveBeenCalledWith({
          reason: outcome,
          utubID: UTUB_ID,
        });
        expect(updateUTubOnFindingStaleData).toHaveBeenCalledTimes(1);
        expect(updateUTubOnFindingStaleData).toHaveBeenCalledWith({
          utubID: UTUB_ID,
        });
        await vi.advanceTimersByTimeAsync(DEBOUNCE_MS * 2);
        expect(section.save).toHaveBeenCalledTimes(1);
        expect(other.save).not.toHaveBeenCalled();
        expect(userSection.save).toHaveBeenCalledTimes(1);
      },
    );

    it("does not call updateUTubOnFindingStaleData for any other outcome", async () => {
      const { queue } = setup();
      for (const outcome of ["ok", "error", "invalid"] as const) {
        const section = makeSection({
          id: outcome,
          save: vi.fn(async () => ({ outcome })),
        });
        queue.enqueue({ section, patch: { a: 1 } });
        await settle();
      }
      expect(updateUTubOnFindingStaleData).not.toHaveBeenCalled();
    });

    it("gone discards every pending patch for the UTub and reports nothing", async () => {
      const { sink, queue } = setup();
      const { section, pending } = controlledSection({
        id: "a",
        panel: "urls",
      });
      const other = makeSection({ id: "b", panel: "tags" });

      queue.enqueue({ section, patch: { a: 1 } });
      await settle();
      queue.enqueue({ section: other, patch: { b: 1 }, debounce: true });
      sink.report.mockClear();
      pending[0].resolve({ outcome: "gone" });
      await settle();
      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS * 2);

      expect(sink.report).not.toHaveBeenCalled();
      expect(other.save).not.toHaveBeenCalled();
      expect(isPanelSettingsBusy()).toBe(false);
    });

    it("stale keeps the pending patch and sends it to its captured UTub", async () => {
      const { sink, queue } = setup();
      const { section, pending } = controlledSection();

      queue.enqueue({ section, patch: { a: 1 } });
      await settle();
      queue.enqueue({ section, patch: { b: 1 } });
      sink.report.mockClear();
      pending[0].resolve({ outcome: "stale", failed: false });
      await settle();

      expect(sink.report).toHaveBeenCalledTimes(1);
      expect(sink.report).toHaveBeenCalledWith({
        sectionId: section.id,
        utubID: UTUB_ID,
        status: "saving",
      });
      expect(sink.announce).not.toHaveBeenCalled();
      expect(resyncSettings).not.toHaveBeenCalled();
      expect(saveCalls(section)[1]).toEqual({
        utubID: UTUB_ID,
        patch: { b: 1 },
      });
    });

    it("stale with failed:true only announces", async () => {
      const { sink, queue } = setup();
      const { section, pending } = controlledSection({ title: "URL sort" });

      queue.enqueue({ section, patch: { a: 1 } });
      await settle();
      pending[0].resolve({ outcome: "stale", failed: true });
      await settle();

      expect(sink.announce).toHaveBeenCalledWith({
        sectionId: section.id,
        utubID: UTUB_ID,
        message: "URL sort: Couldn't save",
      });
      expect(sink.report).not.toHaveBeenCalledWith(
        expect.objectContaining({ status: "error" }),
      );
      expect(sink.forceReadOnly).not.toHaveBeenCalled();
      expect(resyncSettings).not.toHaveBeenCalled();
    });
  });

  describe("enqueue write gate", () => {
    it("drops a submit when canWriteSection is false", async () => {
      setState({ isCurrentUserOwner: false, isCoCreator: false });
      const { sink, queue } = setup();
      const section = makeSection();

      queue.enqueue({ section, patch: { a: 1 } });
      await settle();

      expect(section.save).not.toHaveBeenCalled();
      expect(sink.report).not.toHaveBeenCalled();
      expect(queue.hasWork({ sectionId: section.id })).toBe(false);
    });

    it("drops a submit for a locked UTub", async () => {
      setState({ isCurrentUTubLocked: true });
      const { queue } = setup();
      const section = makeSection();

      queue.enqueue({ section, patch: { a: 1 } });
      await settle();

      expect(section.save).not.toHaveBeenCalled();
    });

    it("drops a scope-utub submit while forced read-only but not a user-scope one", async () => {
      const sink = makeSink({ isForcedReadOnly: vi.fn(() => true) });
      const queue = createSaveQueue({ sink });
      const utubSection = makeSection();
      const userSection = makeSection({
        id: "user",
        panel: "utubs",
        scope: "user",
        userKind: "global",
      });

      queue.enqueue({ section: utubSection, patch: { a: 1 } });
      queue.enqueue({ section: userSection, patch: { a: 1 } });
      await settle();

      expect(utubSection.save).not.toHaveBeenCalled();
      expect(userSection.save).toHaveBeenCalledTimes(1);
    });

    it("drops a UTub-captured submit when there is no active UTub", async () => {
      setState({ activeUTubID: null });
      const { queue } = setup();
      const section = makeSection();

      queue.enqueue({ section, patch: { a: 1 } });
      await settle();

      expect(section.save).not.toHaveBeenCalled();
      expect(isPanelSettingsBusy()).toBe(false);
    });
  });

  describe("dropUTub", () => {
    it("discards pending and debouncing patches of that UTub only", async () => {
      const { queue } = setup();
      const utubSection = makeSection({ id: "utub" });
      const perUtub = makeSection({
        id: "per",
        panel: "members",
        scope: "user",
        userKind: "per-utub",
      });
      const globalSection = makeSection({
        id: "glob",
        panel: "utubs",
        scope: "user",
        userKind: "global",
      });
      const otherUTub = makeSection({ id: "other", panel: "tags" });

      queue.enqueue({ section: otherUTub, patch: { x: 1 }, debounce: true });
      setState({ activeUTubID: 8 });
      queue.dropUTub({ utubID: UTUB_ID });
      // Keys captured for UTub 7 are gone; queue them under UTub 8 for contrast.
      queue.enqueue({ section: utubSection, patch: { a: 1 }, debounce: true });
      queue.enqueue({ section: perUtub, patch: { a: 1 }, debounce: true });
      queue.enqueue({
        section: globalSection,
        patch: { a: 1 },
        debounce: true,
      });
      queue.dropUTub({ utubID: 8 });
      queue.flush({});
      await settle();
      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS * 2);

      expect(otherUTub.save).not.toHaveBeenCalled();
      expect(utubSection.save).not.toHaveBeenCalled();
      expect(perUtub.save).not.toHaveBeenCalled();
      expect(globalSection.save).toHaveBeenCalledTimes(1);
    });

    it("keeps other UTubs' keys", async () => {
      const { queue } = setup();
      const keep = makeSection({ id: "keep", panel: "urls" });
      const drop = makeSection({ id: "drop", panel: "tags" });

      queue.enqueue({ section: drop, patch: { a: 1 }, debounce: true });
      setState({ activeUTubID: 8 });
      queue.enqueue({ section: keep, patch: { a: 1 }, debounce: true });
      queue.dropUTub({ utubID: UTUB_ID });
      queue.flush({});
      await settle();

      expect(drop.save).not.toHaveBeenCalled();
      expect(saveCalls(keep)).toEqual([{ utubID: 8, patch: { a: 1 } }]);
    });
  });

  describe("busy flag and hasWork", () => {
    it("is true while pending, debouncing or in flight and false after every outcome", async () => {
      const outcomes: SaveResult[] = [
        { outcome: "ok" },
        { outcome: "error" },
        { outcome: "invalid" },
        { outcome: "locked" },
        { outcome: "forbidden" },
        { outcome: "gone" },
        { outcome: "stale", failed: true },
      ];
      for (const result of outcomes) {
        const { queue } = setup();
        const { section, pending } = controlledSection({ id: result.outcome });

        queue.enqueue({ section, patch: { a: 1 }, debounce: true });
        expect(queue.hasWork({ sectionId: section.id })).toBe(true);
        expect(isPanelSettingsBusy()).toBe(true);

        await vi.advanceTimersByTimeAsync(DEBOUNCE_MS);
        expect(queue.hasWork({ sectionId: section.id })).toBe(true);

        pending[0].resolve(result);
        await settle();

        expect(queue.hasWork({ sectionId: section.id })).toBe(false);
        expect(isPanelSettingsBusy()).toBe(false);
      }
    });

    it("hasWork is scoped to the given section", async () => {
      const { queue } = setup();
      const section = makeSection();

      queue.enqueue({ section, patch: { a: 1 }, debounce: true });

      expect(queue.hasWork({ sectionId: "someone-else" })).toBe(false);
    });

    it("hasUnsentEdits counts queued and debouncing edits but not a save in flight", async () => {
      const { queue } = setup();
      const { section, pending } = controlledSection();

      queue.enqueue({ section, patch: { a: 1 }, debounce: true });
      expect(queue.hasUnsentEdits({ sectionId: section.id })).toBe(true);
      expect(queue.hasUnsentEdits({ sectionId: "someone-else" })).toBe(false);

      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS);
      // Now in flight: work, but nothing unsent.
      expect(queue.hasWork({ sectionId: section.id })).toBe(true);
      expect(queue.hasUnsentEdits({ sectionId: section.id })).toBe(false);

      // An edit made behind the in-flight save is unsent.
      queue.enqueue({ section, patch: { a: 2 } });
      expect(queue.hasUnsentEdits({ sectionId: section.id })).toBe(true);

      pending[0].resolve({ outcome: "ok" });
      await settle();
      pending[1].resolve({ outcome: "ok" });
      await settle();
      expect(queue.hasUnsentEdits({ sectionId: section.id })).toBe(false);
    });
  });
});
