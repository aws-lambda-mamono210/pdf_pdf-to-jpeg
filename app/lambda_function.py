"""app.lambda_function モジュール.

このモジュールは、S3 内の指定フォルダにある PDF ファイルをダウンロードし、
各ページを JPEG に変換してから S3 にアップロードする AWS Lambda 関数を実装しています。

主な処理の流れ:
1. 指定の S3 バケットから PDF ファイルをダウンロード
2. PDF の各ページを JPEG に変換（convert_pdf_to_jpeg 関数を利用）
3. 変換した JPEG ファイルを S3 にアップロード
"""

import json
import os
import tempfile

import jwt
import requests
from s3_utils import (
    download_objects_from_s3,
    download_objects_from_s3_with_regex,
    upload_file_to_s3,
)

from app.pdf_to_jpeg import convert_pdf_to_jpeg

COGNITO_USER_POOL_ID = "ap-northeast-1_ysVBcgp4S"
COGNITO_APP_CLIENT_ID = "556mf49tmcb8hri8qkjc9hfg3r"
COGNITO_REGION = "ap-northeast-1"


def get_cognito_public_keys():
    """Cognito ユーザープールの公開鍵 (JWKS) を取得する.

    Cognito では JWT トークンの署名を RSA 方式で行っているため、
    署名の検証には公開鍵が必要となる。この関数は、Cognito の
    `.well-known/jwks.json` エンドポイントから公開鍵を取得する。

    Returns:
        list: 公開鍵 (JWKS) のリスト。各要素は JSON 形式の RSA 鍵情報を持つ辞書。

    Raises:
        requests.RequestException: Cognito からの応答が不正、または通信エラーが発生した場合。
    """
    url = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()["keys"]
    except requests.Timeout:
        raise Exception("Timeout error: Unable to fetch Cognito public keys")
    except requests.RequestException as e:
        raise Exception(f"Request error: {str(e)}")


def verify_token(token):
    """Cognito の JWT アクセストークンを検証する.

    API Gateway 経由で渡された JWT トークンが正しい形式であり、
    Cognito によって発行されたものであるかを検証する。

    Args:
        token (str): 検証対象の JWT トークン。

    Returns:
        dict: トークンが有効な場合、デコードされた JWT クレーム情報を含む辞書。
              無効な場合は {"error": "エラーメッセージ"} の形式で返す。

    Raises:
        jwt.ExpiredSignatureError: トークンの有効期限が切れている場合。
        jwt.InvalidTokenError: トークンが無効な場合。
    """
    try:
        # Cognito の公開鍵を取得
        public_keys = get_cognito_public_keys()
        headers = jwt.get_unverified_header(token)
        key = next((key for key in public_keys if key["kid"] == headers["kid"]), None)

        if key is None:
            raise Exception("Invalid token: key not found")

        # 公開鍵で JWT を検証
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
        decoded_token = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=COGNITO_APP_CLIENT_ID,  # アプリクライアントIDを設定
        )

        return decoded_token

    except jwt.ExpiredSignatureError:
        return {"error": "Token has expired"}
    except jwt.InvalidTokenError:
        return {"error": "Invalid token"}


