import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createMockJqXHR } from "../../__tests__/helpers/mock-jquery.js";
import { createFlowBuilder } from "../flow-builder.js";
import type { FlowBuilder, FlowBuilderCallbacks } from "../flow-builder.js";
import { makeCell } from "../flow-builder-dom.js";
import { filterAddReason, renderExtras } from "../flow-builder-rows.js";
import { draftFromEntry } from "../flow-builder-state.js";
import {
  createMetricFlow,
  deleteMetricFlow,
  fetchMetricFlowCatalog,
  previewMetricFlow,
  updateMetricFlow,
} from "../metrics-query-client.js";
import {
  addFilterButton,
  control,
  dimSelect,
  entryWith,
  FILTER_CATALOG,
  filterRows,
  MANY_DIMS_EVENT,
  MANY_GROUPABLE_EVENT,
  ODD_KIND_EVENT,
  optionTexts,
  pick,
  reasonText,
  stepRows,
  type,
  valueControl,
} from "./helpers/flow-builder-harness.js";

vi.mock("../metrics-query-client.js", () => ({
  fetchMetricFlowCatalog: vi.fn(),
  createMetricFlow: vi.fn(),
  previewMetricFlow: vi.fn(),
  updateMetricFlow: vi.fn(),
  deleteMetricFlow: vi.fn(),
}));

type Xhr = ReturnType<typeof createMockJqXHR> & {
  abort: ReturnType<typeof vi.fn>;
  status: number;
};

const fetchMock = vi.mocked(fetchMetricFlowCatalog);
const updateMock = vi.mocked(updateMetricFlow);
let container: HTMLElement;
let callbacks: FlowBuilderCallbacks;
let builder: FlowBuilder;
let catalogXhr: Xhr;

function makeXhr(): Xhr {
  return Object.assign(createMockJqXHR(), {
    abort: vi.fn(),
    status: 0,
  }) as Xhr;
}

function openWith({ steps }: { steps: Record<string, unknown>[] }): void {
  builder.open({ mode: "edit", entry: entryWith({ steps }) });
  catalogXhr.resolve(FILTER_CATALOG);
}

function uiStep({
  event = "ui_form_cancel",
  filters,
  label = "One",
}: {
  event?: string;
  filters?: unknown;
  label?: string;
} = {}): Record<string, unknown> {
  const step: Record<string, unknown> = {
    stream: "ui",
    label,
    event_name: event,
  };
  if (filters !== undefined) {
    step.dim_filter = filters;
  }
  return step;
}

const SECOND_STEP = {
  stream: "domain",
  label: "Two",
  event_name: "url_created",
};

function firstRow(): HTMLElement {
  return stepRows(container)[0];
}

function addFilter({ row = firstRow() }: { row?: HTMLElement } = {}): void {
  addFilterButton({ row }).click();
}

function removeButtons({ row }: { row: HTMLElement }): HTMLElement[] {
  return [
    ...row.querySelectorAll<HTMLElement>('[data-action="remove-filter"]'),
  ];
}

function savedSteps(): Record<string, unknown>[] {
  control({ root: container, selector: 'button[type="submit"]' }).click();
  const call = updateMock.mock.calls[updateMock.mock.calls.length - 1];
  return (call[0].definition as { steps: Record<string, unknown>[] }).steps;
}

/** Presses Save on a draft with a problem: nothing is sent, the summary lists it. */
function blockedSave(): string[] {
  const sent = updateMock.mock.calls.length;
  control({ root: container, selector: 'button[type="submit"]' }).click();
  expect(updateMock.mock.calls.length).toBe(sent);
  return [...container.querySelectorAll(".flow-builder-summary li")].map(
    (item) => item.textContent ?? "",
  );
}

beforeEach(() => {
  catalogXhr = makeXhr();
  fetchMock.mockReset();
  fetchMock.mockImplementation(() => catalogXhr);
  updateMock.mockReset();
  updateMock.mockImplementation(() => makeXhr() as never);
  vi.mocked(createMetricFlow).mockReset();
  vi.mocked(deleteMetricFlow).mockReset();
  vi.mocked(previewMetricFlow).mockReset();
  vi.mocked(previewMetricFlow).mockImplementation(() => makeXhr() as never);
  container = document.createElement("div");
  document.body.append(container);
  callbacks = {
    announce: vi.fn(),
    onSaved: vi.fn(),
    onCancelled: vi.fn(),
    onFlowMissing: vi.fn(),
    onDeleted: vi.fn(),
    onListStale: vi.fn(),
    getWindow: () => "day",
  };
  builder = createFlowBuilder({ container, callbacks });
});

afterEach(() => {
  builder.close();
  container.remove();
});

describe("adding and editing filter rows", () => {
  it("adds a row, focuses its field and announces", () => {
    openWith({ steps: [uiStep(), SECOND_STEP] });
    addFilter();
    const [row] = filterRows(firstRow());
    expect(dimSelect({ filterRow: row })).toBe(document.activeElement);
    expect(callbacks.announce).toHaveBeenCalledWith({
      message: "Filter added.",
    });
    expect(addFilterButton({ row: firstRow() }).textContent).toContain(
      "+ Add filter (1 of 5)",
    );
  });

  it("keeps the value control disabled until a field is chosen", () => {
    openWith({ steps: [uiStep(), SECOND_STEP] });
    addFilter();
    const value = valueControl({ filterRow: filterRows(firstRow())[0] });
    expect(value.disabled).toBe(true);
    expect(optionTexts({ select: value })).toEqual(["Choose a field first"]);
  });

  it("lists the field's values once chosen and resets the value when the field changes", () => {
    openWith({ steps: [uiStep(), SECOND_STEP] });
    addFilter();
    pick({
      select: dimSelect({ filterRow: filterRows(firstRow())[0] }),
      value: "device_type",
    });
    let value = valueControl({ filterRow: filterRows(firstRow())[0] });
    expect(value.disabled).toBe(false);
    expect(optionTexts({ select: value })).toEqual([
      "Choose a value",
      "mobile",
      "desktop",
    ]);
    pick({ select: value, value: "mobile" });
    expect(savedSteps()[0].dim_filter).toEqual(["device_type:mobile"]);

    pick({
      select: dimSelect({ filterRow: filterRows(firstRow())[0] }),
      value: "trigger",
    });
    value = valueControl({ filterRow: filterRows(firstRow())[0] });
    expect((value as HTMLSelectElement).value).toBe("");
  });

  it("keeps focus on a changed field and value", () => {
    openWith({ steps: [uiStep(), SECOND_STEP] });
    addFilter();
    const dim = dimSelect({ filterRow: filterRows(firstRow())[0] });
    pick({ select: dim, value: "device_type" });
    expect(document.activeElement).toBe(
      dimSelect({ filterRow: filterRows(firstRow())[0] }),
    );
    pick({
      select: valueControl({ filterRow: filterRows(firstRow())[0] }),
      value: "desktop",
    });
    expect(document.activeElement).toBe(
      valueControl({ filterRow: filterRows(firstRow())[0] }),
    );
  });

  it("offers a sibling's field to no other row but keeps the row's own", () => {
    openWith({
      steps: [uiStep({ filters: ["device_type:mobile"] }), SECOND_STEP],
    });
    addFilter();
    const [first, second] = filterRows(firstRow());
    expect(optionTexts({ select: dimSelect({ filterRow: first }) })).toEqual([
      "Choose a field",
      "device_type",
      "trigger",
    ]);
    expect(optionTexts({ select: dimSelect({ filterRow: second }) })).toEqual([
      "Choose a field",
      "trigger",
    ]);
  });

  it("shows a text input for a status_code field and keeps focus while typing", () => {
    openWith({
      steps: [
        {
          stream: "api",
          label: "Api",
          api_endpoint: "urls.create_url",
          api_method: "POST",
        },
        SECOND_STEP,
      ],
    });
    addFilter();
    pick({
      select: dimSelect({ filterRow: filterRows(firstRow())[0] }),
      value: "status_code",
    });
    const input = valueControl({
      filterRow: filterRows(firstRow())[0],
    }) as HTMLInputElement;
    expect(input.tagName).toBe("INPUT");
    expect(input.maxLength).toBe(3);
    expect(input.getAttribute("inputmode")).toBe("numeric");
    const hint = document.getElementById(
      input.getAttribute("aria-describedby") ?? "",
    );
    expect(hint?.textContent).toBe("Three digits, 100-599");
    input.focus();
    type({ input, value: "404" });
    expect(document.activeElement).toBe(input);
    expect(savedSteps()[0].dim_filter).toEqual(["status_code:404"]);
  });
});

