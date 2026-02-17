export function isValidURL(inputURL) {
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

export function generateURLObj(inputURL) {
  try {
    return new URL(inputURL);
  } catch {
    return null;
  }
}
