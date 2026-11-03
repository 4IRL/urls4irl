/**
 * A realistic flow catalog for builder state tests: the dim shapes the real
 * catalog serves (closed-set `values`, `status_code`, `group_by_only`).
 */
import type { Schema } from "../../../types/api-helpers.d.ts";

type Catalog = Schema<"FlowCatalogResponseSchema">;
type Dim = Schema<"FlowCatalogDimSchema">;

const DEVICE_TYPE: Dim = {
  key: "device_type",
  groupable: false,
  filter_kind: "values",
  values: ["desktop", "mobile"],
};

export const FLOW_CATALOG_MOCK: Catalog = {
  event_groups: [
    {
      category: "ui",
      events: [
        {
          event_name: "ui_form_cancel",
          description: "",
          category: "ui",
          step_allowed: false,
          dims: [
            DEVICE_TYPE,
            {
              key: "trigger",
              groupable: true,
              filter_kind: "values",
              values: ["button", "escape"],
            },
            {
              key: "form",
              groupable: false,
              filter_kind: "values",
              values: ["utub", "url"],
            },
          ],
        },
        {
          event_name: "ui_form_submit",
          description: "",
          category: "ui",
          step_allowed: true,
          dims: [DEVICE_TYPE],
        },
        {
          event_name: "ui_url_create_open",
          description: "",
          category: "ui",
          step_allowed: true,
          dims: [DEVICE_TYPE],
        },
      ],
    },
    {
      category: "domain",
      events: [
        {
          event_name: "url_create_rejected",
          description: "",
          category: "domain",
          step_allowed: true,
          dims: [
            DEVICE_TYPE,
            {
              key: "reason",
              groupable: true,
              filter_kind: "values",
              values: ["duplicate", "invalid"],
            },
            {
              key: "bucket_only",
              groupable: true,
              filter_kind: "group_by_only",
              values: [],
            },
          ],
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