describe("Add filter availability", () => {
  it("names the step after the visible label", () => {
    openWith({ steps: [uiStep(), SECOND_STEP] });
    const [first, second] = stepRows(container);
    expect(addFilterButton({ row: first }).textContent).toBe(
      "+ Add filter (0 of 5) for step 1",
    );
    expect(addFilterButton({ row: second }).textContent).toBe(
      "+ Add filter (0 of 5) for step 2",
    );
  });

  it("is aria-disabled with a reason when the step has no event", () => {
    openWith({ steps: [{ stream: "ui", label: "One" }, SECOND_STEP] });
    const button = addFilterButton({ row: firstRow() });
    expect(button.getAttribute("aria-disabled")).toBe("true");
    expect(reasonText({ row: firstRow() })).toBe("Choose an event first.");
    expect(
      document.getElementById(button.getAttribute("aria-describedby") ?? "")
        ?.textContent,
    ).toBe("Choose an event first.");
  });

  it("is aria-disabled when an API step has no endpoint", () => {
    openWith({ steps: [{ stream: "api", label: "Api" }, SECOND_STEP] });
    expect(reasonText({ row: firstRow() })).toBe("Choose an event first.");
  });

  it("is aria-disabled when the event has no filterable fields", () => {
    openWith({ steps: [uiStep({ event: "ui_group_only" }), SECOND_STEP] });
    expect(reasonText({ row: firstRow() })).toBe(
      "This event has no fields to filter on.",
    );
  });

  it("is aria-disabled once every field has a filter", () => {
    openWith({
      steps: [
        uiStep({
          event: "ui_url_create_open",
          filters: ["device_type:mobile"],
        }),
        SECOND_STEP,
      ],
    });
    expect(reasonText({ row: firstRow() })).toBe(
      "Every field already has a filter.",
    );
  });

  it("stops at the cap, does nothing on click, and re-enables after a removal", () => {
    openWith({
      steps: [
        uiStep({
          event: MANY_DIMS_EVENT,
          filters: [1, 2, 3, 4, 5].map((index) => `dim_${index}:x`),
        }),
        SECOND_STEP,
      ],
    });
    const button = addFilterButton({ row: firstRow() });
    expect(button.getAttribute("aria-disabled")).toBe("true");
    expect(reasonText({ row: firstRow() })).toBe(
      "At most 5 filters are allowed.",
    );
    button.focus();
    button.click();
    expect(filterRows(firstRow())).toHaveLength(5);
    expect(document.activeElement).toBe(button);

    removeButtons({ row: firstRow() })[0].click();
    expect(
      addFilterButton({ row: firstRow() }).getAttribute("aria-disabled"),
    ).toBeNull();
    expect(reasonText({ row: firstRow() })).toBe("");
  });
});

const API_STEP = {
  stream: "api",
  label: "Api",
  api_endpoint: "urls.create_url",
  api_method: "POST",
};

