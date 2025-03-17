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

from s3_utils import (
    download_objects_from_s3,
    download_objects_from_s3_with_regex,
    upload_file_to_s3,
)

from app.pdf_to_jpeg import convert_pdf_to_jpeg


def lambda_handler(event, context):
    r"""AWS Lambda ハンドラー.

    この関数は、S3 から PDF ファイルをダウンロードし、各ページを JPEG に変換してから、
    指定された S3 パスにアップロードします。

    **処理の流れ:**
    1. API Gateway または AWS Lambda のイベントを受け取り、JSON を解析
    2. 指定の S3 バケットから PDF をダウンロード
    3. PDF の各ページを JPEG に変換（`convert_pdf_to_jpeg` を使用）
    4. 変換した JPEG ファイルを S3 にアップロード
    5. 変換・アップロードしたファイルのリストをレスポンスとして返す

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

    **リクエスト形式（AWS Lambda 直接実行の場合）**
    - `event` は JSON データ（辞書型）として渡される。

    Args:
        event (dict): Lambda イベント情報。以下のパラメータを含む:
            - source_bucket (str): PDF ファイルが格納されている S3 バケット名。例: `"example-bucket"`
            - pdf_prefix (str): PDF ファイルが格納されている S3 のプレフィックス。例: `"api/receipts/r6/pdf/"`
            - upload_prefix (str): JPEG ファイルのアップロード先 S3 のプレフィックス。例: `"api/receipts/r6/jpeg/"`
            - content_type (str, optional): アップロードする JPEG ファイルの MIME タイプ。例: `"image/jpeg"`
            - grayscale (bool, optional): グレースケール変換を行う場合は `True` を指定（デフォルトは `False`）。
            - regex_pattern (str, optional): ダウンロードするファイル名の正規表現パターン。例: `r".*\.pdf"`

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
        ```json
        {
            "statusCode": 400,
            "body": { "error": "Missing required parameters" }
        }
        ```
    """
    try:
        # API Gateway 経由の場合: body が JSON 文字列になっている
        if "body" in event and isinstance(event["body"], str):
            body = json.loads(event["body"])
        else:
            # sam local invoke や直接実行の場合
            body = event

        print("Parsed body:", body)

        # 必須パラメータの取得
        source_bucket = body.get("source_bucket", "")
        pdf_prefix = body.get("pdf_prefix", "")
        upload_prefix = body.get("upload_prefix", "")
        content_type = body.get("content_type", "image/jpeg")
        grayscale = body.get("grayscale", False)
        regex_pattern = body.get("regex_pattern", "")

        # バリデーション（必須パラメータが足りない場合エラー）
        if not source_bucket or not pdf_prefix or not upload_prefix:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing required parameters"}),
            }

        local_dir = tempfile.mkdtemp(prefix="pdf_")
        print(f"Using local directory: {local_dir}")
        print(f"Grayscale conversion is set to: {grayscale}")

        # 1. S3 から PDF をダウンロード
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

        # 2. 各 PDF を処理し、各ページを JPEG に変換して S3 にアップロード
        uploaded_files = []
        for file_path in downloaded_files:
            try:
                # PDF を JPEG に変換する（変換後の JPEG ファイルのパスリストを受け取る）
                jpeg_files = convert_pdf_to_jpeg(
                    file_path, local_dir, grayscale=grayscale
                )

                # 変換した各 JPEG ファイルを S3 にアップロード
                for jpeg_local_path in jpeg_files:
                    jpeg_filename = os.path.basename(jpeg_local_path)
                    upload_key = f"{upload_prefix.rstrip('/')}/{jpeg_filename}"
                    upload_file_to_s3(
                        jpeg_local_path, source_bucket, upload_key, content_type
                    )
                    uploaded_files.append(f"s3://{source_bucket}/{upload_key}")
                    print(f"Uploaded {jpeg_filename} to {uploaded_files[-1]}")

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
