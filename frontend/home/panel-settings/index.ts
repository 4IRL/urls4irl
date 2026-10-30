import { initPopover } from "./popover.js";

export { rerenderSectionIfIdle } from "./popover.js";
export { registerSection } from "./registry.js";
export { isPanelSettingsBusy, isPanelSettingsOpen } from "./state.js";

/**
 * Initialize the panel settings shell: gears, popover surface, save queue and
 * every close trigger. Sections register themselves independently (before or
 * after this runs); the final pass inside reveals gears for early registrations.
 */
export function initPanelSettings(): void {
  initPopover();
}
