/**
 * DOM helpers shared by the flow builder and its nested-row renderer.
 *
 * No state and no imports back into `flow-builder.ts`, so both modules can use them.
 */
import { APP_CONFIG } from "../lib/config.js";
import { fillTemplate } from "../lib/string-template.js";

export function makeElement<Tag extends keyof HTMLElementTagNameMap>({
  tag,
  className,
  text,
  attrs,
}: {
  tag: Tag;
  className?: string;
  text?: string;
  attrs?: Record<string, string>;
}): HTMLElementTagNameMap[Tag] {
  const element = document.createElement(tag);
  if (className) {
    element.className = className;
  }
  if (text !== undefined) {
    element.textContent = text;
  }
  for (const [name, value] of Object.entries(attrs ?? {})) {
    element.setAttribute(name, value);
  }
  return element;
}

export function makeOption({
  value,
  text,
  selected = false,
}: {
  value: string;
  text: string;
  selected?: boolean;
}): HTMLOptionElement {
  const option = makeElement({ tag: "option", text, attrs: { value } });
  option.selected = selected;
  return option;
}

export function isDisabled({ element }: { element: Element }): boolean {
  return element.getAttribute("aria-disabled") === "true";
}

export function setDisabled({
  element,
  disabled,
  reasonId,
}: {
  element: HTMLElement;
  disabled: boolean;
  reasonId: string;
}): void {
  if (disabled) {
    element.setAttribute("aria-disabled", "true");
    element.setAttribute("aria-describedby", reasonId);
  } else {
    element.removeAttribute("aria-disabled");
    element.removeAttribute("aria-describedby");
  }
}

/** A labelled cell wrapping one control; shows `messages` and links them to the control. */
export function makeCell({
  control,
  field,
  messages,
  errorId,
  describedBy = [],
}: {
  control: HTMLElement;
  field: string;
  messages: string[];
  errorId: string;
  /** Extra ids (e.g. a hint) kept in `aria-describedby` after the error id. */
  describedBy?: string[];
}): HTMLElement {
  const cell = makeElement({
    tag: "div",
    className: "flow-builder-cell",
    attrs: { "data-cell": field },
  });
  cell.append(control);
  if (messages.length > 0) {
    control.setAttribute("aria-invalid", "true");
    control.setAttribute(
      "aria-describedby",
      [errorId, ...describedBy].join(" "),
    );
    cell.append(
      makeElement({
        tag: "p",
        className: "flow-builder-error",
        text: messages.join(" "),
        attrs: { id: errorId },
      }),
    );
  }
  return cell;
}

export function makeSelect({
  field,
  key,
  label,
}: {
  field: string;
  key: number;
  label: string;
}): HTMLSelectElement {
  return makeElement({
    tag: "select",
    className: "flow-builder-select",
    attrs: {
      "data-field": field,
      "data-step-key": String(key),
      "aria-label": label,
    },
  });
}

/** Keeps a no-longer-valid stored value selected and flags the select. */
export function appendStaleOption({
  select,
  value,
}: {
  select: HTMLSelectElement;
  value: string;
}): void {
  select.append(
    makeOption({
      value,
      text: fillTemplate({
        template: APP_CONFIG.strings.METRICS_FLOW_BUILDER_NOTE_STALE_VALUE,
        values: { value },
      }),
      selected: true,
    }),
  );
  select.setAttribute("aria-invalid", "true");
}