def lambda_handler(event, context):
    r"""AWS Lambda ハンドラー (Cognito 認証付き).

    この関数は、Cognito 認証を実施し、S3 から PDF をダウンロードして JPEG に変換し、
    変換後の JPEG ファイルを S3 にアップロードする。

    **処理の流れ:**
    1. **認証処理**: API Gateway のリクエストヘッダーに含まれる JWT トークンを Cognito で検証
    2. **リクエストボディの解析**: JSON を解析し、必要なパラメータを取得
    3. **S3 から PDF ファイルをダウンロード**
    4. **PDF の各ページを JPEG に変換**
    5. **変換した JPEG ファイルを S3 にアップロード**
    6. **処理結果 (アップロードされたファイルリスト) をレスポンスとして返す**

    **リクエスト形式（API Gateway 経由の場合）**
    ```json
    {
        "source_bucket": "example-bucket",
        "pdf_prefix": "api/receipts/r6/pdf/",
        "upload_prefix": "api/receipts/r6/jpeg/",
        "content_type": "image/jpeg",
        "grayscale": true
    }
    ```

    **認証**
    - `Authorization: Bearer <JWT_TOKEN>` ヘッダーを API リクエストに含める必要がある。
    - JWT トークンが Cognito によって発行されているかを検証し、不正なトークンの場合 `401 Unauthorized` を返す。

    **リクエスト形式（AWS Lambda 直接実行の場合）**
    - `event` は JSON データ（辞書型）として渡される。
    - Cognito 認証はスキップされる。

    Args:
        event (dict): Lambda イベント情報。以下のパラメータを含む:
            - headers (dict): API Gateway のリクエストヘッダー
            - Authorization (str, 必須): Cognito JWT トークン (形式: `"Bearer <TOKEN>"`)
            - source_bucket (str): PDF ファイルが格納されている S3 バケット名。例: `"example-bucket"`
            - pdf_prefix (str): PDF ファイルが格納されている S3 のプレフィックス。例: `"api/receipts/r6/pdf/"`
            - regex_pattern (str, optional): ダウンロードするファイル名の正規表現パターン。例: `r".*\.pdf"`
            - upload_prefix (str): JPEG ファイルのアップロード先 S3 のプレフィックス。例: `"api/receipts/r6/jpeg/"`
            - content_type (str, optional): アップロードする JPEG ファイルの MIME タイプ。例: `"image/jpeg"`
            - grayscale (bool, optional): グレースケール変換を行う場合は `True` を指定（デフォルトは `False`）。

        context (object): AWS Lambda のランタイムコンテキスト。

    Returns:
        dict: ステータスコードと処理結果のメッセージを含むレスポンスオブジェクト。

        **成功時のレスポンス**
        ```json
        {
            "statusCode": 200,
            "body": {
                "message": "Processing complete",
                "uploaded_files": [
                    "s3://example-bucket/api/receipts/r6/jpeg/page_1.jpg",
                    "s3://example-bucket/api/receipts/r6/jpeg/page_2.jpg"
                ]
            }
        }
        ```

        **エラー時のレスポンス**
        - 認証エラー (`Authorization` ヘッダーがない or トークンが無効)
        ```json
        {
            "statusCode": 401,
            "body": { "error": "Missing token" }
        }
        ```
        ```json
        {
            "statusCode": 401,
            "body": { "error": "Invalid token" }
        }
        ```
        - 必須パラメータが不足している場合
        ```json
        {
            "statusCode": 400,
            "body": { "error": "Missing required parameters" }
        }
        ```
        - JSON の解析エラー
        ```json
        {
            "statusCode": 400,
            "body": { "error": "Invalid JSON", "details": "Expecting property name enclosed in double quotes" }
        }
        ```
    """
    try:
        # 1. 認証チェック
        headers = event.get("headers", {})
        token = headers.get("Authorization", "").replace("Bearer ", "")

        if not token:
            return {"statusCode": 401, "body": json.dumps({"error": "Missing token"})}

        decoded_token = verify_token(token)
        if "error" in decoded_token:
            return {"statusCode": 401, "body": json.dumps(decoded_token)}

        # 2. API Gateway 経由の場合: body が JSON 文字列になっている
        if "body" in event and isinstance(event["body"], str):
            body = json.loads(event["body"])
        else:
            body = event

        print("Parsed body:", body)

        # 3. 必須パラメータの取得
        source_bucket = body.get("source_bucket", "")
        pdf_prefix = body.get("pdf_prefix", "")
        upload_prefix = body.get("upload_prefix", "")
        content_type = body.get("content_type", "image/jpeg")
        grayscale = body.get("grayscale", False)
        regex_pattern = body.get("regex_pattern", "")

        if not source_bucket or not pdf_prefix or not upload_prefix:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing required parameters"}),
            }

        local_dir = tempfile.mkdtemp(prefix="pdf_")
        print(f"Using local directory: {local_dir}")

        # 4. S3 から PDF をダウンロード
        if not regex_pattern:
            downloaded_files = download_objects_from_s3(
                source_bucket, pdf_prefix, local_dir
            )
        else:
            downloaded_files = download_objects_from_s3_with_regex(
                source_bucket, pdf_prefix, regex_pattern, local_dir
            )

        if not downloaded_files:
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": f"No PDFs found under s3://{source_bucket}/{pdf_prefix}"
                    }
                ),
            }

        # 5. PDF → JPEG 変換 & アップロード
        uploaded_files = []
        for file_path in downloaded_files:
            try:
                jpeg_files = convert_pdf_to_jpeg(
                    file_path, local_dir, grayscale=grayscale
                )

                for jpeg_local_path in jpeg_files:
                    jpeg_filename = os.path.basename(jpeg_local_path)
                    upload_key = f"{upload_prefix.rstrip('/')}/{jpeg_filename}"
                    upload_file_to_s3(
                        jpeg_local_path, source_bucket, upload_key, content_type
                    )
                    uploaded_files.append(f"s3://{source_bucket}/{upload_key}")

            except Exception as e:
                print(f"Error processing {file_path}: {e}")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {"message": "Processing complete", "uploaded_files": uploaded_files}
            ),
        }

    except json.JSONDecodeError as e:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid JSON", "details": str(e)}),
        }
