import { getInputValue } from "../../../lib/globals.js";
import type { SchemeSelectorHandle } from "./scheme-selector.js";
import {
  defaultSchemeForText,
  isAuthorityScheme,
  splitScheme,
} from "./scheme-utils.js";

// Runs on every URL input event: calls
// onChange (clears a stale URL error), moves a typed or pasted scheme prefix
// into the selector (an explicit choice), and otherwise keeps a non-explicit
// selector on the scheme the text implies (http for dev hosts). While an
// opaque scheme is explicitly selected the text is left verbatim, so a nested
// `feed:https://x` keeps its inner scheme (composeURL's opaque passthrough).
export function handleSchemePrefixInput({
  input,
  selector,
  onChange,
}: {
  input: JQuery<HTMLElement>;
  selector: SchemeSelectorHandle;
  onChange: () => void;
}): void {
  onChange();
  // Hidden selector: an emptied field puts the snapshotted default back so a
  // pasted opaque scheme (explicit `mailto`) cannot trap what is typed next.
  if (selector.isHidden() && getInputValue(input).trim() === "") {
    selector.restoreDefaultScheme();
  }
  if (
    selector.isExplicit() &&
    !isAuthorityScheme({ scheme: selector.getScheme() })
  ) {
    return;
  }
  const text = getInputValue(input);
  const split = splitScheme({ urlString: text });
  if (split) {
    input.val(split.rest);
    selector.setScheme({
      scheme: split.scheme,
      explicit: true,
      announce: true,
    });
    return;
  }
  if (!selector.isExplicit()) {
    selector.setScheme({
      scheme: defaultSchemeForText({
        text,
        fallbackScheme: selector.getDefaultScheme(),
      }),
      explicit: false,
    });
  }
}
