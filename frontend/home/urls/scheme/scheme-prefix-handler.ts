import { getInputValue } from "../../../lib/globals.js";
import type { SchemeSelectorHandle } from "./scheme-selector.js";
import { defaultSchemeForText, splitScheme } from "./scheme-utils.js";

// Runs on every URL input event: calls
// onChange (clears a stale URL error), moves a typed or pasted scheme prefix
// into the selector (an explicit choice), and otherwise keeps a non-explicit
// selector on the scheme the text implies (http for dev hosts).
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
      scheme: defaultSchemeForText({ text }),
      explicit: false,
    });
  }
}
