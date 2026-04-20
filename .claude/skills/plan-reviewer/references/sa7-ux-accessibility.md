# Subagent 7: UX, Accessibility & Edge Cases

**Role:** Review the plan from the user's perspective — what happens when someone actually uses this feature, including edge cases, accessibility, cross-feature interactions, and mobile behavior.

**Skip condition:** If the plan has no UI/frontend changes, return PASS with empty findings.

**What to read:** The full plan, plus:
- HTML templates for the affected page/view — identify every existing interactive element
- All JS/TS modules loaded on the same page — identify event listeners, keyboard bindings, show/hide logic
- CSS files for the affected area — identify responsive breakpoints, hover/focus styles, touch target sizes
- Existing accessibility attributes (`aria-*`, `role`, `tabindex`) in affected templates

**Review checklist:**

## 1. Cross-Feature Interaction Conflicts (required for any plan adding/modifying UI features)

For every interactive feature the plan adds or modifies, identify ALL other interactive features on the same page. Then check each pair for conflicts:

- **Visibility conflicts**: Does the new feature hide/show elements that another feature depends on? (e.g., search filtering hides a selected card, keyboard nav targets a hidden element). Flag as **Major** if the plan doesn't handle the conflict.
- **Keyboard binding conflicts**: Does the new feature bind a key (Escape, Enter, arrow keys) that another feature also binds on the same page? Flag as **Major** if precedence/propagation isn't specified.
- **State conflicts**: Does the new feature change state that another feature reads? (e.g., filtering changes visible item count that keyboard nav uses for wrap-around). Flag as **Major** if not addressed.
- **Mutual exclusion**: Can two features be active simultaneously when they shouldn't be? (e.g., editing a title while search panel is open). Flag as **Major** if the plan doesn't specify disable/re-enable behavior.

## 2. Accessibility (required for any plan adding interactive elements)

For each interactive element the plan adds:

- **Keyboard operability (WCAG 2.1.1)**: Can the element be reached via Tab and activated via Enter/Space? If a non-button element is made interactive, does the plan add `role="button"`, `tabindex="0"`, and keydown handlers? Flag as **Major** if missing.
- **ARIA labels (WCAG 4.1.2)**: Does each input have `aria-label` or `<label>`? Do custom controls have appropriate `role` attributes? Flag as **Minor** if missing.
- **Dynamic content announcements (WCAG 4.1.3)**: When the feature dynamically changes visible content (filter results, error messages, status changes), is there an `aria-live` region to announce changes to screen readers? Flag as **Minor** if missing.
- **Focus management**: After opening/closing interactive widgets (panels, modals, edit forms), does the plan specify where focus moves? Does focus return to the triggering element on close? Flag as **Major** if unspecified for modal-like interactions.
- **Focus visibility (WCAG 2.4.7)**: Do new interactive elements have `:focus-visible` styles? Flag as **Minor** if missing.

## 3. Empty & Error States (required for any feature that filters/hides content)

- **Zero results state**: When the feature hides all content (search returns no matches, filter excludes everything), does the plan specify what the user sees? A blank area with no message is a UX bug. Flag as **Major** if missing.
- **Distinct empty states**: Is the "no results from search/filter" state visually and textually distinct from the "no content exists" state? Flag as **Minor** if ambiguous.
- **Edge input**: Does the plan handle whitespace-only input, very long input, special characters? Flag as **Minor** if not addressed.

## 4. Input Performance (required for any text input triggering DOM manipulation)

- **Debouncing**: Does the plan debounce text input that triggers filtering, search, or DOM updates? Keystroke-by-keystroke DOM manipulation causes jank. Flag as **Major** if missing.
- **Timer cleanup**: If debounce is specified, does the plan clean up timers on close/unmount/Escape? Orphaned timers cause stale state. Flag as **Minor** if missing.

## 5. Discoverability & Visual Affordances

- **Hidden interactivity**: If the plan makes an element interactive without a visible affordance (e.g., clickable header without icon or cursor change), does it add a visual cue? Flag as **Major** — users won't discover the feature.
- **Device-specific affordances**: Do hover-dependent affordances (pencil icon on hover) have mobile equivalents (persistent icon)? Flag as **Minor** if mobile not addressed.

## 6. Mobile & Touch Concerns

- **Touch targets**: Are interactive elements at least 44px on mobile? The plan should specify `min-height`/`min-width` with responsive media queries if default sizes are smaller. Flag as **Minor** if not addressed.
- **Soft keyboard**: Does the plan's text input interact with mobile soft keyboards? Does viewport shift break layout? Flag as **Minor** if not considered.
- **Hover-dependent behavior**: Do hover-triggered interactions (tooltips, icon reveals, hover states) have touch equivalents? Flag as **Minor** if not addressed.

## 7. Behavioral Consistency

- **Event type consistency**: If similar features use `keydown` vs `keyup` for the same key (e.g., Escape), does the new feature match the established pattern? Inconsistency causes subtle bugs (e.g., keyup fires after focus has already moved). Flag as **Minor** if inconsistent.
- **Animation/transition consistency**: Do open/close animations match the patterns used by similar features on the same page? Flag as **Minor** if inconsistent.

## 8. Adversarial User Scenarios

Think like a QA tester trying to break the feature. Common scenarios to check:

- **Rapid toggling**: Open/close the feature quickly — does state get corrupted?
- **Mid-action interruption**: Start using the feature, then trigger another feature (e.g., start typing in search, then click to edit title) — is the transition clean?
- **Concurrent feature activation**: Activate multiple features that weren't designed to coexist — does the plan handle this or explicitly prevent it?
- **Text selection vs. click**: If an element is clickable, does clicking to select text accidentally trigger the action? Does the plan distinguish between click-to-activate and click-to-select?
