import { getInputValue } from "../../../lib/globals.js";
import { flushParamTrim } from "../trim/param-trim-block.js";
import {
  getSchemeSelector,
  type SchemeSelectorHandle,
} from "./scheme-selector.js";
import { splitScheme } from "./scheme-utils.js";

// Leaf module (no card/panel imports) so the edit form, the dirty-state check and
// the Undo banner can all share one lookup without circular imports.

export const UPDATE_SCHEME_CONTAINER_SELECTOR =
  ".updateUrlStringWrap .text-input-container";

/** The scheme selector mounted in `urlCard`'s edit form, or null when none is. */
export function getUpdateSchemeSelector({
  urlCard,
}: {
  urlCard: JQuery;
}): SchemeSelectorHandle | null {
  return getSchemeSelector({
    container: urlCard.find(UPDATE_SCHEME_CONTAINER_SELECTOR),
  });
}

// Current scheme for composing the submitted URL; "" (the text is the full URL)
// when no selector is mounted.
export function currentUpdateScheme({ urlCard }: { urlCard: JQuery }): string {
  return getUpdateSchemeSelector({ urlCard })?.getScheme() ?? "";
}

/**
 * Resyncs the edit input from `href` (default: the card's stored href). With a
 * selector, a recognized scheme prefix is moved into it (explicit); an href
 * without one (including a legacy unsupported scheme) stays whole in the input
 * and the selector's scheme is left as it is. Callers mounting a fresh selector
 * get its default scheme.
 */
export function syncUpdateInputFromHref({
  urlCard,
  selector,
  href = urlCard.find(".urlString").attr("href") as string,
}: {
  urlCard: JQuery;
  selector: SchemeSelectorHandle | null;
  href?: string;
}): void {
  const input = urlCard.find(".urlStringUpdate");
  const split = selector ? splitScheme({ urlString: href }) : null;
  if (selector && split) {
    input.val(split.rest);
    selector.setScheme({ scheme: split.scheme, explicit: true });
    return;
  }
  input.val(href);
}

/**
 * After a successful Undo: puts `restoredURLString` back into the edit input (split
 * across the mounted selector, if any) and re-renders the trim block from it.
 */
export function resyncUpdateInputAfterUndo({
  urlCard,
  restoredURLString,
}: {
  urlCard: JQuery;
  restoredURLString: string;
}): void {
  const selector = getUpdateSchemeSelector({ urlCard });
  syncUpdateInputFromHref({ urlCard, selector, href: restoredURLString });
  flushParamTrim({
    trimWrap: urlCard.find(".urlParamTrimWrap"),
    text: getInputValue(urlCard.find(".urlStringUpdate")),
    scheme: selector?.getScheme() ?? "",
  });
}
