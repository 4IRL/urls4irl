import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Schema } from "../../types/api-helpers.d.ts";

import { createMockJqXHR } from "../../__tests__/helpers/mock-jquery.js";
import { createFlowBuilder } from "../flow-builder.js";
import type { FlowBuilder, FlowBuilderCallbacks } from "../flow-builder.js";
import {
  createMetricFlow,
  deleteMetricFlow,
  fetchMetricFlowCatalog,
  updateMetricFlow,
} from "../metrics-query-client.js";

vi.mock("../metrics-query-client.js", () => ({
  fetchMetricFlowCatalog: vi.fn(),
  createMetricFlow: vi.fn(),
  updateMetricFlow: vi.fn(),
  deleteMetricFlow: vi.fn(),
}));

type Catalog = Schema<"FlowCatalogResponseSchema">;
type Entry = Schema<"MetricFlowEntrySchema">;
type CatalogXhr = ReturnType<typeof createMockJqXHR> & {
  abort: ReturnType<typeof vi.fn>;
  status: number;
  _429Handled?: boolean;
};

type SaveXhr = CatalogXhr & {
  readyState: number;
  statusText: string;
  responseJSON?: Record<string, unknown>;
};

const CATALOG: Catalog = {
  event_groups: [
    {
      category: "ui",
      events: [
        {
          event_name: "modal_open",
          description: "",
          category: "ui",
          step_allowed: true,
          dims: [],
        },
        {
          event_name: "ui_hidden",
          description: "",
          category: "ui",
          step_allowed: false,
          dims: [],
        },
      ],
    },
    {
      category: "domain",
      events: [
        {
          event_name: "url_created",
          description: "",
          category: "domain",
          step_allowed: true,
          dims: [],
        },
      ],
    },
  ],
  api_endpoints: [
    { endpoint: "urls.create_url", blueprint: "urls", methods: ["POST"] },
    { endpoint: "urls.update_url", blueprint: "urls", methods: ["GET", "PUT"] },
  ],
};

const fetchMock = vi.mocked(fetchMetricFlowCatalog);
const createMock = vi.mocked(createMetricFlow);
const updateMock = vi.mocked(updateMetricFlow);
const deleteMock = vi.mocked(deleteMetricFlow);
let saves: SaveXhr[];
let container: HTMLElement;
let callbacks: FlowBuilderCallbacks;
let builder: FlowBuilder;
let pending: CatalogXhr[];

function makeXhr(): CatalogXhr {
  const xhr = Object.assign(createMockJqXHR(), {
    abort: vi.fn(),
    status: 0,
  }) as CatalogXhr;
  pending.push(xhr);
  return xhr;
}

function makeSaveXhr(): SaveXhr {
  const xhr = Object.assign(createMockJqXHR(), {
    abort: vi.fn(),
    status: 0,
    readyState: 1,
    statusText: "",
  }) as SaveXhr;
  saves.push(xhr);
  return xhr;
}

function failSave({
  xhr,
  status,
  body,
  readyState = 4,
  statusText = "error",
}: {
  xhr: SaveXhr;
  status: number;
  body?: Record<string, unknown>;
  readyState?: number;
  statusText?: string;
}): void {
  xhr.status = status;
  xhr.readyState = readyState;
  xhr.statusText = statusText;
  xhr.responseJSON = body;
  xhr.reject();
}

function resolveCatalog({ xhr }: { xhr: CatalogXhr }): void {
  xhr.resolve(CATALOG);
}

function failCatalog({
  xhr,
  status = 500,
}: {
  xhr: CatalogXhr;
  status?: number;
}): void {
  xhr.status = status;
  xhr.reject();
}

function openAndLoad({
  mode = "create",
  entry,
}: {
  mode?: "create" | "edit";
  entry?: Entry;
} = {}): void {
  builder.open({ mode, entry });
  resolveCatalog({ xhr: pending[pending.length - 1] });
}

function entryWith({ steps }: { steps: Record<string, unknown>[] }): Entry {
  return {
    id: "custom_1",
    display_name: "My flow",
    is_builtin: false,
    definition: { steps },
    errors: {},
    first_invalid: null,
  };
}

function rows(): HTMLElement[] {
  return [...container.querySelectorAll<HTMLElement>(".flow-builder-step")];
}

function control({
  row,
  selector,
}: {
  row: HTMLElement;
  selector: string;
}): HTMLElement {
  const found = row.querySelector<HTMLElement>(selector);
  if (found === null) {
    throw new Error(`missing ${selector}`);
  }
  return found;
}

function labelsOf(): string[] {
  return rows()
    .map(
      (row) =>
        control({ row, selector: '[data-field="label"]' }) as HTMLInputElement,
    )
    .map((input) => (input as HTMLInputElement).value);
}

function optionTexts({ select }: { select: HTMLElement }): string[] {
  return [...select.querySelectorAll("option")].map(
    (option) => option.textContent ?? "",
  );
}

function pick({ select, value }: { select: HTMLElement; value: string }): void {
  (select as HTMLSelectElement).value = value;
  select.dispatchEvent(new Event("change", { bubbles: true }));
}

