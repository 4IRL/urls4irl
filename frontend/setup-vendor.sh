#!/bin/bash
# Downloads vendor JS bundles for offline development
# Run this once after cloning the repo or when updating vendor versions

VENDOR_DIR="frontend/public/vendor"
mkdir -p "$VENDOR_DIR"

echo "Downloading vendor JS bundles..."

# jQuery 3.7.1
curl -o "$VENDOR_DIR/jquery-3.7.1.min.js" \
  "https://code.jquery.com/jquery-3.7.1.min.js"

# Bootstrap 5.2.3 JS bundle
curl -o "$VENDOR_DIR/bootstrap.bundle.min.js" \
  "https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"

echo "✓ Vendor bundles downloaded to $VENDOR_DIR"
echo "✓ jQuery 3.7.1 and Bootstrap 5.2.3 are now available for offline use"
