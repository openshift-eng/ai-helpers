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
jsonStr=$(sed 's/^var allBuilds = //' "$INPUT_FILE" | sed 's/.$//')

if [ $# -eq 0 ]; then
    echo "No keywords provided - copying all jobs..."
    echo "$jsonStr" | jq '{items: .items}' > "$OUTPUT_FILE"
else
    # Build the jq filter condition dynamically
    echo "Looking for jobs containing ALL of the following keywords:"
    JQ_FILTER=""
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
TOTAL_COUNT=$(echo "$jsonStr" | jq '.items | length')
FILTERED_COUNT=$(cat "$OUTPUT_FILE" | jq ".|length")

echo ""
echo "Done!"
echo "Total jobs: $TOTAL_COUNT"
echo "Filtered jobs: $FILTERED_COUNT"
echo "Output saved to: $OUTPUT_FILE"
