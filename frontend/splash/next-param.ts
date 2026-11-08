/**
 * Returns the page's query string only when `next` is its single param,
 * otherwise null. The server (verify_and_provide_next_page) stays the gate.
 */
export function getForwardableNextQuery(search: string): string | null {
  const searchParams = new URLSearchParams(search);
  if (searchParams.size === 1 && searchParams.get("next") !== null) {
    return searchParams.toString();
  }
  return null;
}
