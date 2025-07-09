#!/bin/bash

# Print usage/help
usage() {
    echo "Usage: $0 <input_dir> <output_dir>"
    echo
    echo "Recursively processes all .gif files in <input_dir>,"
    echo "converts them using led-image-viewer, and writes .stream"
    echo "files to the same relative paths under <output_dir>."
    echo
    echo "Example:"
    echo "  $0 ./gifs ./streams"
    echo
    echo "Options:"
    echo "  --help       Show this help message and exit"
    exit 1
}

# Handle help or missing args
if [[ "$1" == "--help" || $# -ne 2 ]]; then
    usage
fi

INPUT_DIR="$1"
OUTPUT_DIR="$2"
EXT=".gif"
CMD="led-image-viewer"
COMMON_ARGS=(--led-cols=64 --led-chain=2 --led-gpio-mapping=adafruit-hat-pwm --led-pixel-mapper "U-mapper" --led-no-drop-privs)

# Ensure input directory is absolute and exists
INPUT_DIR=$(realpath "$INPUT_DIR")
OUTPUT_DIR=$(realpath "$OUTPUT_DIR")

if [[ ! -d "$INPUT_DIR" ]]; then
    echo "Error: Input directory '$INPUT_DIR' does not exist."
    exit 1
fi

rm -rf $OUTPUT_DIR/*

# Process all .gif files
find "$INPUT_DIR" -type f -name "*$EXT" | while read -r file; do
    # Compute relative path and output file
    rel_path=$(realpath --relative-to="$INPUT_DIR" "$file")
    output_path="${rel_path%$EXT}.stream"
    full_output="$OUTPUT_DIR/$output_path"

    # Create output directory
    mkdir -p "$(dirname "$full_output")"

    echo "Processing $file → $full_output"
    $CMD "${COMMON_ARGS[@]}" "$file" -O"$full_output"
done
