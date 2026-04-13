import type { components } from "./api.d.ts";

export type UtubDetail = components["schemas"]["SuccessEnvelope"] &
  components["schemas"]["UtubDetailSchema"];

export type UtubSummaryItem = components["schemas"]["UtubSummaryItemSchema"];
