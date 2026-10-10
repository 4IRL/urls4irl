import { hasUnsupportedSchemePrefix } from "./scheme/scheme-utils.js";

// Instant client-side whitelist check: rejects `foo://x`-style prefixes that
// are not in the backend scheme whitelist. Scheme-less text and host:port pass.
export function isSupportedURLScheme({
  urlString,
}: {
  urlString: string;
}): boolean {
  return !hasUnsupportedSchemePrefix({ text: urlString });
}

export function isValidURL(inputURL: string): boolean {
  if (!inputURL || typeof inputURL !== "string") {
    return false;
  }

  let modifiedURL = inputURL.toLowerCase();

  modifiedURL = modifiedURL.trim();
  if (!modifiedURL) return false;

  const protocolRegex = /^[a-z][a-z0-9+.-]*:/;

  // If no protocol is found in the URL, we add https as default
  if (!protocolRegex.test(modifiedURL)) {
    modifiedURL = "https://" + modifiedURL;
  }

  if (!URL.canParse(modifiedURL)) return false;

  const url = generateURLObj(modifiedURL);
  if (!url) return false;

  const protocol = url.protocol;
  const invalidProtocols = ["javascript:", "data:", "vbscript:"];

  if (invalidProtocols.includes(protocol)) return false;

  return true;
}

export function generateURLObj(inputURL: string): URL | null {
  try {
    return new URL(inputURL);
  } catch {
    return null;
  }
}
