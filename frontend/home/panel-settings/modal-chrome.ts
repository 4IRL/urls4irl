// Modal chrome shared by the panel settings surfaces (desktop dialog and mobile
// sheet): the inert background and the dimming backdrop. It sits below both
// surfaces and never imports popover.ts or sheet.ts.

const ROOT_SELECTOR = "#panelSettingsRoot";
const BACKDROP_SELECTOR = "#panelSettingsBackdrop";

const HIDDEN_CLASS = "hidden";
const BACKDROP_SHOW_CLASS = "panelSettingsBackdrop--show";
const INERT_ATTRIBUTE = "inert";
const NON_INERT_TAGS: ReadonlySet<string> = new Set([
  "SCRIPT",
  "STYLE",
  "TEMPLATE",
]);

interface InertRecord {
  element: Element;
  wasInert: boolean;
}

let _inertRecords: InertRecord[] = [];

function backdropElement(): HTMLElement | null {
  return document.querySelector<HTMLElement>(BACKDROP_SELECTOR);
}

/** Inerts every body child except the settings root; idempotent while applied. */
export function applyInert(): void {
  const root = document.querySelector<HTMLElement>(ROOT_SELECTOR);
  if (_inertRecords.length > 0) return;
  for (const child of Array.from(document.body.children)) {
    if (child === root || NON_INERT_TAGS.has(child.tagName)) continue;
    _inertRecords.push({
      element: child,
      wasInert: child.hasAttribute(INERT_ATTRIBUTE),
    });
    child.setAttribute(INERT_ATTRIBUTE, "");
  }
}

/** Reverse order of application: restores exactly each element's prior state. */
export function restoreInert(): void {
  for (const record of _inertRecords.reverse()) {
    if (record.wasInert) {
      record.element.setAttribute(INERT_ATTRIBUTE, "");
    } else {
      record.element.removeAttribute(INERT_ATTRIBUTE);
    }
  }
  _inertRecords = [];
}

/** Un-hides the backdrop, commits a reflow, then fades it in. */
export function showBackdrop(): void {
  const backdrop = backdropElement();
  if (backdrop === null) return;
  backdrop.classList.remove(HIDDEN_CLASS);
  void backdrop.offsetHeight;
  backdrop.classList.add(BACKDROP_SHOW_CLASS);
}

export function hideBackdrop(): void {
  const backdrop = backdropElement();
  backdrop?.classList.remove(BACKDROP_SHOW_CLASS);
  backdrop?.classList.add(HIDDEN_CLASS);
}
