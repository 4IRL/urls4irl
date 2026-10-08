import { APP_CONFIG } from "../../lib/config.js";

export interface QueryParamSegment {
  index: number;
  raw: string;
  name: string;
  hasValue: boolean;
  value: string;
  isAutoStripped: boolean;
}

export interface ParsedQuery {
  /** Everything before the `?`: scheme, host, port AND path (never a bare `URL.origin`). */
  beforeQuery: string;
  /** Protocol without the trailing `:`, lowercased by the `URL` API. */
  scheme: string;
  segments: QueryParamSegment[];
  fragment: string;
  hadQuery: boolean;
}

/**
 * Mirrors `UrlValidator._is_tracking_param`: the name is lowercased, matched
 * exactly or by prefix, and only for the web schemes the server strips.
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
  const lowered = name.toLowerCase();
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

  // Non-special schemes (e.g. mailto:) have an opaque "null" origin.
  const beforeQuery =
    parsedUrl.origin === "null"
      ? hadQuery
        ? beforeHash.slice(0, queryIndex)
        : beforeHash
      : parsedUrl.origin + parsedUrl.pathname;

  const segments: QueryParamSegment[] =
    query === ""
      ? []
      : query.split("&").map((raw, index) => {
          const equalsIndex = raw.indexOf("=");
          const hasValue = equalsIndex !== -1;
          return {
            index,
            raw,
            name: hasValue ? raw.slice(0, equalsIndex) : raw,
            hasValue,
            value: hasValue ? raw.slice(equalsIndex + 1) : "",
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
