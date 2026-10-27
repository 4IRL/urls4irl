import { APP_CONFIG } from "../../lib/config.js";
import { debug } from "../../lib/debug.js";
import { getState } from "../../store/app-store.js";
import { updateUTubOnFindingStaleData } from "../utubs/stale-data.js";
import {
  handleActiveUTubGone,
  resyncMemberSettings,
  resyncSettings,
} from "./client.js";
import { canWriteSection } from "./permissions.js";
import { setPanelSettingsPendingSaveCount } from "./state.js";
import type {
  PanelSection,
  QueueSink,
  SaveResult,
  SectionPatch,
} from "./types.js";

const log = debug("panel-settings");

export const DEBOUNCE_MS = 300;

interface KeyState {
  keyName: string;
  section: PanelSection;
  /** Captured at submit time; null for 'global' user sections. */
  utubID: number | null;
  pending: SectionPatch | null;
  timer: ReturnType<typeof setTimeout> | null;
  inFlight: boolean;
  /** True while the key sits in the sendable FIFO. */
  queued: boolean;
}

export interface SaveQueue {
  enqueue({
    section,
    patch,
    debounce,
  }: {
    section: PanelSection;
    patch: SectionPatch;
    debounce?: boolean;
  }): void;
  flush({ sectionId }: { sectionId?: string }): void;
  hasWork({ sectionId }: { sectionId: string }): boolean;
  /**
   * Unsent edits only (queued or debouncing), not a save in flight. A resync
   * runs inside the failed save's own in-flight window, so `resynced` cannot use
   * `hasWork`, which that very save would make true.
   */
  hasUnsentEdits({ sectionId }: { sectionId: string }): boolean;
  dropUTub({ utubID }: { utubID: number }): void;
}

function capturesUTub({ section }: { section: PanelSection }): boolean {
  return (
    section.scope === "utub" ||
    (section.scope === "user" && section.userKind === "per-utub")
  );
}

function keyNameOf({
  section,
  utubID,
}: {
  section: PanelSection;
  utubID: number | null;
}): string {
  return utubID === null ? section.id : `${section.id}|${utubID}`;
}

// At most one save in flight per lane: the panel + UTub for scope 'utub' (so
// same-panel responses arrive in commit order), the key itself for user scope.
function laneOf({ state }: { state: KeyState }): string {
  return state.section.scope === "utub"
    ? `${state.section.panel}|${state.utubID}`
    : state.keyName;
}

