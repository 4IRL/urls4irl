const REVEAL_SELECTOR = ".reveal-on-scroll";
const REVEALED_CLASS = "is-revealed";
const REVEAL_THRESHOLD = 0.15;
const REVEAL_ROOT_MARGIN = "0px 0px -10% 0px";

/**
 * Reveals marketing elements as they scroll into view by toggling a class that
 * drives a CSS opacity + translateY transition. Each `.reveal-on-scroll` element
 * is revealed once, then unobserved.
 *
 * Honors `prefers-reduced-motion: reduce` and missing IntersectionObserver
 * support by revealing every target immediately (no animation, no observer), so
 * the content is never left hidden.
 */
export function initScrollReveal(): void {
  const targets = Array.from(
    document.querySelectorAll<HTMLElement>(REVEAL_SELECTOR),
  );
  if (targets.length === 0) return;

  const prefersReducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)",
  ).matches;

  if (prefersReducedMotion || typeof IntersectionObserver === "undefined") {
    targets.forEach((target) => target.classList.add(REVEALED_CLASS));
    return;
  }

  const observer = new IntersectionObserver(
    (entries, activeObserver) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add(REVEALED_CLASS);
        activeObserver.unobserve(entry.target);
      });
    },
    { threshold: REVEAL_THRESHOLD, rootMargin: REVEAL_ROOT_MARGIN },
  );

  targets.forEach((target) => observer.observe(target));
}
