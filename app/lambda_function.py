"""app.lambda_function モジュール.

このモジュールは、S3 内の指定フォルダにある PDF ファイルをダウンロードし、
各ページを JPEG に変換してから S3 にアップロードする AWS Lambda 関数を実装しています。

主な処理の流れ:
1. 指定の S3 バケットから PDF ファイルをダウンロード
2. PDF の各ページを JPEG に変換（convert_pdf_to_jpeg 関数を利用）
3. 変換した JPEG ファイルを S3 にアップロード
"""

import os
import tempfile

from s3_utils import download_objects_from_s3, upload_file_to_s3

from app.pdf_to_jpeg import convert_pdf_to_jpeg


def lambda_handler(event, context):
    """AWS Lambda ハンドラー.

    この関数は、S3 から PDF ファイルをダウンロードし、各ページを JPEG に変換してから、
    指定された S3 パスにアップロードします。

    Args:
        event (dict): Lambda イベント情報。以下のパラメータを含む:
            - pdf_prefix (str): PDF ファイルが格納されている S3 のプレフィックス。例: "api/receipts/r6/pdf/"
            - local_dir (str, optional): 一時的にファイルを保存するローカルディレクトリのパス。
            - upload_prefix (str): JPEG ファイルのアップロード先 S3 のプレフィックス。例: "api/receipts/r6/jpeg"
            - content_type (str): アップロードする JPEG ファイルの MIME タイプ。例: "image/jpeg"
        context (object): AWS Lambda のランタイムコンテキスト。

    Returns:
        dict: ステータスコードと処理結果のメッセージを含むレスポンスオブジェクト。
    """
    # S3 バケットと各種パラメータの設定
    source_bucket = "shitadan"
    pdf_prefix = event.get("pdf_prefix", "api/receipts/r6/pdf/")
    local_dir = event.get("local_dir", tempfile.mkdtemp(prefix="pdf_"))
    print(f"Using local directory: {local_dir}")

    # アップロード先の設定
    upload_prefix = event.get("upload_prefix", "api/receipts/r6/jpeg")
    content_type = event.get("content_type", "image/jpeg")

    # 1. S3 から PDF をダウンロード
    downloaded_files = download_objects_from_s3(source_bucket, pdf_prefix, local_dir)
    if not downloaded_files:
        return {"statusCode": 200, "body": f"No PDFs found under {pdf_prefix}"}

    # 2. 各 PDF を処理し、各ページを JPEG に変換して S3 にアップロード
    for file_path in downloaded_files:
        try:
            # PDF を JPEG に変換する（変換後の JPEG ファイルのパスリストを受け取る）
            jpeg_files = convert_pdf_to_jpeg(file_path, local_dir)

            # 変換した各 JPEG ファイルを S3 にアップロード
            for jpeg_local_path in jpeg_files:
                jpeg_filename = os.path.basename(jpeg_local_path)
                upload_key = f"{upload_prefix.rstrip('/')}/{jpeg_filename}"
                upload_file_to_s3(
                    jpeg_local_path, source_bucket, upload_key, content_type
                )
                print(f"Uploaded {jpeg_filename} to s3://{source_bucket}/{upload_key}")

        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    return {
        "statusCode": 200,
        "body": f"All PDF pages have been converted to JPEG and uploaded to {upload_prefix}",
    }
