#!/bin/bash
# Downloads vendor JS bundles for offline development
# Run this once after cloning the repo or when updating vendor versions
set -euo pipefail

VENDOR_DIR="frontend/public/vendor"
mkdir -p "$VENDOR_DIR"

# --fail: an HTTP error must not be saved as the bundle. --retry-all-errors: retry timeouts too.
CURL_OPTS=(--fail --silent --show-error --location --connect-timeout 10 --max-time 60 --retry 3 --retry-all-errors)

# Each download lands in a temp file and is moved into place only on success, so an
# interrupted download never leaves a partial bundle.
TMP_FILES=()
cleanup() {
  if [ "${#TMP_FILES[@]}" -gt 0 ]; then
    rm -f "${TMP_FILES[@]}"
  fi
}
trap cleanup EXIT

download() {
  local url="$1" file_name="$2" tmp_file
  tmp_file="$(mktemp "$VENDOR_DIR/.${file_name}.XXXXXX")"
  TMP_FILES+=("$tmp_file")
  curl "${CURL_OPTS[@]}" -o "$tmp_file" "$url"
  chmod 644 "$tmp_file" # mktemp creates 0600; the bundle must stay readable to other users
  mv "$tmp_file" "$VENDOR_DIR/$file_name"
}

echo "Downloading vendor JS bundles..."

# jQuery 3.7.1
download "https://code.jquery.com/jquery-3.7.1.min.js" "jquery-3.7.1.min.js"

# Bootstrap 5.2.3 JS bundle
download "https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js" "bootstrap.bundle.min.js"

echo "✓ Vendor bundles downloaded to $VENDOR_DIR"
echo "✓ jQuery 3.7.1 and Bootstrap 5.2.3 are now available for offline use"
