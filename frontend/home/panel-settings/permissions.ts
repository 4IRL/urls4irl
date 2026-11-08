import type { AppState } from "../../store/app-store.js";
import type { PanelSection } from "./types.js";

/**
 * Effective write permission. Scope 'utub' needs a manager (or, for a section
 * declaring `writeAccess: "owner"`, the owner) of an unlocked UTub; scope 'user'
 * is governed by the section's own scope. Fail closed: anything else is denied.
 */
export function canWriteSection({
  section,
  state,
}: {
  section: PanelSection;
  state: AppState;
}): boolean {
  switch (section.scope) {
    case "utub":
      switch (section.writeAccess ?? "manager") {
        case "manager":
          return (
            (state.isCurrentUserOwner || state.isCoCreator) &&
            !state.isCurrentUTubLocked
          );
        case "owner":
          return state.isCurrentUserOwner && !state.isCurrentUTubLocked;
        default:
          return false;
      }
    case "user":
      return true;
    default:
      return false;
  }
}

/** Whether the viewer's role may see the section at all. Fail closed. */
export function isSectionVisible({
  section,
  state,
}: {
  section: PanelSection;
  state: AppState;
}): boolean {
  switch (section.visibleTo ?? "all") {
    case "all":
      return true;
    case "managers":
      return state.isCurrentUserOwner || state.isCoCreator;
    default:
      return false;
  }
}
