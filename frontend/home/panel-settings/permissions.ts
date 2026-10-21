import type { AppState } from "../../store/app-store.js";
import type { PanelSection } from "./types.js";

/**
 * Effective write permission. Scope 'utub' needs a manager of an unlocked UTub;
 * scope 'user' is governed by the section's own scope. Fail closed: anything
 * else is denied.
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
      return (
        (state.isCurrentUserOwner || state.isCoCreator) &&
        !state.isCurrentUTubLocked
      );
    case "user":
      return true;
    default:
      return false;
  }
}
