#!/bin/bash
set -e

LAYER_NAME="aws-s3-utils-layer"
REGION="ap-northeast-1"

LAYER_ARN=$(aws lambda list-layer-versions \
  --layer-name "${LAYER_NAME}" \
  --region "${REGION}" \
  --query 'LayerVersions[0].LayerVersionArn' \
   --output text)

echo "Latest Layer ARN: ${LAYER_ARN}"
echo ${LAYER_ARN} > scripts/layer_arn.txt
