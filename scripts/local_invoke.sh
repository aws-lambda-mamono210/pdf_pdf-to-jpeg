#!/bin/bash
set -e

bash scripts/download_layer.sh
bash scripts/get_layer_arn.sh

sam build --use-container


#!/bin/bash
set -x # デバッグモードを有効化

COGNITO_USER_POOL_ID="ap-northeast-1_ysVBcgp4S"
APP_CLIENT_ID="556mf49tmcb8hri8qkjc9hfg3r"
USERNAME="matsumura_t@yahoo.co.jp"
PASSWORD="NewSecurePass#5678"
REST_API_ID="l2f53fv4ei"
RESOURCE_ID="shenvp"
END_POINT="https://l2f53fv4ei.execute-api.ap-northeast-1.amazonaws.com/prod/convert"

# JSONデータを適切にエスケープする
ACCESS_TOKEN=$(curl -s -X POST \
    -H "Content-Type: application/x-amz-json-1.1" \
    -H "X-Amz-Target: AWSCognitoIdentityProviderService.InitiateAuth" \
    --data @- https://cognito-idp.ap-northeast-1.amazonaws.com/${COGNITO_USER_POOL_ID} <<EOF | jq -r '.AuthenticationResult.IdToken // .message'
{
    "AuthFlow": "USER_PASSWORD_AUTH",
    "ClientId": "$APP_CLIENT_ID",
    "AuthParameters": {
        "USERNAME": "$USERNAME",
        "PASSWORD": "$PASSWORD"
    }
}
EOF
)

# アクセストークンが取得できなかった場合はエラーメッセージを表示
if [[ "$ACCESS_TOKEN" == "null" || -z "$ACCESS_TOKEN" ]]; then
    echo "❌ Access token retrieval failed. Check your credentials and Cognito settings."
    exit 1
fi

echo "✅ Access Token: $ACCESS_TOKEN"

# JSONファイルの書き換え処理 (jqを使用)
TARGET_FILE="events/test.json"
TMP_FILE=$(mktemp)

# jqで headers.Authorization を更新
# --arg を使うことでシェル変数を安全にjq内に渡せます
jq --arg token "$ACCESS_TOKEN" \
   '.headers.Authorization = "Bearer " + $token' \
   "$TARGET_FILE" > "$TMP_FILE" && mv "$TMP_FILE" "$TARGET_FILE"

echo "✅ Updated $TARGET_FILE with new token."

# JSONファイルの書き換え処理 (jqを使用)
TARGET_FILE="events/test-regex-pattern.json"
TMP_FILE=$(mktemp)

# jqで headers.Authorization を更新
# --arg を使うことでシェル変数を安全にjq内に渡せます
jq --arg token "$ACCESS_TOKEN" \
   '.headers.Authorization = "Bearer " + $token' \
   "$TARGET_FILE" > "$TMP_FILE" && mv "$TMP_FILE" "$TARGET_FILE"

echo "✅ Updated $TARGET_FILE with new token."

# 確認のため表示
cat "$TARGET_FILE" | grep "Authorization"

sam local invoke pdf-pdf-to-jpeg \
  --parameter-overrides AwsS3UtilsLayerArn=`cat scripts/layer_arn.txt` \
  --event events/test.json

sam local invoke pdf-pdf-to-jpeg \
  --parameter-overrides AwsS3UtilsLayerArn=`cat scripts/layer_arn.txt` \
  --event events/test-regex-pattern.json
