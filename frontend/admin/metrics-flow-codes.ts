/**
 * HTTP statuses and API error codes the Flows tab and the flow builder both
 * branch on. Kept out of `metrics-query-client.ts` so the many dashboard tests
 * that mock that module need no extra exports.
 */

export const RATE_LIMITED_STATUS = 429;
export const NOT_FOUND_STATUS = 404;
export const BAD_REQUEST_STATUS = 400;

/** API `errorCode` for an update/delete of a flow that no longer exists. */
export const ERR_TARGET_NOT_FOUND = 5;
/** API `errorCode` for creating a flow past the per-deployment limit. */
export const ERR_FLOW_LIMIT = 11;
