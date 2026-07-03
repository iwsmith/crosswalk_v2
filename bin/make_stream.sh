#!/bin/bash

# Print usage/help
usage() {
    echo "Usage: $0 <input_dir> <output_dir> [rotation]"
    echo
    echo "Recursively processes all .gif files in <input_dir>,"
    echo "converts them using led-image-viewer, and writes .stream"
    echo "files to the same relative paths under <output_dir>."
    echo
    echo "Arguments:"
    echo "  input_dir     Source directory containing .gif files"
    echo "  output_dir    Destination directory for .stream files"
    echo "  rotation      (Optional) Rotation angle (default: 90)"
    echo
    echo "Example:"
    echo "  $0 ./gifs ./streams 180"
    echo
    echo "Options:"
    echo "  --help        Show this help message and exit"
    exit 1
}

# Handle help or missing args
if [[ "$1" == "--help" || $# -lt 2 || $# -gt 3 ]]; then
    usage
fi

INPUT_DIR="$1"
OUTPUT_DIR="$2"
ROTATION="${3:-90}"  # Default to 90 if not provided
EXT=".gif"
CMD="led-image-viewer"

# Use absolute paths
INPUT_DIR=$(realpath "$INPUT_DIR")
OUTPUT_DIR=$(realpath "$OUTPUT_DIR")

# Check input directory exists
if [[ ! -d "$INPUT_DIR" ]]; then
    echo "Error: Input directory '$INPUT_DIR' does not exist."
    exit 1
fi

COMMON_ARGS=(
  --led-cols=64
  --led-chain=2
  --led-gpio-mapping=adafruit-hat-pwm
  --led-pixel-mapper "U-mapper;Rotate:$ROTATION"
  # This is an offline gif->stream conversion, not a live display. Do NOT drop
  # privileges: the script runs as root and writes into a root-owned staging
  # dir, so dropping to the crosswalk user here would make every -O write fail
  # with permission denied and leave the stream dir empty. (We chown the
  # finished tree to crosswalk below, before swapping it in.)
  --led-no-drop-privs
)

# Build into a staging directory and swap it in atomically at the end so a
# running matrix driver never sees a half-populated stream directory. The
# staging dir is world-readable (mktemp defaults to 0700) so the unprivileged
# crosswalk service can read the swapped-in files.
STAGING="$(mktemp -d "${OUTPUT_DIR%/}.build.XXXXXX")"
chmod 0755 "$STAGING"
trap 'rm -rf "$STAGING"' EXIT

# Process all .gif files
find "$INPUT_DIR" -type f -name "*$EXT" | while read -r file; do
    # Get relative path and output location
    rel_path=$(realpath --relative-to="$INPUT_DIR" "$file")
    output_path="${rel_path%$EXT}.stream"
    full_output="$STAGING/$output_path"

    # Ensure output directory exists
    mkdir -p "$(dirname "$full_output")"

    echo "Processing $file → $full_output"
    $CMD "${COMMON_ARGS[@]}" "$file" -O"$full_output"
done

# led-image-viewer ran as root, so the streams are root-owned. Hand the tree to
# the crosswalk service user (which only needs read) before swapping it in.
chown -R crosswalk:crosswalk "$STAGING" 2>/dev/null || true

# Atomically replace the live directory with the freshly built one.
OLD="${OUTPUT_DIR%/}.old"
rm -rf "$OLD"
if [[ -d "$OUTPUT_DIR" ]]; then
    mv "$OUTPUT_DIR" "$OLD"
fi
mv "$STAGING" "$OUTPUT_DIR"
trap - EXIT
rm -rf "$OLD"