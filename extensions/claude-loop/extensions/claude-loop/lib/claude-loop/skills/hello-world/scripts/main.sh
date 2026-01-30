#!/bin/bash
#
# hello-world skill - Example executable script
#
# Demonstrates script execution in the skills framework
#

set -euo pipefail

# Get current timestamp
timestamp=$(date "+%Y-%m-%d %H:%M:%S")

# Check if arguments provided
if [ $# -eq 0 ]; then
    # No arguments - default greeting
    echo "Hello, World!"
    echo "Executed at: $timestamp"
else
    # With arguments - personalized greeting
    for name in "$@"; do
        echo "Hello, $name!"
    done
    echo "Executed at: $timestamp"
fi

# Exit successfully
exit 0
