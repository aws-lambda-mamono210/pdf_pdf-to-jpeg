#!/bin/bash
set -e

bash scripts/download_layer.sh
bash scripts/get_layer_arn.sh

sam build --use-container

sam local invoke pdf-pdf-to-jpeg \
  --parameter-overrides AwsS3UtilsLayerArn=`cat scripts/layer_arn.txt` \
  --event events/test.json

sam local invoke pdf-pdf-to-jpeg \
  --parameter-overrides AwsS3UtilsLayerArn=`cat scripts/layer_arn.txt` \
  --event events/test-regex-pattern.json
