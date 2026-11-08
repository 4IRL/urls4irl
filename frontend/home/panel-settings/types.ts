// Contract types for the panel settings shell. Phases 4-7 author sections
// against these and may not edit the shell, except for additive extensions
// (URLs panel phases): an optional `notice` on a saved result, folded into the
// single "Saved" announcement, and an optional `rerenderOn` selector list on a
// per-utub user section, which the shell diffs to know when to re-render it;
// and, on a section, an optional `writeAccess` ("manager" | "owner", scope
// 'utub' only) and `visibleTo` ("all" | "managers"), both failing closed.
import type { AppState } from "../../store/app-store.js";
import type {
  PanelId,
  SettingsScope,
  UtubSettings,
} from "../../types/settings.js";

/** A section's partial settings object (one panel key per PATCH body for scope 'utub'). */
export type SectionPatch = Record<string, unknown>;

export type SaveResult =
  | { outcome: "ok"; settings?: UtubSettings; notice?: string }
  | { outcome: "stale"; failed: boolean; notice?: string }
  | { outcome: "error"; resync?: boolean; notice?: string }
  | { outcome: "locked" | "forbidden" | "gone" | "invalid" };

export interface SectionContext {
  /** UTub slice's last-saved value for scope 'utub'; null for scope 'user'. */
  settings: UtubSettings | null;
  canWrite: boolean;
  /**
   * Scope 'utub' only. Id of the read-only note element; the section's render
   * adds it to its controls' aria-describedby.
   */
  readOnlyNoteId?: string;
  submit({
    patch,
    debounce,
  }: {
    patch: SectionPatch;
    debounce?: boolean;
  }): void;
}

export type UserKind = "global" | "per-utub";

/** Who may write a scope 'utub' section; absent means "manager". */
export type WriteAccess = "manager" | "owner";

/** Who sees a section; absent means "all". */
export type SectionVisibility = "all" | "managers";

export interface PanelSection {
  id: string;
  panel: PanelId;
  title: string;
  scope: SettingsScope;
  /** Required for scope 'user'. */
  userKind?: UserKind;
  /** Scope 'utub' only; absent means "manager". */
  writeAccess?: WriteAccess;
  /** Absent means "all". */
  visibleTo?: SectionVisibility;
  /**
   * Scope 'user', userKind 'per-utub' only: selectors for the store values the
   * render depends on. The shell re-renders the section (when idle) whenever
   * their results change from those taken at the last render.
   */
  rerenderOn?: Array<(state: AppState) => unknown>;
  render({
    container,
    ctx,
  }: {
    container: HTMLElement;
    ctx: SectionContext;
  }): void | (() => void);
  save({
    utubID,
    patch,
  }: {
    utubID: number | null;
    patch: SectionPatch;
  }): Promise<SaveResult>;
}

export type SaveStatus = "saving" | "saved" | "error";

/** The queue's only outlet to the popover layer (implemented by the popover layer, popover.ts). */
export interface QueueSink {
  // `utubID` is the UTub the save was captured for (null for a global user
  // section), so a late outcome never lands on a popover opened for another UTub.
  report({
    sectionId,
    utubID,
    status,
    savedPatch,
    notice,
  }: {
    sectionId: string;
    utubID: number | null;
    status: SaveStatus;
    savedPatch?: SectionPatch;
    notice?: string;
  }): void;
  // `writeAccess` is the refused section's class; it scopes a "forbidden" force.
  forceReadOnly({
    reason,
    utubID,
    writeAccess,
  }: {
    reason: "locked" | "forbidden";
    utubID: number | null;
    writeAccess: WriteAccess;
  }): void;
  announce({
    sectionId,
    utubID,
    message,
  }: {
    sectionId: string;
    utubID: number | null;
    message: string;
  }): void;
  resynced({
    sectionId,
    utubID,
  }: {
    sectionId: string;
    utubID: number | null;
  }): void;
  isForcedReadOnly({ section }: { section: PanelSection }): boolean;
}
