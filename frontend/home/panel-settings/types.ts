// Contract types for the panel settings shell. Phases 4-7 author sections
// against these and may not edit the shell, except for one additive extension
// (URLs panel phase): an optional `notice` on a saved result, folded into the
// single "Saved" announcement.
import type {
  PanelId,
  SettingsScope,
  UtubSettings,
} from "../../types/settings.js";

/** A section's partial settings object (one panel key per PATCH body for scope 'utub'). */
export type SectionPatch = Record<string, unknown>;

export type SaveResult =
  | { outcome: "ok"; settings?: UtubSettings; notice?: string }
  | { outcome: "stale"; failed: boolean }
  | { outcome: "error"; resync?: boolean }
  | { outcome: "locked" | "forbidden" | "gone" | "invalid" };

export interface SectionContext {
  /** UTub slice's last-saved value for scope 'utub'; null for scope 'user'. */
  settings: UtubSettings | null;
  canWrite: boolean;
  submit({
    patch,
    debounce,
  }: {
    patch: SectionPatch;
    debounce?: boolean;
  }): void;
}

export type UserKind = "global" | "per-utub";

export interface PanelSection {
  id: string;
  panel: PanelId;
  title: string;
  scope: SettingsScope;
  /** Required for scope 'user'. */
  userKind?: UserKind;
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
  forceReadOnly({
    reason,
    utubID,
  }: {
    reason: "locked" | "forbidden";
    utubID: number | null;
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
  isForcedReadOnly(): boolean;
}