describe("filter value inputs", () => {
  function openStatusInput(): HTMLInputElement {
    openWith({ steps: [API_STEP, SECOND_STEP] });
    addFilter();
    pick({
      select: dimSelect({ filterRow: filterRows(firstRow())[0] }),
      value: "status_code",
    });
    return valueControl({
      filterRow: filterRows(firstRow())[0],
    }) as HTMLInputElement;
  }

  it("keeps the same node on change, so a following Remove click lands", () => {
    const input = openStatusInput();
    input.focus();
    type({ input, value: "404" });
    input.dispatchEvent(new Event("change", { bubbles: true }));
    expect(input.isConnected).toBe(true);
    expect(valueControl({ filterRow: filterRows(firstRow())[0] })).toBe(input);
    removeButtons({ row: firstRow() })[0].click();
    expect(filterRows(firstRow())).toHaveLength(0);
  });

  function pressEnter({ target }: { target: HTMLElement }): KeyboardEvent {
    const event = new KeyboardEvent("keydown", {
      key: "Enter",
      bubbles: true,
      cancelable: true,
    });
    target.dispatchEvent(event);
    return event;
  }

  it("saves on Enter in a status_code input", () => {
    const input = openStatusInput();
    type({ input, value: "404" });
    const event = pressEnter({ target: input });
    expect(event.defaultPrevented).toBe(true);
    expect(updateMock).toHaveBeenCalledTimes(1);
    const steps = (
      updateMock.mock.calls[0][0].definition as {
        steps: Record<string, unknown>[];
      }
    ).steps;
    expect(steps[0].dim_filter).toEqual(["status_code:404"]);
  });

  it("does not save twice while a save is in flight", () => {
    const input = openStatusInput();
    type({ input, value: "404" });
    pressEnter({ target: input });
    pressEnter({ target: input });
    expect(updateMock).toHaveBeenCalledTimes(1);
  });

  it("leaves Enter on a select alone", () => {
    openWith({ steps: [uiStep(), SECOND_STEP] });
    addFilter();
    const event = pressEnter({
      target: dimSelect({ filterRow: filterRows(firstRow())[0] }),
    });
    expect(event.defaultPrevented).toBe(false);
    expect(updateMock).not.toHaveBeenCalled();
  });

  it("describes the status input by its error and its hint", () => {
    const hint = document.createElement("p");
    const input = document.createElement("input");
    const cell = makeCell({
      control: input,
      field: "x",
      messages: ["Bad"],
      errorId: "err-1",
      describedBy: ["hint-1"],
    });
    hint.id = "hint-1";
    expect(input.getAttribute("aria-describedby")).toBe("err-1 hint-1");
    expect(cell.querySelector("#err-1")?.textContent).toBe("Bad");
  });

  it("renders a disabled select, not a text box, for an unknown filter kind", () => {
    openWith({
      steps: [
        uiStep({ event: ODD_KIND_EVENT, filters: ["odd:x"] }),
        SECOND_STEP,
      ],
    });
    const value = valueControl({ filterRow: filterRows(firstRow())[0] });
    expect(value.tagName).toBe("SELECT");
    expect(value.disabled).toBe(true);
  });

  it("keeps a status_code step as an input after it moves", () => {
    openWith({
      steps: [{ ...API_STEP, dim_filter: ["status_code:404"] }, SECOND_STEP],
    });
    control({
      root: firstRow(),
      selector: '[data-action="move-down"]',
    }).click();
    expect(filterRows(stepRows(container)[1])).toHaveLength(1);
    expect(
      valueControl({ filterRow: filterRows(stepRows(container)[1])[0] })
        .tagName,
    ).toBe("INPUT");
  });

  it("re-renders only the group: the step node and other inputs survive", () => {
    openWith({ steps: [uiStep(), SECOND_STEP] });
    const row = firstRow();
    const label = control({
      root: row,
      selector: '[data-field="label"]',
    }) as HTMLInputElement;
    type({ input: label, value: "Typed label" });
    addFilter();
    pick({
      select: dimSelect({ filterRow: filterRows(row)[0] }),
      value: "device_type",
    });
    removeButtons({ row })[0].click();
    expect(firstRow()).toBe(row);
    expect(control({ root: row, selector: '[data-field="label"]' })).toBe(
      label,
    );
    expect(label.value).toBe("Typed label");
  });
});

describe("Add filter extras", () => {
  it("exposes the visible text first, with a visually hidden step suffix", () => {
    openWith({ steps: [uiStep(), SECOND_STEP] });
    const button = addFilterButton({ row: firstRow() });
    const hidden = button.querySelector(".visually-hidden");
    expect(hidden?.textContent).toBe(" for step 1");
    expect(button.textContent?.startsWith("+ Add filter (0 of 5)")).toBe(true);
  });

  const DISABLED_CASES: [string, Record<string, unknown>][] = [
    ["no event", { stream: "ui", label: "One" }],
    ["no fields", uiStep({ event: "ui_group_only" })],
    [
      "the cap",
      uiStep({
        event: MANY_DIMS_EVENT,
        filters: [1, 2, 3, 4, 5].map((index) => `dim_${index}:x`),
      }),
    ],
    [
      "every field used",
      uiStep({ event: "ui_url_create_open", filters: ["device_type:mobile"] }),
    ],
  ];

  it.each(DISABLED_CASES)("a click does nothing with %s", (_name, step) => {
    openWith({ steps: [step, SECOND_STEP] });
    const before = filterRows(firstRow()).length;
    const button = addFilterButton({ row: firstRow() });
    expect(button.getAttribute("aria-disabled")).toBe("true");
    button.focus();
    button.click();
    expect(filterRows(firstRow())).toHaveLength(before);
    expect(callbacks.announce).not.toHaveBeenCalledWith({
      message: "Filter added.",
    });
    expect(document.activeElement).toBe(button);
  });

  it("puts a missing event before every other reason", () => {
    openWith({
      steps: [
        {
          stream: "ui",
          label: "One",
          dim_filter: ["a:1", "b:1", "c:1", "d:1", "e:1"],
        },
        SECOND_STEP,
      ],
    });
    expect(reasonText({ row: firstRow() })).toBe("Choose an event first.");
  });

  it("puts no-fields before the cap", () => {
    openWith({
      steps: [
        uiStep({
          event: "ui_group_only",
          filters: ["a:1", "b:1", "c:1", "d:1", "e:1"],
        }),
        SECOND_STEP,
      ],
    });
    expect(reasonText({ row: firstRow() })).toBe(
      "This event has no fields to filter on.",
    );
  });

  it("gives disabled Add buttons in two steps distinct reason ids", () => {
    openWith({
      steps: [
        { stream: "ui", label: "One" },
        { stream: "ui", label: "Two" },
      ],
    });
    const ids = [...container.querySelectorAll("[id$='-filter-reason']")].map(
      (element) => element.id,
    );
    expect(ids).toHaveLength(2);
    expect(new Set(ids).size).toBe(2);
  });

  it("stays disabled, with nothing stale, before the catalog loads", () => {
    const [step] = draftFromEntry({
      entry: entryWith({
        steps: [uiStep({ filters: ["device_type:mobile"] })],
      }),
    }).steps;
    expect(filterAddReason({ catalog: null, step })).toBe("");
    const extras = renderExtras({
      uid: "t",
      catalog: null,
      step,
      position: "1",
    });
    expect(extras.textContent).not.toContain("no longer exists");
    expect(extras.textContent).not.toContain("has no fields");
    const button = addFilterButton({ row: extras });
    expect(button.getAttribute("aria-disabled")).toBe("true");
    expect(button.getAttribute("aria-describedby")).toBeNull();
    expect(extras.querySelector("[aria-invalid]")).toBeNull();
  });
});

describe("removing filter rows", () => {
  const THREE = ["device_type:mobile", "trigger:a"];

  it("focuses the next row's field", () => {
    openWith({ steps: [uiStep({ filters: THREE }), SECOND_STEP] });
    removeButtons({ row: firstRow() })[0].click();
    expect(document.activeElement).toBe(
      dimSelect({ filterRow: filterRows(firstRow())[0] }),
    );
    expect(callbacks.announce).toHaveBeenCalledWith({
      message: "Filter removed.",
    });
  });

  it("focuses the previous row's field when the last row goes", () => {
    openWith({ steps: [uiStep({ filters: THREE }), SECOND_STEP] });
    removeButtons({ row: firstRow() })[1].click();
    expect(document.activeElement).toBe(
      dimSelect({ filterRow: filterRows(firstRow())[0] }),
    );
  });

  it("focuses Add when the only row goes", () => {
    openWith({
      steps: [uiStep({ filters: ["device_type:mobile"] }), SECOND_STEP],
    });
    removeButtons({ row: firstRow() })[0].click();
    expect(document.activeElement).toBe(addFilterButton({ row: firstRow() }));
    expect(filterRows(firstRow())).toHaveLength(0);
  });
});

