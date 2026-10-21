import { emit, AppEvents } from "../../lib/event-bus.js";
import { debug } from "../../lib/debug.js";
import type { PanelId } from "../../types/settings.js";
import type { PanelSection } from "./types.js";

const log = debug("panel-settings");

// Mirrors the PanelId union; a panel outside it is rejected (fail closed).
// `satisfies Record<PanelId, true>` is the compile-time drift guard: adding a
// PanelId member without a key here (or keeping a removed one) fails typecheck.
const PANEL_ID_SET = {
  utubs: true,
  members: true,
  tags: true,
  urls: true,
} as const satisfies Record<PanelId, true>;
const KNOWN_PANELS: readonly PanelId[] = Object.keys(PANEL_ID_SET) as PanelId[];

/** Narrowing guard for a raw string (e.g. a gear's `data-panel`). */
export function isKnownPanel(value: string | undefined): value is PanelId {
  return KNOWN_PANELS.some((panel) => panel === value);
}

let _sections: PanelSection[] = [];

// Fail closed: every rejection returns a reason; null means the section is valid.
function validationError({
  section,
}: {
  section: PanelSection;
}): string | null {
  if (typeof section.id !== "string" || section.id === "") {
    return "id must be a non-empty string";
  }
  if (section.id.includes("|")) {
    return "id must not contain '|' (queue key separator)";
  }
  if (!KNOWN_PANELS.includes(section.panel)) {
    return "unknown panel";
  }
  if (section.scope !== "utub" && section.scope !== "user") {
    return "unknown scope";
  }
  if (section.scope === "user") {
    if (section.userKind !== "global" && section.userKind !== "per-utub") {
      return "scope 'user' requires userKind 'global' or 'per-utub'";
    }
    if (section.panel === "utubs" && section.userKind === "per-utub") {
      return "userKind 'per-utub' is not allowed on the utubs panel";
    }
  }
  if (section.scope === "utub" && section.panel === "utubs") {
    return "scope 'utub' is not allowed on the utubs panel";
  }
  if (_sections.some((existing) => existing.id === section.id)) {
    return "duplicate section id";
  }
  return null;
}

/** Registers a section; returns an unregister fn (a no-op when rejected). */
export function registerSection(section: PanelSection): () => void {
  const error = validationError({ section });
  if (error !== null) {
    log("registerSection — rejected", { id: section?.id, reason: error });
    return () => {};
  }

  _sections = [..._sections, section];
  emit(AppEvents.PANEL_SETTINGS_SECTIONS_CHANGED);

  // Per-registration flag: a stale unregister must not remove a later
  // re-registration of the same section object.
  let registered = true;
  return () => {
    if (!registered) return;
    registered = false;
    _sections = _sections.filter((existing) => existing !== section);
    emit(AppEvents.PANEL_SETTINGS_SECTIONS_CHANGED);
  };
}

/** Sections registered for a panel, in registration (render) order. */
export function getSections(panel: PanelId): PanelSection[] {
  return _sections.filter((section) => section.panel === panel);
}

export function _resetRegistryForTests(): void {
  _sections = [];
}
