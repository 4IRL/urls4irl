/**
 * Returns the `next` value and its query string only when `next` is the
 * page's single param, otherwise null. The server
 * (verify_and_provide_next_page) stays the gate.
 */
export function getForwardableNextQuery(
  search: string,
): { value: string; query: string } | null {
  const searchParams = new URLSearchParams(search);
  const value = searchParams.get("next");
  if (searchParams.size === 1 && value !== null) {
    return { value, query: searchParams.toString() };
  }
  return null;
}