describe("stored rows", () => {
  it("marks a stale field and keeps its value readable", () => {
    openWith({
      steps: [uiStep({ filters: ["gone_dim:zzz"] }), SECOND_STEP],
    });
    const [row] = filterRows(firstRow());
    const dim = dimSelect({ filterRow: row });
    expect(dim.getAttribute("aria-invalid")).toBe("true");
    expect(optionTexts({ select: dim })).toContain(
      "gone_dim (no longer exists)",
    );
    expect(row.textContent).toContain(
      "Field 'gone_dim' does not exist for this event.",
    );
    expect(
      document.getElementById(dim.getAttribute("aria-describedby") ?? "")
        ?.textContent,
    ).toBe("Field 'gone_dim' does not exist for this event.");
    expect(valueControl({ filterRow: row }).disabled).toBe(true);
  });

  it("marks a stale value on a values field", () => {
    openWith({
      steps: [uiStep({ filters: ["device_type:tablet"] }), SECOND_STEP],
    });
    const [row] = filterRows(firstRow());
    const value = valueControl({ filterRow: row });
    expect(value.getAttribute("aria-invalid")).toBe("true");
    expect(optionTexts({ select: value })).toContain(
      "tablet (no longer exists)",
    );
    expect(row.textContent).toContain("Choose a value from the list.");
    expect(
      document.getElementById(value.getAttribute("aria-describedby") ?? "")
        ?.textContent,
    ).toBe("Choose a value from the list.");
    pick({ select: value, value: "mobile" });
    expect(
      valueControl({ filterRow: filterRows(firstRow())[0] }).getAttribute(
        "aria-invalid",
      ),
    ).toBeNull();
  });

  it("never marks a status_code value stale", () => {
    openWith({
      steps: [
        {
          stream: "api",
          label: "Api",
          api_endpoint: "urls.create_url",
          dim_filter: ["status_code:999"],
        },
        SECOND_STEP,
      ],
    });
    const [row] = filterRows(firstRow());
    expect(
      valueControl({ filterRow: row }).getAttribute("aria-invalid"),
    ).toBeNull();
  });

  it("shows a malformed entry as its raw string, plain and invalid, until edited", () => {
    openWith({ steps: [uiStep({ filters: ["nocolon"] }), SECOND_STEP] });
    const [row] = filterRows(firstRow());
    const dim = dimSelect({ filterRow: row });
    expect(dim.getAttribute("aria-invalid")).toBe("true");
    expect(optionTexts({ select: dim })).toContain("nocolon");
    expect(optionTexts({ select: dim }).join()).not.toContain(
      "no longer exists",
    );
    expect(valueControl({ filterRow: row }).disabled).toBe(true);
    expect(blockedSave()).toEqual([
      "Step 1, filter 1: Choose a field and value.",
    ]);

    // Save re-renders the row, so pick on the live select.
    pick({
      select: dimSelect({ filterRow: filterRows(firstRow())[0] }),
      value: "trigger",
    });
    const edited = dimSelect({ filterRow: filterRows(firstRow())[0] });
    expect(edited.getAttribute("aria-invalid")).toBeNull();
    expect(
      valueControl({ filterRow: filterRows(firstRow())[0] }).disabled,
    ).toBe(false);
  });
});

describe("several steps", () => {
  it("gives each step's controls distinct names and ids", () => {
    openWith({
      steps: [
        uiStep({ filters: ["device_type:gone"] }),
        uiStep({ label: "Two", filters: ["device_type:gone"] }),
      ],
    });
    const [first, second] = stepRows(container);
    const names = [first, second].flatMap((row) =>
      [
        ...row.querySelectorAll<HTMLElement>("[data-filter-key][aria-label]"),
      ].map((element) => element.getAttribute("aria-label")),
    );
    expect(new Set(names).size).toBe(names.length);
    const ids = [...container.querySelectorAll("[id]")].map(
      (element) => element.id,
    );
    expect(new Set(ids).size).toBe(ids.length);
    expect(names).toContain("Step 2 filter 1 field");
  });

  it("keeps rows with their step when it moves", () => {
    openWith({
      steps: [uiStep({ filters: ["device_type:mobile"] }), SECOND_STEP],
    });
    control({
      root: firstRow(),
      selector: '[data-action="move-down"]',
    }).click();
    expect(filterRows(stepRows(container)[0])).toHaveLength(0);
    expect(filterRows(stepRows(container)[1])).toHaveLength(1);
  });
});

function withBreakdown({
  breakdown,
  event = "ui_form_cancel",
  filters,
}: {
  breakdown: unknown;
  event?: string;
  filters?: unknown;
}): Record<string, unknown> {
  return { ...uiStep({ event, filters }), drop_breakdown: breakdown };
}

function select({
  root,
  field,
}: {
  root: HTMLElement;
  field: string;
}): HTMLSelectElement {
  return control({
    root,
    selector: `[data-field="${field}"]`,
  }) as HTMLSelectElement;
}

function action({
  root,
  name,
}: {
  root: HTMLElement;
  name: string;
}): HTMLElement {
  return control({ root, selector: `[data-action="${name}"]` });
}

function breakdownBlock({ row = firstRow() }: { row?: HTMLElement } = {}) {
  return control({ root: row, selector: ".flow-builder-breakdown" });
}

function breakdownFilterRows({
  row = firstRow(),
}: { row?: HTMLElement } = {}): HTMLElement[] {
  return filterRows(breakdownBlock({ row }));
}

