import type { components, operations } from "./api.d.ts";

export type Schema<Name extends keyof components["schemas"]> =
  components["schemas"][Name];

export type SuccessResponse<
  Op extends keyof operations,
  Status extends keyof operations[Op]["responses"] & (200 | 201) = Extract<
    keyof operations[Op]["responses"],
    200
  >,
> = operations[Op]["responses"][Status]["content"]["application/json"];
