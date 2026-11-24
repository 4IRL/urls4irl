/**
 * HTTP statuses the Flows tab and the flow builder both
 * branch on. Kept out of `metrics-query-client.ts` so the many dashboard tests
 * that mock that module need no extra exports.
 */

export const RATE_LIMITED_STATUS = 429;
export const NOT_FOUND_STATUS = 404;
export const BAD_REQUEST_STATUS = 400;