describe("drop-off breakdown", () => {
  it("adds a breakdown, focuses its event select and announces", () => {
    openWith({ steps: [uiStep(), SECOND_STEP] });
    action({ root: firstRow(), name: "add-breakdown" }).click();
    expect(
      select({ root: breakdownBlock(), field: "breakdown_event_name" }),
    ).toBe(document.activeElement);
    expect(callbacks.announce).toHaveBeenCalledWith({
      message: "Breakdown added.",
    });
    // One per step: the Add button is replaced by the block.
    expect(
      firstRow().querySelector('[data-action="add-breakdown"]'),
    ).toBeNull();
    expect(firstRow().querySelectorAll(".flow-builder-breakdown")).toHaveLength(
      1,
    );
  });

  it("is aria-disabled with a reason until the step has an event", () => {
    openWith({
      steps: [{ stream: "ui", label: "Blank" }, SECOND_STEP],
    });
    const add = action({ root: firstRow(), name: "add-breakdown" });
    expect(add.getAttribute("aria-disabled")).toBe("true");
    const reasonId = add.getAttribute("aria-describedby") ?? "";
    expect(container.querySelector(`[id="${reasonId}"]`)?.textContent).toBe(
      "Choose an event first.",
    );
    add.click();
    expect(firstRow().querySelector(".flow-builder-breakdown")).toBeNull();
  });

  it("offers only groupable events, grouped, and only groupable group_by fields", () => {
    openWith({ steps: [uiStep(), SECOND_STEP] });
    action({ root: firstRow(), name: "add-breakdown" }).click();
    const event = select({
      root: breakdownBlock(),
      field: "breakdown_event_name",
    });
    const names = optionTexts({ select: event });
    expect(names).toContain("ui_form_cancel");
    expect(names).toContain("api_hit");
    expect(names).not.toContain("ui_url_create_open");
    expect(event.querySelectorAll("optgroup").length).toBeGreaterThan(1);
    const groupBy = select({
      root: breakdownBlock(),
      field: "breakdown_group_by",
    });
    expect(groupBy.disabled).toBe(true);
    pick({ select: event, value: "ui_form_cancel" });
    const enabled = select({
      root: breakdownBlock(),
      field: "breakdown_group_by",
    });
    expect(enabled.disabled).toBe(false);
    expect(optionTexts({ select: enabled })).toEqual([
      "Choose a field",
      "trigger",
    ]);
    // Focus stays on the control after a re-render.
    expect(
      select({ root: breakdownBlock(), field: "breakdown_event_name" }),
    ).toBe(document.activeElement);
  });

  it("resets group_by and breakdown filters on an event change, keeping step filters", () => {
    openWith({
      steps: [
        withBreakdown({
          filters: ["device_type:mobile"],
          breakdown: {
            event_name: "ui_form_cancel",
            group_by: "trigger",
            dim_filter: ["device_type:desktop"],
          },
        }),
        SECOND_STEP,
      ],
    });
    pick({
      select: select({ root: breakdownBlock(), field: "breakdown_event_name" }),
      value: "many_groupable_event",
    });
    expect(
      select({ root: breakdownBlock(), field: "breakdown_group_by" }).value,
    ).toBe("");
    expect(breakdownFilterRows()).toHaveLength(0);
    expect(
      filterRows(firstRow()).filter(
        (row) => row.closest(".flow-builder-breakdown") === null,
      ),
    ).toHaveLength(1);
  });

  it("shows a stored non-groupable group_by as invalid and does not replace it", () => {
    openWith({
      steps: [
        withBreakdown({
          breakdown: { event_name: "ui_form_cancel", group_by: "device_type" },
        }),
        SECOND_STEP,
      ],
    });
    const groupBy = select({
      root: breakdownBlock(),
      field: "breakdown_group_by",
    });
    expect(groupBy.getAttribute("aria-invalid")).toBe("true");
    expect(optionTexts({ select: groupBy })).toContain(
      "device_type (no longer exists)",
    );
    expect(breakdownBlock().textContent).toContain(
      "Group by field 'device_type' is not available for this event.",
    );
    expect(blockedSave()).toEqual([
      "Step 1, breakdown: Group by field 'device_type' is not available for this event.",
    ]);
    expect(groupBy.value).toBe("device_type");
  });

  it("shows a stored zero-groupable event as a plain invalid option with disabled controls", () => {
    openWith({
      steps: [
        withBreakdown({
          breakdown: {
            event_name: "ui_url_create_open",
            group_by: "device_type",
            dim_filter: ["device_type:mobile"],
          },
        }),
        SECOND_STEP,
      ],
    });
    const event = select({
      root: breakdownBlock(),
      field: "breakdown_event_name",
    });
    expect(optionTexts({ select: event })).toContain("ui_url_create_open");
    expect(event.textContent).not.toContain("no longer exists");
    expect(event.getAttribute("aria-invalid")).toBe("true");
    const helper = breakdownBlock().querySelector(
      ".flow-builder-hint",
    ) as HTMLElement;
    expect(helper.textContent).toBe("This event cannot be broken down.");
    expect(event.getAttribute("aria-describedby")).toContain(helper.id);
    const groupBy = select({
      root: breakdownBlock(),
      field: "breakdown_group_by",
    });
    expect(groupBy.disabled).toBe(true);
    expect(groupBy.getAttribute("aria-describedby")).toBe(helper.id);
    const [bdRow] = breakdownFilterRows();
    expect(
      select({ root: bdRow, field: "breakdown_filter_dim" }).disabled,
    ).toBe(true);
    expect(
      select({ root: bdRow, field: "breakdown_filter_value" }).disabled,
    ).toBe(true);
    const addFilterBtn = action({
      root: breakdownBlock(),
      name: "add-breakdown-filter",
    });
    expect(addFilterBtn.getAttribute("aria-disabled")).toBe("true");
    expect(addFilterBtn.getAttribute("aria-describedby")).toBe(helper.id);
    expect(
      breakdownBlock().querySelectorAll(".flow-builder-reason"),
    ).toHaveLength(0);
    // Unedited, nothing is repaired: Save is blocked and says why.
    expect(blockedSave()).toEqual([
      "Step 1, breakdown: This event cannot be broken down.",
    ]);
    // Picking a groupable event recovers the row.
    pick({
      select: select({ root: breakdownBlock(), field: "breakdown_event_name" }),
      value: "ui_form_cancel",
    });
    expect(
      select({ root: breakdownBlock(), field: "breakdown_group_by" }).disabled,
    ).toBe(false);
    expect(
      select({
        root: breakdownBlock(),
        field: "breakdown_event_name",
      }).getAttribute("aria-invalid"),
    ).toBeNull();
  });

  it("shows a stored event missing from the catalog as stale with read-only controls", () => {
    openWith({
      steps: [
        withBreakdown({
          breakdown: {
            event_name: "ui_old_event",
            group_by: "trigger",
            dim_filter: ["form:a", "form:b"],
          },
        }),
        SECOND_STEP,
      ],
    });
    const event = select({
      root: breakdownBlock(),
      field: "breakdown_event_name",
    });
    expect(optionTexts({ select: event })).toContain(
      "ui_old_event (no longer exists)",
    );
    expect(event.getAttribute("aria-invalid")).toBe("true");
    const helper = breakdownBlock().querySelector(
      ".flow-builder-hint",
    ) as HTMLElement;
    expect(helper.textContent).toBe("This event no longer exists.");
    expect(
      select({ root: breakdownBlock(), field: "breakdown_group_by" }).disabled,
    ).toBe(true);
    expect(breakdownFilterRows()).toHaveLength(2);
    // Each row's Remove stays enabled; focus goes to the next Remove, else Add.
    const removes = (): HTMLElement[] => [
      ...breakdownBlock().querySelectorAll<HTMLElement>(
        '[data-action="remove-breakdown-filter"]',
      ),
    ];
    expect(removes().every((button) => !button.hasAttribute("disabled"))).toBe(
      true,
    );
    removes()[0].click();
    expect(breakdownFilterRows()).toHaveLength(1);
    expect(document.activeElement).toBe(removes()[0]);
    removes()[0].click();
    expect(document.activeElement).toBe(
      action({ root: breakdownBlock(), name: "add-breakdown-filter" }),
    );
    // Removing the breakdown recovers the row.
    action({ root: firstRow(), name: "remove-breakdown" }).click();
    expect(firstRow().querySelector(".flow-builder-breakdown")).toBeNull();
    expect(document.activeElement).toBe(
      action({ root: firstRow(), name: "add-breakdown" }),
    );
    expect(callbacks.announce).toHaveBeenCalledWith({
      message: "Breakdown removed.",
    });
  });

  describe("removing breakdown filter rows", () => {
    const openTwo = (): void =>
      openWith({
        steps: [
          withBreakdown({
            breakdown: {
              event_name: "ui_form_cancel",
              group_by: "trigger",
              dim_filter: ["device_type:mobile", "trigger:a"],
            },
          }),
          SECOND_STEP,
        ],
      });
    const removes = (): HTMLElement[] => [
      ...breakdownBlock().querySelectorAll<HTMLElement>(
        '[data-action="remove-breakdown-filter"]',
      ),
    ];

    it("focuses the next row's field and announces", () => {
      openTwo();
      removes()[0].click();
      expect(document.activeElement).toBe(
        select({
          root: breakdownFilterRows()[0],
          field: "breakdown_filter_dim",
        }),
      );
      expect(callbacks.announce).toHaveBeenLastCalledWith({
        message: "Filter removed.",
      });
    });

    it("focuses the previous row's field when the last row goes", () => {
      openTwo();
      removes()[1].click();
      expect(breakdownFilterRows()).toHaveLength(1);
      expect(document.activeElement).toBe(
        select({
          root: breakdownFilterRows()[0],
          field: "breakdown_filter_dim",
        }),
      );
    });

    it("focuses Add breakdown filter when the only row goes", () => {
      openTwo();
      removes()[0].click();
      removes()[0].click();
      expect(breakdownFilterRows()).toHaveLength(0);
      expect(document.activeElement).toBe(
        action({ root: breakdownBlock(), name: "add-breakdown-filter" }),
      );
    });

    it("focuses Add breakdown and announces when the whole breakdown goes", () => {
      openTwo();
      action({ root: firstRow(), name: "remove-breakdown" }).click();
      expect(firstRow().querySelector(".flow-builder-breakdown")).toBeNull();
      expect(document.activeElement).toBe(
        action({ root: firstRow(), name: "add-breakdown" }),
      );
      expect(callbacks.announce).toHaveBeenLastCalledWith({
        message: "Breakdown removed.",
      });
    });
  });

  it("names the four breakdown buttons from their visible text plus the step", () => {
    openWith({
      steps: [
        uiStep(),
        withBreakdown({
          breakdown: { event_name: "ui_form_cancel", group_by: "trigger" },
        }),
      ],
    });
    const [first, second] = stepRows(container);
    const addName = action({ root: first, name: "add-breakdown" });
    expect(addName.textContent).toBe("+ Add drop-off breakdown for step 1");
    expect(addName.firstChild?.textContent).toBe("+ Add drop-off breakdown");
    expect(action({ root: second, name: "remove-breakdown" }).textContent).toBe(
      "Remove breakdown for step 2",
    );
    expect(
      action({ root: second, name: "add-breakdown-filter" }).textContent,
    ).toBe("+ Add breakdown filter (0 of 5) for step 2");
    action({ root: second, name: "add-breakdown-filter" }).click();
    const remove = action({ root: second, name: "remove-breakdown-filter" });
    expect(remove.getAttribute("aria-label")).toBe(
      "Remove step 2 breakdown filter 1",
    );
    expect(
      select({
        root: breakdownFilterRows({ row: second })[0],
        field: "breakdown_filter_dim",
      }).getAttribute("aria-label"),
    ).toBe("Step 2 breakdown filter 1 field");
  });

  it("caps breakdown filters independently of the step's", () => {
    openWith({
      steps: [
        withBreakdown({
          event: "many_dims_event",
          filters: [1, 2, 3, 4, 5].map((index) => `dim_${index}:x`),
          breakdown: {
            event_name: "many_groupable_event",
            group_by: "dim_1",
            dim_filter: [1, 2, 3, 4].map((index) => `dim_${index}:x`),
          },
        }),
        SECOND_STEP,
      ],
    });
    const add = action({
      root: breakdownBlock(),
      name: "add-breakdown-filter",
    });
    expect(add.getAttribute("aria-disabled")).toBeNull();
    expect(
      action({ root: firstRow(), name: "add-filter" }).getAttribute(
        "aria-disabled",
      ),
    ).toBe("true");
    add.click();
    expect(breakdownFilterRows()).toHaveLength(5);
    const capped = action({
      root: breakdownBlock(),
      name: "add-breakdown-filter",
    });
    expect(capped.getAttribute("aria-disabled")).toBe("true");
    expect(
      breakdownBlock().querySelector(
        `[id="${capped.getAttribute("aria-describedby")}"]`,
      )?.textContent,
    ).toBe("At most 5 filters are allowed.");
    capped.click();
    expect(breakdownFilterRows()).toHaveLength(5);
  });

  it("explains Add breakdown filter before an event is chosen", () => {
    openWith({ steps: [uiStep(), SECOND_STEP] });
    action({ root: firstRow(), name: "add-breakdown" }).click();
    const add = action({
      root: breakdownBlock(),
      name: "add-breakdown-filter",
    });
    expect(add.getAttribute("aria-disabled")).toBe("true");
    expect(
      breakdownBlock().querySelector(
        `[id="${add.getAttribute("aria-describedby")}"]`,
      )?.textContent,
    ).toBe("Choose an event first.");
    add.click();
    expect(breakdownFilterRows()).toHaveLength(0);
  });

  it("clears the breakdown when the step's stream changes", () => {
    openWith({
      steps: [
        withBreakdown({
          breakdown: { event_name: "ui_form_cancel", group_by: "trigger" },
        }),
        SECOND_STEP,
      ],
    });
    pick({
      select: select({ root: firstRow(), field: "stream" }),
      value: "api",
    });
    expect(firstRow().querySelector(".flow-builder-breakdown")).toBeNull();
  });

  it("recovers a stale group_by and a missing event by re-picking", () => {
    openWith({
      steps: [
        withBreakdown({
          breakdown: { event_name: "ui_form_cancel", group_by: "device_type" },
        }),
        withBreakdown({
          breakdown: { event_name: "ui_old_event", group_by: "trigger" },
        }),
      ],
    });
    const [first, second] = stepRows(container);
    pick({
      select: select({
        root: breakdownBlock({ row: first }),
        field: "breakdown_group_by",
      }),
      value: "trigger",
    });
    const fixed = select({
      root: breakdownBlock({ row: first }),
      field: "breakdown_group_by",
    });
    expect(fixed.getAttribute("aria-invalid")).toBeNull();
    expect(optionTexts({ select: fixed }).join()).not.toContain(
      "no longer exists",
    );
    pick({
      select: select({
        root: breakdownBlock({ row: second }),
        field: "breakdown_event_name",
      }),
      value: "ui_form_cancel",
    });
    const event = select({
      root: breakdownBlock({ row: second }),
      field: "breakdown_event_name",
    });
    expect(event.getAttribute("aria-invalid")).toBeNull();
    expect(
      select({
        root: breakdownBlock({ row: second }),
        field: "breakdown_group_by",
      }).disabled,
    ).toBe(false);
  });

  it("labels the breakdown filter group with the step", () => {
    openWith({
      steps: [
        withBreakdown({
          breakdown: {
            event_name: "ui_form_cancel",
            group_by: "trigger",
            dim_filter: ["device_type:mobile"],
          },
        }),
        SECOND_STEP,
      ],
    });
    expect(
      breakdownBlock()
        .querySelector(".flow-builder-filters")
        ?.getAttribute("aria-label"),
    ).toBe("Step 1 breakdown filters");
  });

  it("clears the breakdown when the step's event changes", () => {
    openWith({
      steps: [
        withBreakdown({
          breakdown: { event_name: "ui_form_cancel", group_by: "trigger" },
        }),
        SECOND_STEP,
      ],
    });
    pick({
      select: select({ root: firstRow(), field: "event_name" }),
      value: "ui_url_create_open",
    });
    expect(firstRow().querySelector(".flow-builder-breakdown")).toBeNull();
  });
});