function type({ input, value }: { input: HTMLElement; value: string }): void {
  (input as HTMLInputElement).value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

beforeEach(() => {
  pending = [];
  saves = [];
  fetchMock.mockReset();
  fetchMock.mockImplementation(() => makeXhr());
  createMock.mockReset();
  createMock.mockImplementation(() => makeSaveXhr() as never);
  updateMock.mockReset();
  updateMock.mockImplementation(() => makeSaveXhr() as never);
  deleteMock.mockReset();
  deleteMock.mockImplementation(() => makeSaveXhr() as never);
  container = document.createElement("div");
  document.body.append(container);
  callbacks = {
    announce: vi.fn(),
    onSaved: vi.fn(),
    onCancelled: vi.fn(),
    onFlowMissing: vi.fn(),
    onDeleted: vi.fn(),
    onListStale: vi.fn(),
  };
  builder = createFlowBuilder({ container, callbacks });
});

afterEach(() => {
  builder.close();
  container.remove();
});

describe("open", () => {
  it("focuses the heading and shows loading text, no form", () => {
    builder.open({ mode: "create" });
    const heading = container.querySelector("h3");
    expect(document.activeElement).toBe(heading);
    expect(heading?.getAttribute("tabindex")).toBe("-1");
    expect(container.textContent).toContain("Loading the event list");
    expect(container.querySelector("form")).toBeNull();
    expect(builder.isOpen()).toBe(true);
    expect(container.hidden).toBe(false);
  });

  it("renders the form labelled by the heading with two blank steps", () => {
    openAndLoad();
    const form = container.querySelector("form");
    const heading = container.querySelector("h3");
    expect(form?.getAttribute("aria-labelledby")).toBe(heading?.id);
    expect(form?.hasAttribute("novalidate")).toBe(true);
    expect(rows()).toHaveLength(2);
    expect(document.activeElement).toBe(heading);
  });

  it("requires an entry for edit mode", () => {
    expect(() => builder.open({ mode: "edit" })).toThrow();
  });

  it("close aborts the request, ignores a stale response and hides", () => {
    builder.open({ mode: "create" });
    const xhr = pending[0];
    builder.close();
    expect(xhr.abort).toHaveBeenCalledTimes(1);
    resolveCatalog({ xhr });
    expect(container.querySelector("form")).toBeNull();
    expect(builder.isOpen()).toBe(false);
    expect(container.hidden).toBe(true);
  });
});

describe("catalog failure", () => {
  it("shows the error with Try again and no picker", () => {
    builder.open({ mode: "create" });
    failCatalog({ xhr: pending[0] });
    expect(container.textContent).toContain("Could not load the event list");
    expect(container.querySelector("select")).toBeNull();
    expect(document.activeElement?.textContent).toBe("Try again");
  });

  it("shows the rate-limit message for a JSON 429", () => {
    builder.open({ mode: "create" });
    failCatalog({ xhr: pending[0], status: 429 });
    expect(container.textContent).toContain("Too many requests");
  });

  it("re-enables Try again when the 429 was already handled", () => {
    builder.open({ mode: "create" });
    pending[0]._429Handled = true;
    failCatalog({ xhr: pending[0], status: 429 });
    expect(container.textContent).toContain("Too many requests");
    expect(container.textContent).not.toContain("Loading the event list");
    const retry = document.activeElement as HTMLButtonElement;
    expect(retry.textContent).toBe("Try again");
    expect(retry.getAttribute("aria-disabled")).toBeNull();
  });

  it("re-enables Try again after a retry hits a handled 429", () => {
    builder.open({ mode: "create" });
    failCatalog({ xhr: pending[0] });
    const retry = document.activeElement as HTMLButtonElement;
    retry.click();
    expect(retry.getAttribute("aria-disabled")).toBe("true");
    pending[1]._429Handled = true;
    failCatalog({ xhr: pending[1], status: 429 });
    expect(retry.getAttribute("aria-disabled")).toBeNull();
    expect(document.activeElement).toBe(retry);
    expect(container.textContent).toContain("Too many requests");
  });

  it("keeps Try again outside the status live region", () => {
    builder.open({ mode: "create" });
    failCatalog({ xhr: pending[0] });
    const retry = document.activeElement as HTMLElement;
    expect(retry.closest('[role="status"]')).toBeNull();
    expect(retry.parentElement).toBe(
      container.querySelector('[role="status"]')?.parentElement,
    );
  });

  it("keeps Try again mounted, disabled and focused while retrying", () => {
    builder.open({ mode: "create" });
    failCatalog({ xhr: pending[0] });
    const retry = document.activeElement as HTMLButtonElement;
    retry.click();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(retry.isConnected).toBe(true);
    expect(retry.getAttribute("aria-disabled")).toBe("true");
    expect(document.activeElement).toBe(retry);
    expect(container.textContent).toContain("Loading the event list");
  });

  it("sends no second request when pressed while pending", () => {
    builder.open({ mode: "create" });
    failCatalog({ xhr: pending[0] });
    const retry = document.activeElement as HTMLButtonElement;
    retry.click();
    retry.click();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(document.activeElement).toBe(retry);
  });

  it("refocuses Try again after a repeated failure", () => {
    builder.open({ mode: "create" });
    failCatalog({ xhr: pending[0] });
    const retry = document.activeElement as HTMLButtonElement;
    retry.click();
    failCatalog({ xhr: pending[1] });
    expect(retry.getAttribute("aria-disabled")).toBeNull();
    expect(document.activeElement).toBe(retry);
    expect(container.textContent).toContain("Could not load the event list");
  });

  it("renders the form and focuses the heading after a successful retry", () => {
    builder.open({ mode: "create" });
    failCatalog({ xhr: pending[0] });
    (document.activeElement as HTMLButtonElement).click();
    resolveCatalog({ xhr: pending[1] });
    expect(container.querySelector("form")).not.toBeNull();
    expect(document.activeElement).toBe(container.querySelector("h3"));
  });

  it("ignores a response from a request superseded by close and reopen", () => {
    builder.open({ mode: "create" });
    const first = pending[0];
    builder.open({ mode: "create" });
    expect(first.abort).toHaveBeenCalledTimes(1);
    resolveCatalog({ xhr: first });
    expect(container.querySelector("form")).toBeNull();
    resolveCatalog({ xhr: pending[1] });
    expect(container.querySelector("form")).not.toBeNull();
  });

  it("ignores a failure from a request superseded by close", () => {
    builder.open({ mode: "create" });
    const first = pending[0];
    builder.close();
    failCatalog({ xhr: first });
    expect(container.textContent).toBe("");
  });
});

describe("pickers", () => {
  it("lists only step-allowed events of the row's stream", () => {
    openAndLoad();
    const select = control({
      row: rows()[0],
      selector: '[data-field="event_name"]',
    });
    expect(optionTexts({ select })).toEqual(["Choose an event", "modal_open"]);
  });

  it("groups endpoints by blueprint and limits methods to the endpoint", () => {
    openAndLoad();
    const [first] = rows();
    pick({
      select: control({ row: first, selector: '[data-field="stream"]' }),
      value: "api",
    });
    const endpoint = control({
      row: rows()[0],
      selector: '[data-field="api_endpoint"]',
    });
    expect(endpoint.querySelectorAll("optgroup")).toHaveLength(1);
    expect(endpoint.querySelector("optgroup")?.label).toBe("urls");
    pick({ select: endpoint, value: "urls.update_url" });
    const method = control({
      row: rows()[0],
      selector: '[data-field="api_method"]',
    });
    expect(optionTexts({ select: method })).toEqual([
      "Choose a method",
      "GET",
      "PUT",
    ]);
  });

  it("keeps a stale stored event selected until another is picked", () => {
    openAndLoad({
      mode: "edit",
      entry: entryWith({
        steps: [
          { stream: "ui", label: "One", event_name: "gone_event" },
          { stream: "ui", label: "Two", event_name: "modal_open" },
        ],
      }),
    });
    const select = control({
      row: rows()[0],
      selector: '[data-field="event_name"]',
    }) as HTMLSelectElement;
    expect(select.value).toBe("gone_event");
    expect(select.getAttribute("aria-invalid")).toBe("true");
    expect(optionTexts({ select })).toContain("gone_event (no longer exists)");
    pick({ select, value: "modal_open" });
    const after = control({
      row: rows()[0],
      selector: '[data-field="event_name"]',
    }) as HTMLSelectElement;
    expect(optionTexts({ select: after })).not.toContain(
      "gone_event (no longer exists)",
    );
    expect(after.value).toBe("modal_open");
    expect(after.hasAttribute("aria-invalid")).toBe(false);
  });

  it("keeps stale endpoint and method options selected and flagged", () => {
    openAndLoad({
      mode: "edit",
      entry: entryWith({
        steps: [
          { stream: "ui", label: "One", event_name: "modal_open" },
          {
            stream: "api",
            label: "Two",
            api_endpoint: "urls.create_url",
            api_method: "DELETE",
          },
          {
            stream: "api",
            label: "Three",
            api_endpoint: "gone.endpoint",
            api_method: "GET",
          },
        ],
      }),
    });
    const method = control({
      row: rows()[1],
      selector: '[data-field="api_method"]',
    }) as HTMLSelectElement;
    expect(method.value).toBe("DELETE");
    expect(method.getAttribute("aria-invalid")).toBe("true");
    expect(optionTexts({ select: method })).toContain(
      "DELETE (no longer exists)",
    );
    const endpoint = control({
      row: rows()[2],
      selector: '[data-field="api_endpoint"]',
    }) as HTMLSelectElement;
    expect(endpoint.value).toBe("gone.endpoint");
    expect(endpoint.getAttribute("aria-invalid")).toBe("true");
    expect(optionTexts({ select: endpoint })).toContain(
      "gone.endpoint (no longer exists)",
    );
    expect(endpoint.querySelector("option[aria-invalid]")).toBeNull();
  });

  it("auto-selects the only method of a single-method endpoint", () => {
    openAndLoad();
    pick({
      select: control({ row: rows()[0], selector: '[data-field="stream"]' }),
      value: "api",
    });
    pick({
      select: control({
        row: rows()[0],
        selector: '[data-field="api_endpoint"]',
      }),
      value: "urls.create_url",
    });
    const method = control({
      row: rows()[0],
      selector: '[data-field="api_method"]',
    }) as HTMLSelectElement;
    expect(method.value).toBe("POST");
  });

  it("selects the stored values in an existing flow", () => {
    openAndLoad({
      mode: "edit",
      entry: entryWith({
        steps: [
          { stream: "ui", label: "One", event_name: "modal_open" },
          {
            stream: "api",
            label: "Two",
            api_endpoint: "urls.create_url",
            api_method: "POST",
          },
        ],
      }),
    });
    expect(container.querySelector("h3")?.textContent).toBe("Edit flow");
    const method = control({
      row: rows()[1],
      selector: '[data-field="api_method"]',
    }) as HTMLSelectElement;
    expect(method.value).toBe("POST");
  });
});

describe("step editing", () => {
  it("typing does not replace the row element and marks the draft dirty", () => {
    openAndLoad();
    const [first] = rows();
    const input = control({ row: first, selector: '[data-field="label"]' });
    expect(builder.isDirty()).toBe(false);
    type({ input, value: "Hello" });
    expect(rows()[0]).toBe(first);
    expect(input.isConnected).toBe(true);
    expect(builder.isDirty()).toBe(true);
  });

  it("clears a field's server error when the field is edited", () => {
    const entry = entryWith({
      steps: [
        { stream: "ui", label: "", event_name: "modal_open" },
        { stream: "ui", label: "Two", event_name: "modal_open" },
      ],
    });
    entry.errors = { "steps.0.label": ["Too short."] };
    openAndLoad({ mode: "edit", entry });
    const input = control({ row: rows()[0], selector: '[data-field="label"]' });
    expect(container.textContent).toContain("Too short.");
    expect(input.getAttribute("aria-invalid")).toBe("true");
    type({ input, value: "Fixed" });
    expect(container.textContent).not.toContain("Too short.");
    expect(input.hasAttribute("aria-invalid")).toBe(false);
  });

  it("clears stream-related server errors when the stream changes", () => {
    const entry = entryWith({
      steps: [
        { stream: "ui", label: "One", event_name: "modal_open" },
        { stream: "ui", label: "Two", event_name: "modal_open" },
      ],
    });
    entry.errors = { "steps.0.event_name": ["Bad event."] };
    openAndLoad({ mode: "edit", entry });
    expect(container.textContent).toContain("Bad event.");
    pick({
      select: control({ row: rows()[0], selector: '[data-field="stream"]' }),
      value: "domain",
    });
    expect(container.textContent).not.toContain("Bad event.");
    pick({
      select: control({ row: rows()[0], selector: '[data-field="stream"]' }),
      value: "ui",
    });
    expect(container.textContent).not.toContain("Bad event.");
  });

  it("clears a select field's server error when it is changed", () => {
    const entry = entryWith({
      steps: [
        { stream: "ui", label: "One" },
        { stream: "ui", label: "Two", event_name: "modal_open" },
      ],
    });
    entry.errors = { "steps.0.event_name": ["Pick an event."] };
    openAndLoad({ mode: "edit", entry });
    const select = control({
      row: rows()[0],
      selector: '[data-field="event_name"]',
    });
    expect(select.getAttribute("aria-invalid")).toBe("true");
    const error = container.querySelector(
      `#${select.getAttribute("aria-describedby")}`,
    );
    expect(error?.textContent).toBe("Pick an event.");
    pick({ select, value: "modal_open" });
    expect(container.textContent).not.toContain("Pick an event.");
    const after = control({
      row: rows()[0],
      selector: '[data-field="event_name"]',
    });
    expect(after.hasAttribute("aria-invalid")).toBe(false);
    expect(after.hasAttribute("aria-describedby")).toBe(false);
  });

  it("keeps first-up and last-down disabled after a row re-renders", () => {
    openAndLoad();
    pick({
      select: control({ row: rows()[0], selector: '[data-field="stream"]' }),
      value: "domain",
    });
    pick({
      select: control({ row: rows()[1], selector: '[data-field="stream"]' }),
      value: "domain",
    });
    const up = control({ row: rows()[0], selector: '[data-action="move-up"]' });
    const down = control({
      row: rows()[1],
      selector: '[data-action="move-down"]',
    });
    for (const button of [up, down]) {
      expect(button.getAttribute("aria-disabled")).toBe("true");
      expect(button.getAttribute("aria-describedby")).not.toBeNull();
    }
  });

  it("moves a middle step up, keeping focus on its move-up control", () => {
    openAndLoad();
    container.querySelector<HTMLElement>('[data-action="add"]')?.click();
    for (const [index, value] of ["A", "B", "C"].entries()) {
      type({
        input: control({
          row: rows()[index],
          selector: '[data-field="label"]',
        }),
        value,
      });
    }
    const up = control({ row: rows()[1], selector: '[data-action="move-up"]' });
    up.focus();
    up.click();
    expect(labelsOf()).toEqual(["B", "A", "C"]);
    expect(document.activeElement).toBe(
      control({ row: rows()[0], selector: '[data-action="move-up"]' }),
    );
  });

  it("moves a step, keeps focus on the pressed control and announces once", () => {
    openAndLoad();
    type({
      input: control({ row: rows()[0], selector: '[data-field="label"]' }),
      value: "A",
    });
    type({
      input: control({ row: rows()[1], selector: '[data-field="label"]' }),
      value: "B",
    });
    const down = control({
      row: rows()[0],
      selector: '[data-action="move-down"]',
    });
    down.focus();
    down.click();
    expect(labelsOf()).toEqual(["B", "A"]);
    const moved = control({
      row: rows()[1],
      selector: '[data-action="move-down"]',
    });
    expect(document.activeElement).toBe(moved);
    expect(callbacks.announce).toHaveBeenCalledTimes(1);
    expect(callbacks.announce).toHaveBeenCalledWith({
      message: "Step moved to position 2 of 2.",
    });
  });

  it("disables first-up and last-down with a reason and does nothing", () => {
    openAndLoad();
    const up = control({ row: rows()[0], selector: '[data-action="move-up"]' });
    const down = control({
      row: rows()[1],
      selector: '[data-action="move-down"]',
    });
    for (const button of [up, down]) {
      expect(button.getAttribute("aria-disabled")).toBe("true");
      expect(button.hasAttribute("disabled")).toBe(false);
      const reason = container.querySelector(
        `#${button.getAttribute("aria-describedby")}`,
      );
      expect(reason?.textContent).not.toBe("");
      button.focus();
      button.click();
      expect(document.activeElement).toBe(button);
    }
    expect(callbacks.announce).not.toHaveBeenCalled();
  });

  it("adds a step, focusing its label, and announces", () => {
    openAndLoad();
    container.querySelector<HTMLElement>('[data-action="add"]')?.click();
    expect(rows()).toHaveLength(3);
    expect(document.activeElement).toBe(
      control({ row: rows()[2], selector: '[data-field="label"]' }),
    );
    expect(callbacks.announce).toHaveBeenCalledWith({ message: "Step added." });
  });

  it("disables Add at the maximum with a visible reason", () => {
    openAndLoad();
    const add = container.querySelector<HTMLElement>('[data-action="add"]')!;
    while (rows().length < 8) {
      add.click();
    }
    expect(add.getAttribute("aria-disabled")).toBe("true");
    expect(container.querySelector(".flow-builder-reason")?.textContent).toBe(
      "At most 8 steps are allowed.",
    );
    add.focus();
    add.click();
    expect(rows()).toHaveLength(8);
    expect(document.activeElement).toBe(add);
  });

  it("disables Remove at the minimum, keeping focus and doing nothing", () => {
    openAndLoad();
    const remove = control({
      row: rows()[0],
      selector: '[data-action="remove"]',
    });
    expect(remove.getAttribute("aria-disabled")).toBe("true");
    remove.focus();
    remove.click();
    expect(rows()).toHaveLength(2);
    expect(document.activeElement).toBe(remove);
    expect(container.querySelector(".flow-builder-reason")?.textContent).toBe(
      "At least 2 steps are required.",
    );
  });

  it("removes a step and focuses the next row, else the previous", () => {
    openAndLoad();
    const add = container.querySelector<HTMLElement>('[data-action="add"]')!;
    add.click();
    add.click();
    const labelsBefore = rows().map((row) => row.dataset.stepKey);
    control({ row: rows()[1], selector: '[data-action="remove"]' }).click();
    expect(rows()).toHaveLength(3);
    expect(document.activeElement).toBe(
      control({ row: rows()[1], selector: '[data-field="label"]' }),
    );
    expect(rows()[1].dataset.stepKey).toBe(labelsBefore[2]);
    control({ row: rows()[2], selector: '[data-action="remove"]' }).click();
    expect(document.activeElement).toBe(
      control({ row: rows()[1], selector: '[data-field="label"]' }),
    );
    expect(callbacks.announce).toHaveBeenCalledWith({
      message: "Step removed.",
    });
  });

  it("swaps the event picker for endpoint and method on an API stream", () => {
    openAndLoad();
    pick({
      select: control({ row: rows()[0], selector: '[data-field="stream"]' }),
      value: "api",
    });
    expect(rows()[0].querySelector('[data-field="event_name"]')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Step 5: confirms, Escape and Delete
// ---------------------------------------------------------------------------

async function flush(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
}

function pressEscape({ target }: { target: HTMLElement }): KeyboardEvent {
  const event = new KeyboardEvent("keydown", {
    key: "Escape",
    bubbles: true,
    cancelable: true,
  });
  target.dispatchEvent(event);
  return event;
}

function dirtyLabel(): void {
  type({
    input: control({ row: rows()[0], selector: '[data-field="label"]' }),
    value: "x",
  });
}

function actionButton({ action }: { action: string }): HTMLElement {
  const found = container.querySelector<HTMLElement>(
    `[data-action="${action}"]`,
  );
  if (found === null) {
    throw new Error(`missing ${action}`);
  }
  return found;
}

function confirmEl(): HTMLElement | null {
  return container.querySelector<HTMLElement>(".flow-builder-confirm");
}

function confirmButton({ which }: { which: "confirm" | "safe" }): HTMLElement {
  const found = container.querySelector<HTMLElement>(
    `[data-confirm="${which}"]`,
  );
  if (found === null) {
    throw new Error(`missing ${which}`);
  }
  return found;
}

function form(): HTMLElement {
  const found = container.querySelector<HTMLElement>("form");
  if (found === null) {
    throw new Error("missing form");
  }
  return found;
}

describe("discard gate", () => {
  it("resolves true at once when clean, with no prompt", async () => {
    openAndLoad();
    await expect(builder.confirmDiscard()).resolves.toBe(true);
    expect(confirmEl()).toBeNull();
  });

  it("shows an alertdialog naming the flow, inerts the form and focuses Keep editing", async () => {
    openAndLoad({
      mode: "edit",
      entry: entryWith({
        steps: [
          { label: "a", event_name: "modal_open", stream: "ui" },
          { label: "b", event_name: "url_created", stream: "domain" },
        ],
      }),
    });
    dirtyLabel();
    const decision = builder.confirmDiscard();
    const dialog = confirmEl();
    expect(dialog?.getAttribute("role")).toBe("alertdialog");
    expect(dialog?.getAttribute("aria-labelledby")).toBeTruthy();
    expect(dialog?.getAttribute("aria-describedby")).toBeTruthy();
    expect(dialog?.textContent).toContain("My flow");
    expect(form().hasAttribute("inert")).toBe(true);
    expect(document.activeElement).toBe(confirmButton({ which: "safe" }));
    expect(builder.focusPendingConfirm()).toBe(true);
    confirmButton({ which: "safe" }).click();
    await expect(decision).resolves.toBe(false);
    expect(confirmEl()).toBeNull();
    expect(form().hasAttribute("inert")).toBe(false);
  });

  it("names a new flow as New flow", () => {
    openAndLoad();
    dirtyLabel();
    void builder.confirmDiscard();
    expect(confirmEl()?.textContent).toContain("New flow");
  });

  it("resolves true when the user discards", async () => {
    openAndLoad();
    dirtyLabel();
    const decision = builder.confirmDiscard();
    confirmButton({ which: "confirm" }).click();
    await expect(decision).resolves.toBe(true);
    expect(confirmEl()).toBeNull();
  });

  it("a second call while one is pending resolves false and opens no second prompt", async () => {
    openAndLoad();
    dirtyLabel();
    const first = builder.confirmDiscard();
    await expect(builder.confirmDiscard()).resolves.toBe(false);
    expect(container.querySelectorAll(".flow-builder-confirm")).toHaveLength(1);
    confirmButton({ which: "safe" }).click();
    await expect(first).resolves.toBe(false);
  });

  it("resolves false with no prompt while a Save is in flight", async () => {
    openAndLoad();
    dirtyLabel();
    fillValid();
    submit();
    expect(saves).toHaveLength(1);
    await expect(builder.confirmDiscard()).resolves.toBe(false);
    expect(confirmEl()).toBeNull();
  });

  it("closing the builder denies a pending discard instead of leaving it hanging", async () => {
    openAndLoad();
    dirtyLabel();
    const decision = builder.confirmDiscard();
    builder.close();
    await expect(decision).resolves.toBe(false);
  });

  it("focusPendingConfirm is false with no confirm open", () => {
    openAndLoad();
    expect(builder.focusPendingConfirm()).toBe(false);
  });
});

describe("cancel button and Escape", () => {
  it("Cancel on a clean form reports cancelled", async () => {
    openAndLoad();
    actionButton({ action: "cancel" }).click();
    await flush();
    expect(callbacks.onCancelled).toHaveBeenCalledTimes(1);
  });

  it("Cancel on a dirty form asks first and Keep editing returns focus to Cancel", async () => {
    openAndLoad();
    dirtyLabel();
    actionButton({ action: "cancel" }).click();
    expect(confirmEl()).not.toBeNull();
    expect(callbacks.onCancelled).not.toHaveBeenCalled();
    confirmButton({ which: "safe" }).click();
    await flush();
    expect(callbacks.onCancelled).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(actionButton({ action: "cancel" }));
  });

  it("discarding from the Cancel prompt reports cancelled", async () => {
    openAndLoad();
    dirtyLabel();
    actionButton({ action: "cancel" }).click();
    confirmButton({ which: "confirm" }).click();
    await flush();
    expect(callbacks.onCancelled).toHaveBeenCalledTimes(1);
  });

  it("Cancel is aria-disabled and inert while a Save is in flight", async () => {
    openAndLoad();
    dirtyLabel();
    fillValid();
    submit();
    const cancel = actionButton({ action: "cancel" });
    expect(cancel.getAttribute("aria-disabled")).toBe("true");
    cancel.click();
    await flush();
    expect(confirmEl()).toBeNull();
    expect(callbacks.onCancelled).not.toHaveBeenCalled();
  });

  it("Escape with nothing open runs Cancel through the gate", async () => {
    openAndLoad();
    const event = pressEscape({ target: nameInput() });
    await flush();
    expect(event.defaultPrevented).toBe(false);
    expect(callbacks.onCancelled).toHaveBeenCalledTimes(1);
  });

  it("Escape on a dirty form opens the discard prompt instead of cancelling", async () => {
    openAndLoad();
    dirtyLabel();
    pressEscape({ target: nameInput() });
    await flush();
    expect(confirmEl()).not.toBeNull();
    expect(callbacks.onCancelled).not.toHaveBeenCalled();
  });

  it("Escape on the open prompt takes the safe choice and does not start Cancel", async () => {
    openAndLoad();
    dirtyLabel();
    actionButton({ action: "cancel" }).click();
    const outer = vi.fn();
    document.body.addEventListener("keydown", outer);
    pressEscape({ target: confirmButton({ which: "safe" }) });
    document.body.removeEventListener("keydown", outer);
    await flush();
    expect(confirmEl()).toBeNull();
    expect(callbacks.onCancelled).not.toHaveBeenCalled();
    expect(outer).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(actionButton({ action: "cancel" }));
  });

  it("ignores Escape on a select", async () => {
    openAndLoad();
    dirtyLabel();
    pressEscape({
      target: control({ row: rows()[0], selector: '[data-field="stream"]' }),
    });
    await flush();
    expect(confirmEl()).toBeNull();
    expect(callbacks.onCancelled).not.toHaveBeenCalled();
  });

  it("lets an open confirm take Escape even when it comes from a select", async () => {
    openAndLoad();
    dirtyLabel();
    actionButton({ action: "cancel" }).click();
    pressEscape({
      target: control({ row: rows()[0], selector: '[data-field="stream"]' }),
    });
    await flush();
    expect(confirmEl()).toBeNull();
    expect(callbacks.onCancelled).not.toHaveBeenCalled();
  });

  it("does not let Escape on a select bubble past the builder", () => {
    openAndLoad();
    const outer = vi.fn();
    document.body.addEventListener("keydown", outer, { once: true });
    pressEscape({
      target: control({ row: rows()[0], selector: '[data-field="stream"]' }),
    });
    expect(outer).not.toHaveBeenCalled();
    document.body.removeEventListener("keydown", outer);
  });

  it("keeps Tab inside an open confirm", () => {
    openAndLoad();
    dirtyLabel();
    actionButton({ action: "cancel" }).click();
    const safe = confirmButton({ which: "safe" });
    const other = confirmButton({ which: "confirm" });
    const forward = new KeyboardEvent("keydown", {
      key: "Tab",
      bubbles: true,
      cancelable: true,
    });
    safe.dispatchEvent(forward);
    expect(forward.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(other);
    const back = new KeyboardEvent("keydown", {
      key: "Tab",
      shiftKey: true,
      bubbles: true,
      cancelable: true,
    });
    other.dispatchEvent(back);
    expect(back.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(safe);
  });

  it("ignores Escape that was already handled", async () => {
    openAndLoad();
    const event = new KeyboardEvent("keydown", {
      key: "Escape",
      bubbles: true,
      cancelable: true,
    });
    nameInput().addEventListener("keydown", (inner) => inner.preventDefault());
    nameInput().dispatchEvent(event);
    await flush();
    expect(callbacks.onCancelled).not.toHaveBeenCalled();
  });

  it("handles no other key", async () => {
    openAndLoad();
    for (const key of ["Home", "End", "Enter"]) {
      const event = new KeyboardEvent("keydown", {
        key,
        bubbles: true,
        cancelable: true,
      });
      nameInput().dispatchEvent(event);
      expect(event.defaultPrevented).toBe(false);
    }
    await flush();
    expect(callbacks.onCancelled).not.toHaveBeenCalled();
  });
});

describe("delete", () => {
  function openEdit(): void {
    openAndLoad({
      mode: "edit",
      entry: entryWith({
        steps: [
          { label: "a", event_name: "modal_open", stream: "ui" },
          { label: "b", event_name: "url_created", stream: "domain" },
        ],
      }),
    });
  }

  function startDelete(): SaveXhr {
    actionButton({ action: "delete" }).click();
    confirmButton({ which: "confirm" }).click();
    return saves[saves.length - 1];
  }

  it("is absent in create mode", () => {
    openAndLoad();
    expect(container.querySelector('[data-action="delete"]')).toBeNull();
  });

  it("asks first, names the stored flow, and warns about unsaved changes only when dirty", () => {
    openEdit();
    actionButton({ action: "delete" }).click();
    const dialog = confirmEl();
    expect(dialog?.getAttribute("data-kind")).toBe("delete");
    expect(dialog?.textContent).toContain("My flow");
    expect(dialog?.textContent).not.toContain("unsaved");
    expect(document.activeElement).toBe(confirmButton({ which: "safe" }));
    expect(form().hasAttribute("inert")).toBe(true);
    expect(deleteMock).not.toHaveBeenCalled();
    confirmButton({ which: "safe" }).click();

    dirtyLabel();
    type({ input: nameInput(), value: "Renamed" });
    actionButton({ action: "delete" }).click();
    expect(confirmEl()?.textContent).toContain("My flow");
    expect(confirmEl()?.textContent).not.toContain("Renamed");
    expect(confirmEl()?.textContent).toContain("unsaved");
  });

  it("Cancel on the confirm returns focus to Delete flow and sends nothing", () => {
    openEdit();
    actionButton({ action: "delete" }).click();
    confirmButton({ which: "safe" }).click();
    expect(confirmEl()).toBeNull();
    expect(document.activeElement).toBe(actionButton({ action: "delete" }));
    expect(deleteMock).not.toHaveBeenCalled();
  });

  it("Escape on the delete confirm cancels the confirm only", async () => {
    openEdit();
    actionButton({ action: "delete" }).click();
    pressEscape({ target: confirmButton({ which: "safe" }) });
    await flush();
    expect(confirmEl()).toBeNull();
    expect(callbacks.onCancelled).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(actionButton({ action: "delete" }));
  });

  it("focusPendingConfirm refocuses the Delete confirm's safe button", () => {
    openEdit();
    actionButton({ action: "delete" }).click();
    nameInput().focus();
    expect(builder.focusPendingConfirm()).toBe(true);
    expect(document.activeElement).toBe(confirmButton({ which: "safe" }));
  });

  it("cannot open a Delete confirm while a discard confirm is pending", () => {
    openEdit();
    dirtyLabel();
    void builder.confirmDiscard();
    actionButton({ action: "delete" }).click();
    expect(container.querySelectorAll(".flow-builder-confirm")).toHaveLength(1);
    expect(confirmEl()?.getAttribute("data-kind")).toBe("discard");
  });

  it("closing the builder mid-delete aborts the request and ignores its late failure", () => {
    openEdit();
    const xhr = startDelete();
    builder.close();
    expect(xhr.abort).toHaveBeenCalledTimes(1);
    failSave({ xhr, status: 500 });
    expect(callbacks.onDeleted).not.toHaveBeenCalled();
    expect(callbacks.onListStale).not.toHaveBeenCalled();
  });

  it("sends the delete and reports success", () => {
    openEdit();
    const xhr = startDelete();
    expect(deleteMock).toHaveBeenCalledWith({ flowId: "custom_1" });
    xhr.resolve({});
    expect(callbacks.onDeleted).toHaveBeenCalledWith({
      id: "custom_1",
      name: "My flow",
    });
  });

  it("shows Deleting... while in flight and blocks Cancel and a second Delete", async () => {
    openEdit();
    startDelete();
    expect(actionButton({ action: "delete" }).textContent).toBe("Deleting…");
    expect(confirmButton({ which: "confirm" }).textContent).toBe("Deleting…");
    expect(
      actionButton({ action: "delete" }).getAttribute("aria-disabled"),
    ).toBe("true");
    expect(
      actionButton({ action: "cancel" }).getAttribute("aria-disabled"),
    ).toBe("true");
    confirmButton({ which: "confirm" }).click();
    expect(deleteMock).toHaveBeenCalledTimes(1);
    await expect(builder.confirmDiscard()).resolves.toBe(false);
    pressEscape({ target: confirmButton({ which: "safe" }) });
    expect(confirmEl()).not.toBeNull();
  });

  it("ignores a stale delete response after the builder was reopened", () => {
    openEdit();
    const xhr = startDelete();
    openEdit();
    xhr.resolve({});
    expect(callbacks.onDeleted).not.toHaveBeenCalled();
  });

  it("is aria-disabled while a Save is in flight", () => {
    openEdit();
    dirtyLabel();
    submit();
    expect(updateMock).toHaveBeenCalledTimes(1);
    const button = actionButton({ action: "delete" });
    expect(button.getAttribute("aria-disabled")).toBe("true");
    button.click();
    expect(confirmEl()).toBeNull();
  });

  it("shows a 429 inline, keeps the draft and returns focus to Delete flow", () => {
    openEdit();
    dirtyLabel();
    const xhr = startDelete();
    failSave({ xhr, status: 429 });
    expect(formErrorText()).toContain("Too many requests");
    expect(confirmEl()).toBeNull();
    expect(builder.isDirty()).toBe(true);
    expect(document.activeElement).toBe(actionButton({ action: "delete" }));
    expect(
      actionButton({ action: "delete" }).getAttribute("aria-describedby"),
    ).toBe(container.querySelector(".flow-builder-form-errors")?.id);
    expect(actionButton({ action: "delete" }).textContent).toBe("Delete flow");
    expect(callbacks.onDeleted).not.toHaveBeenCalled();
  });

  it("stays silent for an already handled 429", () => {
    openEdit();
    const xhr = startDelete();
    xhr._429Handled = true;
    failSave({ xhr, status: 429 });
    expect(formErrorText()).toBe("");
    expect(confirmEl()).toBeNull();
  });

  it("a 404 with the missing-target code shows the already-deleted line and asks for a refresh", () => {
    openEdit();
    const xhr = startDelete();
    failSave({ xhr, status: 404, body: { errorCode: 5 } });
    expect(formErrorText()).toContain("My flow");
    expect(formErrorText()).toContain("already deleted");
    expect(callbacks.onListStale).toHaveBeenCalledTimes(1);
    expect(callbacks.onDeleted).not.toHaveBeenCalled();
  });

  it("a 404 without that code, and other failures, show the generic message", () => {
    openEdit();
    const first = startDelete();
    failSave({ xhr: first, status: 404, body: { errorCode: 99 } });
    expect(formErrorText()).toContain("Couldn't delete");
    expect(callbacks.onListStale).not.toHaveBeenCalled();
    const second = startDelete();
    failSave({ xhr: second, status: 500 });
    expect(formErrorText()).toContain("Couldn't delete");
  });

  it("a real abort restores the buttons without a message", () => {
    openEdit();
    const xhr = startDelete();
    failSave({ xhr, status: 0, readyState: 0, statusText: "abort" });
    expect(formErrorText()).toBe("");
    expect(actionButton({ action: "delete" }).textContent).toBe("Delete flow");
  });

  it("an offline failure surfaces the generic message", () => {
    openEdit();
    const xhr = startDelete();
    failSave({ xhr, status: 0, readyState: 0, statusText: "error" });
    expect(formErrorText()).toContain("Couldn't delete");
  });

  it("clears the Delete description once the user edits", () => {
    openEdit();
    const xhr = startDelete();
    failSave({ xhr, status: 500 });
    type({ input: nameInput(), value: "Other" });
    expect(
      actionButton({ action: "delete" }).hasAttribute("aria-describedby"),
    ).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Step 4: validation, save and error surfaces
// ---------------------------------------------------------------------------

const HIDDEN_FILTERS = [{ dim: "a" }, { dim: "b" }];
const HIDDEN_BREAKDOWN = { dim: "c" };

function nameInput(): HTMLInputElement {
  return control({
    row: container,
    selector: '[data-field="display_name"]',
  }) as HTMLInputElement;
}

function saveButton(): HTMLButtonElement {
  return control({
    row: container,
    selector: 'button[type="submit"]',
  }) as HTMLButtonElement;
}

function summary(): HTMLElement {
  return control({ row: container, selector: ".flow-builder-summary" });
}

function summaryLines(): string[] {
  return [...summary().querySelectorAll("li")].map(
    (item) => item.textContent ?? "",
  );
}

function formErrorText(): string {
  return (
    container.querySelector(".flow-builder-form-errors")?.textContent ?? ""
  );
}

function fillValid(): void {
  type({ input: nameInput(), value: "Funnel" });
  for (const row of rows()) {
    type({
      input: control({ row, selector: '[data-field="label"]' }),
      value: "Label",
    });
    pick({
      select: control({ row, selector: '[data-field="event_name"]' }),
      value: "modal_open",
    });
  }
}

function submit(): void {
  saveButton().click();
}

function savedEntry(): Entry {
  return {
    id: "custom_9",
    display_name: "Funnel",
    is_builtin: false,
    definition: { steps: [] },
    errors: {},
    first_invalid: null,
  };
}

function hiddenEntry(): Entry {
  return entryWith({
    steps: [
      {
        stream: "ui",
        label: "One",
        event_name: "modal_open",
        dim_filter: HIDDEN_FILTERS,
        drop_breakdown: HIDDEN_BREAKDOWN,
      },
      { stream: "ui", label: "Two", event_name: "modal_open" },
      { stream: "domain", label: "Three", event_name: "url_created" },
    ],
  });
}

describe("save", () => {
  it("shows a summary, focuses it and sends nothing when invalid", () => {
    openAndLoad();
    submit();
    expect(createMock).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(summary());
    expect(summary().getAttribute("tabindex")).toBe("-1");
    expect(summary().querySelector("h4")?.textContent).toBe(
      "5 problems to fix",
    );
    expect(nameInput().getAttribute("aria-invalid")).toBe("true");
    const describedBy = nameInput().getAttribute("aria-describedby");
    expect(document.getElementById(describedBy ?? "")?.textContent).toContain(
      "Enter a name",
    );
    expect(summary().querySelector('[role="alert"]')).toBeNull();
  });

  it("links each summary line to its field", () => {
    openAndLoad();
    submit();
    const links = [...summary().querySelectorAll("button")];
    expect(links).toHaveLength(5);
    expect(links.every((link) => link.type === "button")).toBe(true);
    links[0].click();
    expect(document.activeElement).toBe(nameInput());
    links[1].click();
    expect(document.activeElement).toBe(
      control({ row: rows()[0], selector: '[data-field="label"]' }),
    );
    expect(summaryLines()[1]).toBe(
      "Step 1: Enter a label of 1 to 64 characters.",
    );
  });

  it("clears a field's error and summary line when it is edited", () => {
    openAndLoad();
    submit();
    expect(summaryLines()).toHaveLength(5);
    type({ input: nameInput(), value: "Funnel" });
    expect(nameInput().hasAttribute("aria-invalid")).toBe(false);
    expect(summaryLines()).toHaveLength(4);
    expect(summary().querySelector("h4")?.textContent).toBe(
      "4 problems to fix",
    );
  });

  it("sends the generated body for a create and reports the saved entry", () => {
    openAndLoad();
    fillValid();
    submit();
    expect(createMock).toHaveBeenCalledTimes(1);
    const { definition } = createMock.mock.calls[0][0];
    expect(definition.display_name).toBe("Funnel");
    expect(definition.steps).toHaveLength(2);
    expect(saveButton().textContent).toBe("Saving…");
    expect(saveButton().getAttribute("aria-disabled")).toBe("true");
    saves[0].resolve({ status: "Success", ...savedEntry() });
    expect(callbacks.onSaved).toHaveBeenCalledWith({
      entry: savedEntry(),
      mode: "create",
    });
    expect(saveButton().textContent).toBe("Save flow");
  });

  it("ignores a second submit while saving", () => {
    openAndLoad();
    fillValid();
    submit();
    submit();
    container.querySelector("form")?.requestSubmit();
    expect(createMock).toHaveBeenCalledTimes(1);
  });

  it("updates through the flow id in edit mode", () => {
    openAndLoad({ mode: "edit", entry: hiddenEntry() });
    type({ input: nameInput(), value: "Renamed" });
    submit();
    expect(updateMock).toHaveBeenCalledTimes(1);
    expect(updateMock.mock.calls[0][0].flowId).toBe("custom_1");
    expect(createMock).not.toHaveBeenCalled();
    saves[0].resolve({ status: "Success", ...savedEntry() });
    expect(callbacks.onSaved).toHaveBeenCalledWith(
      expect.objectContaining({ mode: "edit" }),
    );
  });

  it("sends hidden filters and breakdown unchanged after rename, move and remove", () => {
    openAndLoad({ mode: "edit", entry: hiddenEntry() });
    type({ input: nameInput(), value: "Renamed" });
    control({ row: rows()[0], selector: '[data-action="move-down"]' }).click();
    control({ row: rows()[2], selector: '[data-action="remove"]' }).click();
    submit();
    const { steps } = updateMock.mock.calls[0][0].definition;
    expect(steps).toHaveLength(2);
    const moved = steps.find((step) => step.label === "One");
    expect(moved?.dim_filter).toEqual(HIDDEN_FILTERS);
    expect(moved?.drop_breakdown).toEqual(HIDDEN_BREAKDOWN);
  });

  it("only the Save button submits, and Add step does not", () => {
    openAndLoad({ mode: "edit", entry: hiddenEntry() });
    const buttons = [...container.querySelectorAll("button")];
    const submitters = buttons.filter((button) => button.type === "submit");
    expect(submitters).toEqual([saveButton()]);
    const onSubmit = vi.fn();
    container.querySelector("form")?.addEventListener("submit", onSubmit);
    control({ row: container, selector: '[data-action="add"]' }).click();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("lets Enter in the name and label inputs submit the form once", () => {
    openAndLoad();
    fillValid();
    const form = container.querySelector("form");
    const inputs = [
      nameInput(),
      control({ row: rows()[0], selector: '[data-field="label"]' }),
    ];
    for (const input of inputs) {
      // jsdom has no implicit submission; this is the HTML condition for it:
      // the input is in a form whose only submit button is Save.
      expect((input as HTMLInputElement).form).toBe(form);
      const enter = new KeyboardEvent("keydown", {
        key: "Enter",
        bubbles: true,
        cancelable: true,
      });
      input.dispatchEvent(enter);
      expect(enter.defaultPrevented).toBe(false);
    }
    expect(
      [...container.querySelectorAll("button")].filter(
        (button) => button.type === "submit",
      ),
    ).toHaveLength(1);
    form?.requestSubmit();
    expect(createMock).toHaveBeenCalledTimes(1);
  });

  it("keeps hidden-field errors when client validation also fails", () => {
    const entry = hiddenEntry();
    entry.errors = { "steps.0.dim_filter.0.dim": ["Unknown dimension."] };
    openAndLoad({ mode: "edit", entry });
    type({ input: nameInput(), value: "" });
    submit();
    expect(
      summaryLines().some((line) => line.includes("Unknown dimension.")),
    ).toBe(true);
    expect(rows()[0].textContent).toContain("Unknown dimension.");
  });

  it("links the steps error to the Add step button and clears it on add", () => {
    openAndLoad();
    // Remove-minimum is enforced by the UI, so the error arrives from the server.
    fillValid();
    submit();
    failSave({
      xhr: saves[0],
      status: 400,
      body: { errors: { steps: ["Too few steps."] } },
    });
    const add = control({ row: container, selector: '[data-action="add"]' });
    expect(add.getAttribute("aria-invalid")).toBe("true");
    const described = document.getElementById(
      add.getAttribute("aria-describedby") ?? "",
    );
    expect(described?.textContent).toBe("Too few steps.");
    expect(summaryLines()).toEqual(["Too few steps."]);
    add.click();
    expect(add.hasAttribute("aria-invalid")).toBe(false);
    expect(summary().hidden).toBe(true);
  });

  it("clears a step label edit's error, summary line and count", () => {
    openAndLoad();
    submit();
    const label = control({ row: rows()[0], selector: '[data-field="label"]' });
    expect(label.getAttribute("aria-invalid")).toBe("true");
    type({ input: label, value: "Named" });
    expect(label.hasAttribute("aria-invalid")).toBe(false);
    expect(summary().querySelector("h4")?.textContent).toBe(
      "4 problems to fix",
    );
    expect(summaryLines().join("|")).not.toContain("Step 1: Enter a label");
  });
});

describe("save failures", () => {
  function startSave(): SaveXhr {
    openAndLoad();
    fillValid();
    submit();
    return saves[0];
  }

  it("shows the rate-limit error and keeps every draft value on a 429", () => {
    const xhr = startSave();
    failSave({ xhr, status: 429 });
    expect(formErrorText()).toContain("Too many requests");
    expect(container.querySelector('[role="alert"]')).not.toBeNull();
    expect(container.querySelectorAll('[role="alert"]')).toHaveLength(1);
    expect(nameInput().value).toBe("Funnel");
    expect(labelsOf()).toEqual(["Label", "Label"]);
    expect(saveButton().getAttribute("aria-disabled")).toBeNull();
    expect(callbacks.onSaved).not.toHaveBeenCalled();
  });

  it("returns silently for an already-handled 429 and re-enables Save", () => {
    const xhr = startSave();
    xhr._429Handled = true;
    failSave({ xhr, status: 429 });
    expect(formErrorText()).toBe("");
    expect(saveButton().textContent).toBe("Save flow");
  });

  it("returns silently on an abort and keeps the draft", () => {
    const xhr = startSave();
    failSave({ xhr, status: 0, readyState: 0, statusText: "abort" });
    expect(formErrorText()).toBe("");
    expect(summary().hidden).toBe(true);
    expect(nameInput().value).toBe("Funnel");
    expect(saveButton().getAttribute("aria-disabled")).toBeNull();
  });

  it("shows the generic error for a timeout", () => {
    const xhr = startSave();
    failSave({ xhr, status: 0, readyState: 0, statusText: "timeout" });
    expect(formErrorText()).toContain("Couldn't save this flow");
    expect(nameInput().value).toBe("Funnel");
  });

  it("shows the generic error for a network failure, not a silent abort", () => {
    const xhr = startSave();
    failSave({ xhr, status: 0, readyState: 0, statusText: "error" });
    expect(formErrorText()).toContain("Couldn't save this flow");
    expect(saveButton().getAttribute("aria-disabled")).toBeNull();
  });

  it("clears a form error on the next edit", () => {
    const xhr = startSave();
    failSave({ xhr, status: 429 });
    expect(formErrorText()).not.toBe("");
    type({ input: nameInput(), value: "Other" });
    expect(formErrorText()).toBe("");
  });

  it("shows one form message for errorCode 11 with __root__", () => {
    const xhr = startSave();
    failSave({
      xhr,
      status: 400,
      body: {
        errorCode: 11,
        message: "Ignored.",
        errors: { __root__: ["Flow limit reached."] },
      },
    });
    expect(formErrorText()).toBe("Flow limit reached.");
  });

  it("falls back to the save-failed text for errorCode 11 without a message", () => {
    const xhr = startSave();
    failSave({ xhr, status: 400, body: { errorCode: 11 } });
    expect(formErrorText()).toContain("Couldn't save this flow");
  });

  it("shows the generic error for a 400 with empty errors", () => {
    const xhr = startSave();
    failSave({ xhr, status: 400, body: { errors: {} } });
    expect(formErrorText()).toContain("Couldn't save this flow");
  });

  it("shows the generic error for a create-mode 404 with errorCode 5", () => {
    const xhr = startSave();
    failSave({ xhr, status: 404, body: { errorCode: 5 } });
    expect(callbacks.onFlowMissing).not.toHaveBeenCalled();
    expect(formErrorText()).toContain("Couldn't save this flow");
  });

  it("keeps the summary and a form error apart on a mixed 400", () => {
    const xhr = startSave();
    failSave({
      xhr,
      status: 400,
      body: {
        errors: { display_name: ["Name already used."], __root__: ["Odd."] },
      },
    });
    expect(summaryLines()).toEqual(["Name already used."]);
    expect(formErrorText()).toBe("Odd.");
    expect(container.querySelectorAll('[role="alert"]')).toHaveLength(1);
  });

  it("describes an invalid step field with its message", () => {
    const xhr = startSave();
    failSave({
      xhr,
      status: 400,
      body: { errors: { "steps.1.event_name": ["Bad event."] } },
    });
    const select = control({
      row: rows()[1],
      selector: '[data-field="event_name"]',
    });
    const described = document.getElementById(
      select.getAttribute("aria-describedby") ?? "",
    );
    expect(described?.textContent).toBe("Bad event.");
  });

  it("reports an edit-mode 429 and re-enables Save", () => {
    openAndLoad({ mode: "edit", entry: hiddenEntry() });
    submit();
    expect(updateMock).toHaveBeenCalledTimes(1);
    failSave({ xhr: saves[0], status: 429 });
    expect(formErrorText()).toContain("Too many requests");
    expect(saveButton().getAttribute("aria-disabled")).toBeNull();
  });

  it("shows the generic error for an HTML 403 and keeps the draft", () => {
    const xhr = startSave();
    failSave({ xhr, status: 403 });
    expect(formErrorText()).toContain("Couldn't save this flow");
    expect(labelsOf()).toEqual(["Label", "Label"]);
  });

  it("clears a previous form error when Save is pressed again", () => {
    const xhr = startSave();
    failSave({ xhr, status: 500 });
    expect(formErrorText()).not.toBe("");
    submit();
    expect(formErrorText()).toBe("");
    expect(createMock).toHaveBeenCalledTimes(2);
  });

  it("calls onFlowMissing for an update 404 with errorCode 5", () => {
    openAndLoad({ mode: "edit", entry: hiddenEntry() });
    submit();
    failSave({ xhr: saves[0], status: 404, body: { errorCode: 5 } });
    expect(callbacks.onFlowMissing).toHaveBeenCalledWith({ id: "custom_1" });
    expect(formErrorText()).toBe("");
    expect(summary().hidden).toBe(true);
    expect(saveButton().getAttribute("aria-disabled")).toBeNull();
  });

  it("shows the generic error for a 404 without errorCode 5", () => {
    openAndLoad({ mode: "edit", entry: hiddenEntry() });
    submit();
    failSave({ xhr: saves[0], status: 404, body: { errorCode: 3 } });
    expect(callbacks.onFlowMissing).not.toHaveBeenCalled();
    expect(formErrorText()).toContain("Couldn't save this flow");
    expect(nameInput().value).toBe("My flow");
  });

  it("puts a duplicate-name error on the Display name field", () => {
    const xhr = startSave();
    failSave({
      xhr,
      status: 400,
      body: { errors: { display_name: ["Name already used."] } },
    });
    expect(
      document.getElementById(
        nameInput().getAttribute("aria-describedby") ?? "",
      )?.textContent,
    ).toBe("Name already used.");
    expect(nameInput().getAttribute("aria-invalid")).toBe("true");
    expect(summaryLines()).toEqual(["Name already used."]);
    expect(document.activeElement).toBe(summary());
    type({ input: nameInput(), value: "Other" });
    expect(nameInput().hasAttribute("aria-invalid")).toBe(false);
    expect(summary().hidden).toBe(true);
  });

  it("lands snake_case step paths on rows and inputs", () => {
    const xhr = startSave();
    failSave({
      xhr,
      status: 400,
      body: { errors: { "steps.1.event_name": ["Bad event."] } },
    });
    const select = control({
      row: rows()[1],
      selector: '[data-field="event_name"]',
    });
    expect(select.getAttribute("aria-invalid")).toBe("true");
    expect(rows()[1].textContent).toContain("Bad event.");
    expect(summaryLines()).toEqual(["Step 2: Bad event."]);
  });

  it("renders errorCode 11 as a form error, not on a field", () => {
    const xhr = startSave();
    failSave({
      xhr,
      status: 400,
      body: { errorCode: 11, message: "You have 20 flows." },
    });
    expect(formErrorText()).toBe("You have 20 flows.");
    expect(summary().hidden).toBe(true);
    expect(nameInput().hasAttribute("aria-invalid")).toBe(false);
  });

  it("renders an __root__ entry as a form error", () => {
    const xhr = startSave();
    failSave({
      xhr,
      status: 400,
      body: { errors: { __root__: ["Flow limit reached."] } },
    });
    expect(formErrorText()).toBe("Flow limit reached.");
    expect(summary().hidden).toBe(true);
  });

  it("shows an unrecognised path at form level", () => {
    const xhr = startSave();
    failSave({
      xhr,
      status: 400,
      body: { errors: { mystery: ["Odd."] } },
    });
    expect(formErrorText()).toBe("mystery: Odd.");
  });

  it("resolves server indexes against the keys that were sent", () => {
    const xhr = startSave();
    // While the request is in flight, the first step moves below the second.
    control({ row: rows()[0], selector: '[data-action="move-down"]' }).click();
    failSave({
      xhr,
      status: 400,
      body: { errors: { "steps.0.label": ["Too plain."] } },
    });
    // Step "0" at send time is now the second row.
    expect(rows()[1].textContent).toContain("Too plain.");
    expect(rows()[0].textContent).not.toContain("Too plain.");
    expect(summaryLines()).toEqual(["Step 2: Too plain."]);
  });

  it("sends a removed step's error to form level", () => {
    const xhr = startSave();
    // Add a step, then remove the first one: index 0 no longer exists.
    control({ row: container, selector: '[data-action="add"]' }).click();
    control({ row: rows()[0], selector: '[data-action="remove"]' }).click();
    failSave({
      xhr,
      status: 400,
      body: { errors: { "steps.0.label": ["Gone."] } },
    });
    expect(formErrorText()).toBe("steps.0.label: Gone.");
  });

  it("ignores a response after the builder closes", () => {
    const xhr = startSave();
    builder.close();
    failSave({ xhr, status: 500 });
    expect(callbacks.onSaved).not.toHaveBeenCalled();
    expect(xhr.abort).toHaveBeenCalledTimes(1);
  });
});

describe("open-time errors", () => {
  function attentionEntry(): Entry {
    const entry = entryWith({
      steps: [
        { stream: "ui", label: "", event_name: "modal_open" },
        { stream: "ui", label: "Two", event_name: "gone_event" },
      ],
    });
    entry.errors = {
      "steps.0.label": ["Too short."],
      "steps.1.event_name": ["Unknown event."],
    };
    return entry;
  }

  it("shows plain-text lines and describes the heading before the catalog loads", () => {
    builder.open({ mode: "edit", entry: attentionEntry() });
    expect(summary().hidden).toBe(false);
    expect(summary().querySelectorAll("button")).toHaveLength(0);
    expect(summaryLines()).toEqual([
      "Step 1: Too short.",
      "Step 2: Unknown event.",
    ]);
    const heading = container.querySelector("h3");
    const target = document.getElementById(
      heading?.getAttribute("aria-describedby") ?? "",
    );
    expect(target?.textContent).toBe("2 problems to fix");
    expect(builder.isDirty()).toBe(false);
  });

  it("keeps one summary node through failure, retry and success, then upgrades the lines", () => {
    builder.open({ mode: "edit", entry: attentionEntry() });
    const node = summary();
    const heading = container.querySelector("h3");
    const target = node.querySelector("h4")?.id;
    failCatalog({ xhr: pending[0] });
    expect(summary()).toBe(node);
    expect(node.querySelectorAll("button")).toHaveLength(0);
    expect(heading?.getAttribute("aria-describedby")).toBe(target);
    (document.activeElement as HTMLButtonElement).click();
    resolveCatalog({ xhr: pending[1] });
    expect(summary()).toBe(node);
    expect(node.querySelectorAll("button")).toHaveLength(2);
    expect(node.querySelector("h4")?.id).toBe(target);
    expect(heading?.getAttribute("aria-describedby")).toBe(target);
    expect(builder.isDirty()).toBe(false);
  });

  it("drops the heading description on the first edit", () => {
    openAndLoad({ mode: "edit", entry: attentionEntry() });
    const heading = container.querySelector("h3");
    expect(heading?.hasAttribute("aria-describedby")).toBe(true);
    type({ input: nameInput(), value: "New name" });
    expect(heading?.hasAttribute("aria-describedby")).toBe(false);
  });

  it("drops the heading description on Save", () => {
    openAndLoad({ mode: "edit", entry: attentionEntry() });
    submit();
    const heading = container.querySelector("h3");
    expect(heading?.hasAttribute("aria-describedby")).toBe(false);
    expect(document.activeElement).toBe(summary());
  });

  it("shows a filter error with step number, reason and guidance, no button", () => {
    const entry = hiddenEntry();
    entry.errors = { "steps.0.dim_filter.0.dim": ["Unknown dimension."] };
    openAndLoad({ mode: "edit", entry });
    expect(summaryLines()).toEqual([
      "Step 1: Unknown dimension. Filters can't be edited here yet: remove the step or delete the flow.",
    ]);
    expect(summary().querySelectorAll("button")).toHaveLength(0);
    const note = rows()[0].querySelector(".flow-builder-note");
    const reason = document.getElementById(
      note?.getAttribute("aria-describedby") ?? "",
    );
    expect(reason?.textContent).toBe("Unknown dimension.");
    expect(note?.textContent).toBe(
      "2 filters and a breakdown kept. Not editable yet.",
    );
  });
});

describe("row notes", () => {
  it("shows a kept note with the count for hidden filters", () => {
    openAndLoad({ mode: "edit", entry: hiddenEntry() });
    expect(rows()[0].querySelector(".flow-builder-note")?.textContent).toBe(
      "2 filters and a breakdown kept. Not editable yet.",
    );
    expect(rows()[1].querySelector(".flow-builder-note")).toBeNull();
  });

  it("removes the kept note, shows the removed note and announces once when the event changes", () => {
    openAndLoad({ mode: "edit", entry: hiddenEntry() });
    pick({
      select: control({ row: rows()[0], selector: '[data-field="stream"]' }),
      value: "domain",
    });
    const note = rows()[0].querySelector(".flow-builder-note");
    expect(note?.textContent).toBe(
      "Filters and breakdown removed because the event changed.",
    );
    expect(callbacks.announce).toHaveBeenCalledTimes(1);
    expect(callbacks.announce).toHaveBeenCalledWith({
      message: "Filters and breakdown removed because the event changed.",
    });
  });
});
