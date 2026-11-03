/**
 * Shared catalog and DOM helpers for the flow-builder nested-row tests.
 *
 * The catalog mirrors the real one's shapes (values dims, a status_code dim, a
 * group_by_only dim). `vi.mock` of the query client stays in each test file because
 * it is only hoisted there.
 */
import type { Schema } from "../../../types/api-helpers.d.ts";

type Catalog = Schema<"FlowCatalogResponseSchema">;
type CatalogDim = Schema<"FlowCatalogDimSchema">;
type Entry = Schema<"MetricFlowEntrySchema">;

function valuesDim({
  key,
  values,
  groupable = false,
}: {
  key: string;
  values: string[];
  groupable?: boolean;
}): CatalogDim {
  return { key, groupable, filter_kind: "values", values };
}

const DEVICE_DIM = valuesDim({
  key: "device_type",
  values: ["mobile", "desktop"],
});

export const MANY_DIMS_EVENT = "many_dims_event";
/** Groupable event with six filterable dims: the breakdown filter cap needs one. */
export const MANY_GROUPABLE_EVENT = "many_groupable_event";
export const ODD_KIND_EVENT = "odd_kind_event";

export const FILTER_CATALOG: Catalog = {
  event_groups: [
    {
      category: "ui",
      events: [
        {
          event_name: "ui_form_cancel",
          description: "",
          category: "ui",
          step_allowed: true,
          dims: [
            DEVICE_DIM,
            valuesDim({ key: "trigger", values: ["a", "b"], groupable: true }),
          ],
        },
        {
          event_name: "ui_url_create_open",
          description: "",
          category: "ui",
          step_allowed: true,
          dims: [DEVICE_DIM],
        },
        {
          event_name: "ui_group_only",
          description: "",
          category: "ui",
          step_allowed: true,
          dims: [
            {
              key: "bucket",
              groupable: true,
              filter_kind: "group_by_only",
              values: [],
            },
          ],
        },
        {
          event_name: ODD_KIND_EVENT,
          description: "",
          category: "ui",
          step_allowed: true,
          dims: [
            {
              key: "odd",
              groupable: false,
              // A kind the schema does not know yet (a newer backend).
              filter_kind: "future_kind" as never,
              values: [],
            },
          ],
        },
        {
          event_name: MANY_DIMS_EVENT,
          description: "",
          category: "ui",
          step_allowed: true,
          dims: [1, 2, 3, 4, 5, 6].map((index) =>
            valuesDim({ key: `dim_${index}`, values: ["x", "y"] }),
          ),
        },
        {
          event_name: MANY_GROUPABLE_EVENT,
          description: "",
          category: "ui",
          step_allowed: true,
          dims: [1, 2, 3, 4, 5, 6].map((index) =>
            valuesDim({
              key: `dim_${index}`,
              values: ["x", "y"],
              groupable: index === 1,
            }),
          ),
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
          dims: [DEVICE_DIM],
        },
      ],
    },
    {
      category: "api",
      events: [
        {
          event_name: "api_hit",
          description: "",
          category: "api",
          step_allowed: false,
          dims: [
            {
              key: "status_code",
              groupable: true,
              filter_kind: "status_code",
              values: [],
            },
          ],
        },
      ],
    },
  ],
  api_endpoints: [
    { endpoint: "urls.create_url", blueprint: "urls", methods: ["POST"] },
  ],
};

export function entryWith({
  steps,
}: {
  steps: Record<string, unknown>[];
}): Entry {
  return {
    id: "custom_1",
    display_name: "My flow",
    is_builtin: false,
    definition: { steps },
    errors: {},
    first_invalid: null,
  };
}

export function stepRows(container: HTMLElement): HTMLElement[] {
  return [...container.querySelectorAll<HTMLElement>(".flow-builder-step")];
}

export function filterRows(row: HTMLElement): HTMLElement[] {
  return [...row.querySelectorAll<HTMLElement>(".flow-builder-filter")];
}

export function control({
  root,
  selector,
}: {
  root: HTMLElement;
  selector: string;
}): HTMLElement {
  const found = root.querySelector<HTMLElement>(selector);
  if (found === null) {
    throw new Error(`missing ${selector}`);
  }
  return found;
}

export function addFilterButton({ row }: { row: HTMLElement }): HTMLElement {
  return control({ root: row, selector: '[data-action="add-filter"]' });
}

export function dimSelect({
  filterRow,
}: {
  filterRow: HTMLElement;
}): HTMLSelectElement {
  return control({
    root: filterRow,
    selector: '[data-field="filter_dim"]',
  }) as HTMLSelectElement;
}

export function valueControl({
  filterRow,
}: {
  filterRow: HTMLElement;
}): HTMLSelectElement | HTMLInputElement {
  return control({
    root: filterRow,
    selector: '[data-field="filter_value"]',
  }) as HTMLSelectElement | HTMLInputElement;
}

export function optionTexts({ select }: { select: HTMLElement }): string[] {
  return [...select.querySelectorAll("option")].map(
    (option) => option.textContent ?? "",
  );
}

export function pick({
  select,
  value,
}: {
  select: HTMLElement;
  value: string;
}): void {
  (select as HTMLSelectElement).value = value;
  select.dispatchEvent(new Event("change", { bubbles: true }));
}

export function type({
  input,
  value,
}: {
  input: HTMLElement;
  value: string;
}): void {
  (input as HTMLInputElement).value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

export function reasonText({ row }: { row: HTMLElement }): string {
  return (
    row.querySelector('.flow-builder-extras [id$="-filter-reason"]')
      ?.textContent ?? ""
  );
}