describe("errors, damaged values and summary links", () => {
  const GROUP_ONLY_STEP = {
    stream: "ui",
    label: "One",
    event_name: "ui_group_only",
  };
  const ZERO_BREAKDOWN = {
    event_name: "ui_url_create_open",
    group_by: "device_type",
    dim_filter: ["device_type:mobile"],
  };

  function openEntry({
    steps,
    errors = {},
  }: {
    steps: Record<string, unknown>[];
    errors?: Record<string, string[]>;
  }): void {
    builder.open({ mode: "edit", entry: { ...entryWith({ steps }), errors } });
    catalogXhr.resolve(FILTER_CATALOG);
  }

  function summaryLinks(): HTMLElement[] {
    return [
      ...container.querySelectorAll<HTMLElement>(
        ".flow-builder-summary button",
      ),
    ];
  }

  function formErrors(): string {
    return (
      container.querySelector(".flow-builder-form-errors")?.textContent ?? ""
    );
  }

  function describedBy({ element }: { element: HTMLElement }): string[] {
    return (element.getAttribute("aria-describedby") ?? "")
      .split(" ")
      .filter((id) => id !== "");
  }

  function textOf({ id }: { id: string }): string {
    return document.getElementById(id)?.textContent ?? "";
  }

  describe("form-level error cleanup", () => {
    const stepWithBreakdown = withBreakdown({
      breakdown: { event_name: "ui_form_cancel", group_by: "trigger" },
      filters: ["device_type:mobile"],
    });
    const cases: [string, () => void][] = [
      [
        "Remove breakdown",
        () => action({ root: firstRow(), name: "remove-breakdown" }).click(),
      ],
      [
        "a breakdown event change",
        () =>
          pick({
            select: select({
              root: breakdownBlock(),
              field: "breakdown_event_name",
            }),
            value: MANY_GROUPABLE_EVENT,
          }),
      ],
      [
        "a filter value edit",
        () =>
          pick({
            select: valueControl({ filterRow: filterRows(firstRow())[0] }),
            value: "desktop",
          }),
      ],
    ];

    it.each(cases)("is emptied by %s", (_name, edit) => {
      openEntry({
        steps: [stepWithBreakdown, SECOND_STEP],
        errors: { "steps.0.drop_breakdown.mystery": ["Odd."] },
      });
      expect(formErrors()).toContain("Odd.");
      edit();
      expect(formErrors()).toBe("");
    });
  });

  describe("row errors", () => {
    it("link both controls and clear when the value is typed", () => {
      openEntry({
        steps: [{ ...API_STEP, dim_filter: ["status_code:99"] }, SECOND_STEP],
        errors: { "steps.0.dim_filter.0": ["Status out of range."] },
      });
      const [row] = filterRows(firstRow());
      const input = valueControl({ filterRow: row }) as HTMLInputElement;
      const dim = dimSelect({ filterRow: row });
      const message = row.querySelector(".flow-builder-error") as HTMLElement;
      for (const element of [dim, input]) {
        expect(element.getAttribute("aria-invalid")).toBe("true");
        expect(describedBy({ element })).toContain(message.id);
      }
      type({ input, value: "404" });
      expect(row.querySelector(".flow-builder-error")).toBeNull();
      for (const element of [dim, input]) {
        expect(element.hasAttribute("aria-invalid")).toBe(false);
        expect(describedBy({ element })).not.toContain(message.id);
      }
      // The status hint stays linked.
      expect(describedBy({ element: input })).toHaveLength(1);
    });

    it("sends nothing on Enter in a status_code input with an incomplete row", () => {
      openEntry({ steps: [API_STEP, SECOND_STEP] });
      addFilter();
      pick({
        select: dimSelect({ filterRow: filterRows(firstRow())[0] }),
        value: "status_code",
      });
      const input = valueControl({
        filterRow: filterRows(firstRow())[0],
      }) as HTMLInputElement;
      const enter = new KeyboardEvent("keydown", {
        key: "Enter",
        bubbles: true,
        cancelable: true,
      });
      input.dispatchEvent(enter);
      expect(updateMock).not.toHaveBeenCalled();
      expect(
        [...container.querySelectorAll(".flow-builder-summary li")].map(
          (item) => item.textContent,
        ),
      ).toEqual(["Step 1, filter 1: Choose a field and value."]);
    });
  });

  describe("damaged stored values", () => {
    const DAMAGED_MESSAGE =
      "This step's stored filters could not be read. Add a filter to replace them.";
    const HINT = "Or change this step's event or endpoint to clear it.";

    it("shows the message on open, linked from a disabled Add with its recourse hint", () => {
      openEntry({
        steps: [{ ...GROUP_ONLY_STEP, dim_filter: "oops" }, SECOND_STEP],
      });
      const add = addFilterButton({ row: firstRow() });
      expect(add.getAttribute("aria-disabled")).toBe("true");
      const texts = describedBy({ element: add }).map((id) => textOf({ id }));
      expect(texts).toContain(DAMAGED_MESSAGE);
      expect(texts[texts.length - 1]).toBe(HINT);
      expect(
        [...container.querySelectorAll(".flow-builder-summary li")].map(
          (item) => item.textContent,
        ),
      ).toEqual([`Step 1, filters: ${DAMAGED_MESSAGE}`]);
    });

    it("keeps the hint beside a server message that replaces the damaged one", () => {
      openEntry({
        steps: [{ ...GROUP_ONLY_STEP, dim_filter: "oops" }, SECOND_STEP],
        errors: { "steps.0.dim_filter": ["Server says no."] },
      });
      const add = addFilterButton({ row: firstRow() });
      const texts = describedBy({ element: add }).map((id) => textOf({ id }));
      expect(texts).toContain("Server says no.");
      expect(texts).not.toContain(DAMAGED_MESSAGE);
      expect(texts[texts.length - 1]).toBe(HINT);
    });

    it("announces the replacement for Add and for breakdown-level actions", () => {
      openEntry({
        steps: [
          { ...uiStep(), dim_filter: "oops", drop_breakdown: ["x"] },
          SECOND_STEP,
        ],
      });
      addFilter();
      expect(callbacks.announce).toHaveBeenLastCalledWith({
        message: "Stored filters replaced.",
      });
      action({ root: firstRow(), name: "add-breakdown" }).click();
      expect(callbacks.announce).toHaveBeenLastCalledWith({
        message: "Stored breakdown replaced.",
      });
    });

    const DAMAGED_FILTERS_BREAKDOWN = {
      event_name: "ui_form_cancel",
      group_by: "trigger",
      dim_filter: "x",
    };

    it("announces damaged breakdown filters replaced by a breakdown event change", () => {
      openEntry({
        steps: [
          withBreakdown({ breakdown: DAMAGED_FILTERS_BREAKDOWN }),
          SECOND_STEP,
        ],
      });
      pick({
        select: select({
          root: breakdownBlock(),
          field: "breakdown_event_name",
        }),
        value: MANY_GROUPABLE_EVENT,
      });
      expect(callbacks.announce).toHaveBeenLastCalledWith({
        message: "Stored breakdown filters replaced.",
      });
    });

    it("announces a plain removal when Remove breakdown drops damaged filters", () => {
      openEntry({
        steps: [
          withBreakdown({ breakdown: DAMAGED_FILTERS_BREAKDOWN }),
          SECOND_STEP,
        ],
      });
      action({ root: firstRow(), name: "remove-breakdown" }).click();
      expect(callbacks.announce).toHaveBeenLastCalledWith({
        message: "Breakdown removed.",
      });
    });
  });

  describe("a stored zero-groupable breakdown", () => {
    it("shows its server messages once on the event select, not the disabled controls", () => {
      openEntry({
        steps: [withBreakdown({ breakdown: ZERO_BREAKDOWN }), SECOND_STEP],
        errors: {
          "steps.0.drop_breakdown.group_by": ["Bad group."],
          "steps.0.drop_breakdown.dim_filter.0": ["Bad filter."],
        },
      });
      const event = select({
        root: breakdownBlock(),
        field: "breakdown_event_name",
      });
      const texts = describedBy({ element: event }).map((id) => textOf({ id }));
      expect(texts).toContain("Bad group. Bad filter.");
      expect(
        breakdownBlock().querySelectorAll(".flow-builder-error"),
      ).toHaveLength(1);
      const links = summaryLinks();
      expect(links.map((link) => link.textContent)).toEqual([
        "Step 1, breakdown: Bad group.",
      ]);
      links[0].click();
      expect(document.activeElement).toBe(event);
    });
  });

  describe("summary links", () => {
    const eventSelect = (): HTMLSelectElement =>
      select({ root: breakdownBlock(), field: "breakdown_event_name" });
    const cases: [string, Record<string, unknown>, () => HTMLElement][] = [
      [
        "a damaged step filter list goes to its Add filter",
        { ...GROUP_ONLY_STEP, dim_filter: "oops" },
        () => addFilterButton({ row: firstRow() }),
      ],
      [
        "a stale filter value goes to the value control",
        uiStep({ filters: ["device_type:bogus"] }),
        () => valueControl({ filterRow: filterRows(firstRow())[0] }),
      ],
      [
        "a stale filter field goes to the field select",
        uiStep({ filters: ["gone:x"] }),
        () => dimSelect({ filterRow: filterRows(firstRow())[0] }),
      ],
      [
        "a damaged breakdown goes to Add drop-off breakdown",
        { ...uiStep(), drop_breakdown: ["x"] },
        () => action({ root: firstRow(), name: "add-breakdown" }),
      ],
      [
        "damaged breakdown filters go to Add breakdown filter",
        withBreakdown({
          breakdown: {
            event_name: "ui_form_cancel",
            group_by: "trigger",
            dim_filter: "x",
          },
        }),
        () => action({ root: firstRow(), name: "add-breakdown-filter" }),
      ],
      [
        "a zero-groupable breakdown goes to its event select",
        withBreakdown({ breakdown: ZERO_BREAKDOWN }),
        eventSelect,
      ],
      [
        "a raw row under a zero-groupable event goes to the event select",
        withBreakdown({
          breakdown: { ...ZERO_BREAKDOWN, dim_filter: ["nocolon"] },
        }),
        eventSelect,
      ],
      [
        "a raw row under a missing event goes to the event select",
        withBreakdown({
          breakdown: {
            event_name: "ui_old_event",
            group_by: "trigger",
            dim_filter: ["nocolon"],
          },
        }),
        eventSelect,
      ],
    ];

    it.each(cases)("%s", (_name, step, target) => {
      openEntry({ steps: [step, SECOND_STEP] });
      const [link] = summaryLinks();
      link.click();
      expect(document.activeElement).toBe(target());
      expect(document.activeElement).not.toBe(
        select({ root: firstRow(), field: "label" }),
      );
    });

    it("lands an incomplete breakdown on its event select", () => {
      openEntry({ steps: [uiStep(), SECOND_STEP] });
      action({ root: firstRow(), name: "add-breakdown" }).click();
      blockedSave();
      summaryLinks()[0].click();
      expect(document.activeElement).toBe(eventSelect());
    });
  });
});
