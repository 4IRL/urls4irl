/**
 * Roving-tabindex keyboard navigation for the admin portal section nav
 * (#AdminNav), matching the interaction model of the metrics dashboard
 * tablist (see metrics-dashboard.ts handleTabKeydown):
 *   - Left/Right cycle through the nav links with wrap-around
 *   - Home/End jump to the first/last link
 *   - a single link holds tabindex="0" (the active section, or the first link
 *     when none is active); the rest are tabindex="-1", so Tab enters/exits
 *     the nav as one stop and arrow keys move focus within it
 *
 * The links remain real <a href> elements: Enter/click navigate natively, so
 * this is a progressive enhancement — without JS every link stays tabbable.
 *
 * Returns a disposer that unbinds the keydown handler (page code ignores it;
 * tests use it to avoid handlers accumulating across cases).
 */

import { $ } from "../lib/globals.js";

export const NAV_LINK_SELECTOR = "#AdminNav .admin-nav-link";
export const NAV_KEYDOWN_NAMESPACE = "keydown.adminNavKeyboard";
const ACTIVE_LINK_CLASS = "active";

function setRovingFocus({
  links,
  activeIndex,
}: {
  links: HTMLAnchorElement[];
  activeIndex: number;
}): void {
  links.forEach((link, index) => {
    link.setAttribute("tabindex", index === activeIndex ? "0" : "-1");
  });
}

export function initAdminNavKeyboard(): () => void {
  const links = Array.from(
    document.querySelectorAll<HTMLAnchorElement>(NAV_LINK_SELECTOR),
  );
  if (links.length === 0) {
    return () => {};
  }

  const activeIndex = links.findIndex((link) =>
    link.classList.contains(ACTIVE_LINK_CLASS),
  );
  setRovingFocus({ links, activeIndex: activeIndex === -1 ? 0 : activeIndex });

  function handleNavKeydown(event: JQuery.TriggeredEvent): void {
    const key = event.key as string | undefined;
    if (
      key !== "ArrowLeft" &&
      key !== "ArrowRight" &&
      key !== "Home" &&
      key !== "End"
    ) {
      return;
    }

    const currentIndex = links.indexOf(
      event.currentTarget as HTMLAnchorElement,
    );
    if (currentIndex === -1) {
      return;
    }

    let nextIndex: number;
    if (key === "ArrowLeft") {
      nextIndex = (currentIndex - 1 + links.length) % links.length;
    } else if (key === "ArrowRight") {
      nextIndex = (currentIndex + 1) % links.length;
    } else if (key === "Home") {
      nextIndex = 0;
    } else {
      nextIndex = links.length - 1;
    }

    event.preventDefault();
    setRovingFocus({ links, activeIndex: nextIndex });
    links[nextIndex].focus();
  }

  $(NAV_LINK_SELECTOR).offAndOnExact(NAV_KEYDOWN_NAMESPACE, handleNavKeydown);

  return () => {
    $(NAV_LINK_SELECTOR).off(NAV_KEYDOWN_NAMESPACE);
  };
}
