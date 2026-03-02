#!/bin/bash
set -e

# Check the method and URL
if [[ "$1" == "POST" && "$2" =~ ^https://discord\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]+$ ]]; then
    # Allow POST requests to Discord webhooks
    # $3 contains the message content
    /usr/bin/curl.real -s -d "{\"content\":\"$3\"}" \
        -H "Content-Type: application/json" \
        -X POST "$2"
else
    echo "Error: Unauthorized URL or method"
    exit 1
fi
