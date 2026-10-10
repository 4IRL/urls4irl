#!/bin/bash
# Downloads vendor JS bundles for offline development
# Run this once after cloning the repo or when updating vendor versions
set -euo pipefail

VENDOR_DIR="frontend/public/vendor"
mkdir -p "$VENDOR_DIR"

# --fail: an HTTP error must not be saved as the bundle. --retry-all-errors: retry timeouts too.
CURL_OPTS=(--fail --silent --show-error --location --connect-timeout 10 --max-time 60 --retry 3 --retry-all-errors)

echo "Downloading vendor JS bundles..."

# jQuery 3.7.1
curl "${CURL_OPTS[@]}" -o "$VENDOR_DIR/jquery-3.7.1.min.js" \
  "https://code.jquery.com/jquery-3.7.1.min.js"

# Bootstrap 5.2.3 JS bundle
curl "${CURL_OPTS[@]}" -o "$VENDOR_DIR/bootstrap.bundle.min.js" \
  "https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"

echo "✓ Vendor bundles downloaded to $VENDOR_DIR"
echo "✓ jQuery 3.7.1 and Bootstrap 5.2.3 are now available for offline use"
