#!/usr/bin/env bash
# Fetch the optional third-party example pack from The Sound Archive.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORMAT="${1:-wav}"
case "$FORMAT" in
    wav|mp3) ;;
    *)
        echo "Usage: ./download.sh [wav|mp3]" >&2
        exit 2
        ;;
esac

DESTINATION="$SCRIPT_DIR/downloads/$FORMAT"
BASE_URL="https://www.thesoundarchive.com/simpsons/homer"
mkdir -p "$DESTINATION"

SOURCES=(mbeernut mburger mchocola mcrumble organized mmurinal)
NAMES=(
    "Mmmm, Beernuts"
    "Mmmm, Burgers"
    "Mmmm, Chocolate"
    "Mmmm, Crumbled up cookie things"
    "Mmmm, Organized crime"
    "Mmmm, Urinal fresh"
)

for INDEX in "${!SOURCES[@]}"; do
    OUTPUT="$DESTINATION/${NAMES[$INDEX]}.$FORMAT"
    echo "Downloading ${NAMES[$INDEX]}..."
    curl --fail --location --silent --show-error \
        "$BASE_URL/${SOURCES[$INDEX]}.$FORMAT" \
        --output "$OUTPUT"
done

echo "Downloaded ${#SOURCES[@]} files to $DESTINATION"
echo "These recordings are third-party media and are not covered by this project's MIT license."
