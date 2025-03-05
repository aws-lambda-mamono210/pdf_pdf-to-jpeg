#!/bin/bash

# レイヤー名を設定
LAYER_NAME="aws-s3-utils-layer"

# 最新バージョンを取得（LayerVersions はデフォルトで降順にソートされているため、最初の要素が最新）
VERSION=$(aws lambda list-layer-versions \
  --layer-name "$LAYER_NAME" \
  --query 'LayerVersions[0].Version' \
  --output text)

echo "Latest version for $LAYER_NAME is: $VERSION"

# AWS CLI でレイヤーのダウンロード URL を取得
DOWNLOAD_URL=$(aws lambda get-layer-version \
  --layer-name "$LAYER_NAME" \
  --version-number "$VERSION" \
  --query 'Content.Location' \
  --output text)

# 保存先ディレクトリ
TARGET_DIR="tests/unit/layer_code"
mkdir -p "$TARGET_DIR"

# ZIP ファイルのダウンロード
curl -o "$TARGET_DIR/layer.zip" "$DOWNLOAD_URL"

# ZIP ファイルの解凍（/python ディレクトリが展開される前提）
unzip -o "$TARGET_DIR/layer.zip" -d "$TARGET_DIR"
