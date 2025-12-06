#!/bin/bash

# Script to filter jobs from all_jobs.json
# Filters jobs where the name contains ALL specified keywords
# Usage: ./filter_jobs.sh INPUT_FILE OUTPUT_FILE [keyword1]
# Example: ./filter_jobs.sh input.json output.json
# Example: ./filter_jobs.sh input.json output.json "release-4.21 upgrade"

# Check if at least 2 arguments are provided (input and output files)
if [ $# -lt 2 ]; then
    echo "Error: Missing required arguments."
    echo "Usage: $0 INPUT_FILE OUTPUT_FILE [keyword1]"
    echo "Example: $0 all_jobs.json filtered_jobs.json"
    echo "Example: $0 all_jobs.json filtered_jobs.json 'release-4.21 upgrade'"
    exit 1
fi

INPUT_FILE="$1"
OUTPUT_FILE="$2"
shift 2  # Remove first two arguments, remaining are keywords

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "Error: jq is not installed. Please install jq to use this script."
    exit 1
fi

# Check if input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: Input file $INPUT_FILE not found."
    exit 1
fi

echo "Filtering jobs from $INPUT_FILE..."

# If no keywords provided, copy all jobs
# Strip JavaScript variable wrapper: "var allBuilds = " prefix and trailing ";"
jsonStr=$(sed 's/^var allBuilds = //' "$INPUT_FILE" | sed 's/;$//')

# Validate we got valid JSON
if ! echo "$jsonStr" | jq empty 2>/dev/null; then
    echo "Error: Failed to extract valid JSON from $INPUT_FILE"
    echo "Expected format: var allBuilds = {...};"
    exit 1
fi

if [ $# -eq 0 ]; then
    echo "No keywords provided - including all ProwJob items..."
    echo "$jsonStr" | \
        jq '.items[] | select(.kind == "ProwJob")' | \
        jq -s 'map({name: .spec.job, state: .status.state, url: .status.url})' \
        > "$OUTPUT_FILE"
else
    # Build the jq filter condition dynamically
    echo "Looking for jobs containing ALL of the following keywords:"
    JQ_FILTER=""
    # shellcheck disable=SC2068
    for keyword in $@; do
        echo "  - $keyword"
        JQ_FILTER="$JQ_FILTER | select(.spec.job | contains(\"$keyword\"))"
    done
    
    echo -e "Filter: " '.items[] | select(.kind == "ProwJob")'"$JQ_FILTER"''

    # Extract the JavaScript variable and convert to proper JSON, then filter
    # The file starts with "var allBuilds = " so we need to strip that
    
    echo "$jsonStr" | \
     	jq '.items[] | select(.kind == "ProwJob")'"$JQ_FILTER"'' | \
    	jq -s 'map({name: .spec.job, state: .status.state, url: .status.url})'> "$OUTPUT_FILE"
fi

# Count the filtered jobs
TOTAL_COUNT=$(echo "$jsonStr" | jq '.items | length' 2>/dev/null || echo "0")
FILTERED_COUNT=$(jq 'length' "$OUTPUT_FILE" 2>/dev/null || echo "0")

echo ""
echo "Done!"
echo "Total jobs: $TOTAL_COUNT"
echo "Filtered jobs: $FILTERED_COUNT"
echo "Output saved to: $OUTPUT_FILE"
