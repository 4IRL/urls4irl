const REVEAL_SELECTOR = ".reveal-on-scroll";
const REVEALED_CLASS = "is-revealed";
// Reveal as soon as any part of a target enters the viewport. A positive
// threshold or a negative bottom rootMargin would leave elements that sit in
// the lower edge of the first screen visible-but-unrevealed (a blank gap on
// load), so detect against the full viewport with a zero threshold.
const REVEAL_THRESHOLD = 0;
const REVEAL_ROOT_MARGIN = "0px";

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
