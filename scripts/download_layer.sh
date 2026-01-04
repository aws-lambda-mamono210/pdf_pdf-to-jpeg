#!/bin/bash
set -e

LAYER_NAME="aws-s3-utils-layer"
OUTPUT_DIR="layers"

LATEST_VERSION=$(aws lambda list-layer-versions \
  --layer-name "$LAYER_NAME" \
  --query 'LayerVersions[0].Version' \
  --output text)

echo "Latest version: $LATEST_VERSION"

DOWNLOAD_URL=$(aws lambda get-layer-version \
  --layer-name "$LAYER_NAME" \
  --version-number "$LATEST_VERSION" \
  --query 'Content.Location' \
  --output text)

rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

curl -s -o layer.zip "$DOWNLOAD_URL"

unzip layer.zip -d "$OUTPUT_DIR" >/dev/null
rm layer.zip

echo "Layer downloaded to $OUTPUT_DIR/"
