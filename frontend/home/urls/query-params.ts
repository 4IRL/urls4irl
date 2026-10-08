import { APP_CONFIG } from "../../lib/config.js";

export interface QueryParamSegment {
  index: number;
  raw: string;
  name: string;
  isAutoStripped: boolean;
}

export interface ParsedQuery {
  /**
   * The text before the first `?` or `#`, verbatim (with `https://` prepended
   * when the input had no protocol): scheme, userinfo, host, port AND path.
   */
  beforeQuery: string;
  /** Protocol without the trailing `:`, lowercased by the `URL` API. */
  scheme: string;
  segments: QueryParamSegment[];
  fragment: string;
  hadQuery: boolean;
}

/** Form-decodes a query name like `URLSearchParams`; a malformed escape keeps the raw name. */
function decodeParamName(name: string): string {
  const spaced = name.replace(/\+/g, " ");
  try {
    return decodeURIComponent(spaced);
  } catch {
    return spaced;
  }
}

/**
 * Mirrors `UrlValidator._is_tracking_param`: the name is percent-decoded (the
 * server matches after `URLSearchParams` decoding), lowercased, matched exactly
 * or by prefix, and only for the web schemes the server strips.
 */
export function isAutoStrippedParam({
  name,
  scheme,
}: {
  name: string;
  scheme: string;
}): boolean {
  const {
    TRACKING_QUERY_PARAMS,
    TRACKING_QUERY_PARAM_PREFIXES,
    TRACKING_STRIP_SCHEMES,
  } = APP_CONFIG.constants;
  if (!TRACKING_STRIP_SCHEMES.includes(scheme.toLowerCase())) return false;
  const lowered = decodeParamName(name).toLowerCase();
  return (
    TRACKING_QUERY_PARAMS.includes(lowered) ||
    TRACKING_QUERY_PARAM_PREFIXES.some((prefix) => lowered.startsWith(prefix))
  );
}

interface TrimArgs {
  original: string;
  parsed: ParsedQuery;
  droppedIndexes: ReadonlySet<number>;
}

const PROTOCOL_REGEX = /^[a-z][a-z0-9+.-]*:/i;

/**
 * Splits a URL's query into positional segments by plain text, never via
 * URLSearchParams, so surviving segments can be re-emitted byte-for-byte.
 */
export function parseQuerySegments(urlString: string): ParsedQuery | null {
  if (!urlString || typeof urlString !== "string") return null;

  const candidate = PROTOCOL_REGEX.test(urlString)
    ? urlString
    : "https://" + urlString;
  if (!URL.canParse(candidate)) return null;
  const parsedUrl = new URL(candidate);

  const hashIndex = candidate.indexOf("#");
  const fragment = hashIndex === -1 ? "" : candidate.slice(hashIndex);
  const beforeHash =
    hashIndex === -1 ? candidate : candidate.slice(0, hashIndex);

  const queryIndex = beforeHash.indexOf("?");
  const hadQuery = queryIndex !== -1;
  const query = hadQuery ? beforeHash.slice(queryIndex + 1) : "";

  // Verbatim text before the first `?`/`#`: re-serializing via the URL API would
  // drop userinfo, resolve dot-segments and normalize spaces/backslashes.
  const beforeQuery = hadQuery ? beforeHash.slice(0, queryIndex) : beforeHash;

  const segments: QueryParamSegment[] =
    query === ""
      ? []
      : query.split("&").map((raw, index) => {
          const equalsIndex = raw.indexOf("=");
          return {
            index,
            raw,
            name: equalsIndex === -1 ? raw : raw.slice(0, equalsIndex),
            isAutoStripped: false,
          };
        });

  return {
    beforeQuery,
    scheme: parsedUrl.protocol.slice(0, -1),
    segments,
    fragment,
    hadQuery,
  };
}

function rebuild({
  parsed,
  shouldRemove,
}: {
  parsed: ParsedQuery;
  shouldRemove: (segment: QueryParamSegment) => boolean;
}): string {
  const surviving = parsed.segments
    .filter((segment) => !shouldRemove(segment))
    .map((segment) => segment.raw);
  const query = surviving.length > 0 ? "?" + surviving.join("&") : "";
  return parsed.beforeQuery + query + parsed.fragment;
}

/** The string to submit: user-dropped segments removed; original returned untouched if none. */
export function buildTrimmedUrl({
  original,
  parsed,
  droppedIndexes,
}: TrimArgs): string {
  if (droppedIndexes.size === 0) return original;
  return rebuild({
    parsed,
    shouldRemove: (segment) => droppedIndexes.has(segment.index),
  });
}

/** The string the user will see stored: also removes segments the server strips. */
export function previewStoredUrl({
  original,
  parsed,
  droppedIndexes,
}: TrimArgs): string {
  const hasAutoStripped = parsed.segments.some(
    (segment) => segment.isAutoStripped,
  );
  if (droppedIndexes.size === 0 && !hasAutoStripped) return original;
  return rebuild({
    parsed,
    shouldRemove: (segment) =>
      droppedIndexes.has(segment.index) || segment.isAutoStripped,
  });
}
