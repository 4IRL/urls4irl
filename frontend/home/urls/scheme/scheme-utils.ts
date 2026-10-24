import { APP_CONFIG } from "../../../lib/config.js";

export interface SchemeSplit {
  scheme: string;
  rest: string;
}

// `token:remainder`. `s` lets the remainder span newlines; the token is
// lowercased by callers before any whitelist lookup.
const SCHEME_PREFIX_REGEX = /^([a-z][a-z0-9+.-]*):(.*)$/is;
const HOST_PORT_REMAINDER_REGEX = /^\d{1,5}(?:[/?#]|$)/;
const CREDENTIALS_REMAINDER_REGEX = /^[^/?#]*@/;
const AUTHORITY_SLASHES_REGEX = /^\/\//;

function isWhitelistedScheme({ scheme }: { scheme: string }): boolean {
  return APP_CONFIG.constants.URL_SCHEMES.includes(scheme);
}

function escapeRegexLiteral({ value }: { value: string }): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// Lossless-or-null invariant: a split is returned only when composeURL on the
// result reproduces the input (modulo scheme case / leading whitespace).
// Anything that would not round-trip (an authority scheme without `//`, e.g.
// `ssh:22`, which is host:port, or with extra slashes, e.g. `https:////x`)
// yields null so nothing is stripped.
export function splitScheme({
  urlString,
}: {
  urlString: string;
}): SchemeSplit | null {
  const match = SCHEME_PREFIX_REGEX.exec(urlString.trimStart());
  if (match === null) return null;

  const scheme = match[1].toLowerCase();
  const remainder = match[2];
  if (!isWhitelistedScheme({ scheme })) return null;

  if (!isAuthorityScheme({ scheme })) {
    return { scheme, rest: remainder };
  }

  if (!AUTHORITY_SLASHES_REGEX.test(remainder)) return null;
  const rest = remainder.replace(AUTHORITY_SLASHES_REGEX, "");
  if (rest.startsWith("/")) return null;
  return { scheme, rest };
}

export function isAuthorityScheme({ scheme }: { scheme: string }): boolean {
  return APP_CONFIG.constants.URL_AUTHORITY_SCHEMES.includes(scheme);
}

export function composeURL({
  scheme,
  text,
}: {
  scheme: string;
  text: string;
}): string {
  const trimmedText = text.trim();
  if (trimmedText === "") return "";

  // A selection outside the whitelist cannot be composed safely.
  if (!isWhitelistedScheme({ scheme })) return trimmedText;

  const isAuthority = isAuthorityScheme({ scheme });

  // Opaque selections deliberately skip the recognized-scheme and
  // unsupported-prefix passthroughs below: whatever follows `scheme:` is kept
  // verbatim so the round trip stays lossless (`spotify:track:x`,
  // `feed:https://x`). Only authority selections treat text carrying its own
  // scheme as an already-complete URL.
  if (!isAuthority) return `${scheme}:${trimmedText}`;

  if (splitScheme({ urlString: trimmedText }) !== null) return trimmedText;

  // An unsupported prefix (`foo://x`, `javascript:alert(1)`) is left as typed
  // so validation rejects it rather than hiding it behind the selector.
  if (hasUnsupportedSchemePrefix({ text: trimmedText })) return trimmedText;

  // A whitelisted `token:` that is neither host:port nor credentials is a
  // malformed URL (`https:/example.com`, `https:////x`): leave it for the
  // server to reject instead of producing `https://https:/example.com`.
  const match = SCHEME_PREFIX_REGEX.exec(trimmedText);
  if (
    match !== null &&
    isWhitelistedScheme({ scheme: match[1].toLowerCase() })
  ) {
    const remainder = match[2];
    if (
      !HOST_PORT_REMAINDER_REGEX.test(remainder) &&
      !CREDENTIALS_REMAINDER_REGEX.test(remainder)
    ) {
      return trimmedText;
    }
  }

  return `${scheme}://${trimmedText.replace(AUTHORITY_SLASHES_REGEX, "")}`;
}

export function hasUnsupportedSchemePrefix({
  text,
}: {
  text: string;
}): boolean {
  const match = SCHEME_PREFIX_REGEX.exec(text.trimStart());
  if (match === null) return false;

  if (isWhitelistedScheme({ scheme: match[1].toLowerCase() })) return false;

  const remainder = match[2];
  // `localhost:8080`, `example.com:8080/x`
  if (HOST_PORT_REMAINDER_REGEX.test(remainder)) return false;
  // `user:pass@host.com` - the server reports its own error for these.
  if (CREDENTIALS_REMAINDER_REGEX.test(remainder)) return false;

  return true;
}

// Dev hosts (localhost, 127.0.0.1, ...) rarely serve TLS, so a non-explicit
// selector shows `http` for them and the caller's fallback for everything else.
const DEV_HOST_SCHEME = "http";

export function defaultSchemeForText({
  text,
  fallbackScheme,
}: {
  text: string;
  fallbackScheme: string;
}): string {
  return isDevHostText({ text }) ? DEV_HOST_SCHEME : fallbackScheme;
}

export function isDevHostText({ text }: { text: string }): boolean {
  const hosts = APP_CONFIG.constants.URL_DEV_HOSTS;
  if (hosts.length === 0) return false;

  const alternation = hosts
    .map((host) => escapeRegexLiteral({ value: host }))
    .join("|");
  const devHostRegex = new RegExp(
    `^(?:${alternation})(?::\\d{1,5})?(?:[/?#]|$)`,
    "i",
  );
  return devHostRegex.test(text.trim());
}
