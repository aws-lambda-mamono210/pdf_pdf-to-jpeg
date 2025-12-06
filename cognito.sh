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

# aws apigateway test-invoke-method の修正
aws apigateway test-invoke-method \
    --rest-api-id ${REST_API_ID} \
    --resource-id ${RESOURCE_ID} \
    --http-method POST \
    --headers "{\"Authorization\":\"Bearer ${ACCESS_TOKEN}\"}" \
    --body '{
        "source_bucket":"shitadan",
        "pdf_prefix":"r6/cash-journal/src/invoices/",
	"regex_pattern":"7([0-9][0-9])請.pdf$",
        "upload_prefix":"r6/cash-journal/img/invoices/",
        "content_type":"image/jpeg",
        "grayscale":true
    }'

# curl コマンドの修正
curl -X POST \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{
        "source_bucket": "shitadan",
        "pdf_prefix": "r6/cash-journal/src/invoices/",
        "upload_prefix": "r6/cash-journal/img/invoices/",
	"regex_pattern":"7([0-9][0-9])請.pdf$",
        "content_type": "image/jpeg",
        "grayscale": true
    }' \
    ${END_POINT}