export function createSaveQueue({ sink }: { sink: QueueSink }): SaveQueue {
  const keys = new Map<string, KeyState>();
  const lanesInFlight = new Set<string>();
  let sendable: KeyState[] = [];

  function hasKeyWork({ state }: { state: KeyState }): boolean {
    return state.pending !== null || state.timer !== null || state.inFlight;
  }

  // Drops idle keys and mirrors the number of busy keys into the busy flag.
  function refreshBusy(): void {
    for (const [keyName, state] of keys) {
      if (!hasKeyWork({ state })) keys.delete(keyName);
    }
    setPanelSettingsPendingSaveCount({ count: keys.size });
  }

  function cancelTimer({ state }: { state: KeyState }): void {
    if (state.timer !== null) {
      clearTimeout(state.timer);
      state.timer = null;
    }
  }

  function dropPending({ state }: { state: KeyState }): void {
    cancelTimer({ state });
    state.pending = null;
    state.queued = false;
    sendable = sendable.filter((queuedState) => queuedState !== state);
  }

  function dropKeysForUTub({
    utubID,
    utubScopeOnly = false,
  }: {
    utubID: number;
    utubScopeOnly?: boolean;
  }): void {
    for (const state of keys.values()) {
      if (state.utubID !== utubID) continue;
      if (utubScopeOnly && state.section.scope !== "utub") continue;
      dropPending({ state });
    }
  }

  function markSendable({ state }: { state: KeyState }): void {
    if (state.pending === null || state.timer !== null || state.queued) return;
    state.queued = true;
    sendable.push(state);
  }

  function pump(): void {
    for (const state of [...sendable]) {
      const lane = laneOf({ state });
      if (lanesInFlight.has(lane)) continue;
      sendable = sendable.filter((queuedState) => queuedState !== state);
      state.queued = false;
      void send({ state, lane });
    }
  }

  async function send({
    state,
    lane,
  }: {
    state: KeyState;
    lane: string;
  }): Promise<void> {
    const patch = state.pending;
    if (patch === null) return;
    state.pending = null;
    state.inFlight = true;
    lanesInFlight.add(lane);

    try {
      sink.report({
        sectionId: state.section.id,
        utubID: state.utubID,
        status: "saving",
      });
      let result: SaveResult;
      try {
        result = await state.section.save({ utubID: state.utubID, patch });
      } catch (error) {
        log("save threw", { sectionId: state.section.id, error });
        result = { outcome: "error" };
      }
      await handleResult({ state, patch, result });
    } catch (error) {
      log("handling save result failed", {
        sectionId: state.section.id,
        error,
      });
    } finally {
      state.inFlight = false;
      lanesInFlight.delete(lane);
      refreshBusy();
      markSendable({ state });
      pump();
      refreshBusy();
    }
  }

  async function handleResult({
    state,
    patch,
    result: rawResult,
  }: {
    state: KeyState;
    patch: SectionPatch;
    result: SaveResult;
  }): Promise<void> {
    const { section, utubID } = state;
    const sectionId = section.id;
    const isUserScope = section.scope === "user";
    let result = rawResult;

    // A per-utub user section is not UTub-bound at the client: apply the stale
    // rule here.
    if (
      isUserScope &&
      section.userKind === "per-utub" &&
      result.outcome !== "stale" &&
      utubID !== getState().activeUTubID
    ) {
      result = { outcome: "stale", failed: result.outcome !== "ok" };
    }

    // A user endpoint's 403/404 says nothing about the UTub's lock or existence.
    if (isUserScope && result.outcome === "gone") {
      if (utubID !== null) {
        handleActiveUTubGone({ utubID });
        dropKeysForUTub({ utubID });
        return;
      }
      result = { outcome: "error" };
    } else if (
      isUserScope &&
      (result.outcome === "locked" || result.outcome === "forbidden")
    ) {
      result = { outcome: "error" };
    }

    switch (result.outcome) {
      case "ok":
        sink.report({
          sectionId,
          utubID,
          status: "saved",
          ...(section.scope === "utub" ? { savedPatch: patch } : {}),
          ...(result.notice ? { notice: result.notice } : {}),
        });
        return;
      case "error": {
        dropPending({ state });
        sink.report({ sectionId, utubID, status: "error" });
        if (
          (section.scope === "utub" ||
            (section.scope === "user" && section.userKind === "per-utub")) &&
          result.resync !== false
        ) {
          await resyncAfterError({ section, utubID });
        }
        return;
      }
      case "invalid":
        dropPending({ state });
        sink.report({ sectionId, utubID, status: "error" });
        return;
      case "forbidden":
      case "locked": {
        if (utubID === null) return;
        dropKeysForUTub({ utubID, utubScopeOnly: true });
        sink.forceReadOnly({ reason: result.outcome, utubID });
        updateUTubOnFindingStaleData({ utubID }).catch((error: unknown) => {
          log("convergence refresh failed", { utubID, error });
        });
        return;
      }
      case "gone":
        // The client already ran the UTub-removed handling.
        if (utubID !== null) dropKeysForUTub({ utubID });
        return;
      case "stale":
        // Keep the pending patch: it still goes to its captured UTub.
        if (result.failed) {
          sink.announce({
            sectionId,
            utubID,
            message: `${section.title}: ${APP_CONFIG.strings.PANEL_SETTINGS_SAVE_FAILED}`,
          });
        }
        return;
      default:
        // Fail closed on an unhandled outcome.
        dropPending({ state });
        sink.report({ sectionId, utubID, status: "error" });
    }
  }

  // The server may have committed a timed-out or network-failed PATCH.
  async function resyncAfterError({
    section,
    utubID,
  }: {
    section: PanelSection;
    utubID: number | null;
  }): Promise<void> {
    if (utubID === null) return;
    const resynced =
      section.scope === "user"
        ? await resyncMemberSettings({ utubID })
        : await resyncSettings({ utubID });
    if (resynced) sink.resynced({ sectionId: section.id, utubID });
  }

  return {
    enqueue({ section, patch, debounce = false }) {
      let utubID: number | null = null;
      if (capturesUTub({ section })) {
        utubID = getState().activeUTubID;
        if (utubID === null) {
          log("enqueue — no active UTub, dropping", { sectionId: section.id });
          return;
        }
      }
      if (
        !canWriteSection({ section, state: getState() }) ||
        (section.scope === "utub" && sink.isForcedReadOnly())
      ) {
        log("enqueue — write not permitted, dropping", {
          sectionId: section.id,
        });
        return;
      }

      const keyName = keyNameOf({ section, utubID });
      let state = keys.get(keyName);
      if (!state) {
        state = {
          keyName,
          section,
          utubID,
          pending: null,
          timer: null,
          inFlight: false,
          queued: false,
        };
        keys.set(keyName, state);
      }
      state.pending = { ...state.pending, ...patch };
      cancelTimer({ state });

      if (debounce) {
        const debouncedState = state;
        debouncedState.timer = setTimeout(() => {
          debouncedState.timer = null;
          markSendable({ state: debouncedState });
          pump();
        }, DEBOUNCE_MS);
      } else {
        markSendable({ state });
      }
      refreshBusy();
      pump();
    },

    flush({ sectionId }) {
      for (const state of keys.values()) {
        if (sectionId !== undefined && state.section.id !== sectionId) continue;
        if (state.pending === null) continue;
        cancelTimer({ state });
        markSendable({ state });
      }
      pump();
    },

    hasWork({ sectionId }) {
      for (const state of keys.values()) {
        if (state.section.id === sectionId && hasKeyWork({ state })) {
          return true;
        }
      }
      return false;
    },

    hasUnsentEdits({ sectionId }) {
      for (const state of keys.values()) {
        if (
          state.section.id === sectionId &&
          (state.pending !== null || state.timer !== null)
        ) {
          return true;
        }
      }
      return false;
    },

    dropUTub({ utubID }) {
      dropKeysForUTub({ utubID });
      refreshBusy();
    },
  };
}
