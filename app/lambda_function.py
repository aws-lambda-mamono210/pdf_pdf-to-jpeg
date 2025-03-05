"""AWS Lambda 関数: S3 内の指定フォルダにある PDF ファイルをすべて処理し、各ページを JPEG に変換して、それぞれの JPEG ファイルを指定の S3 パスへアップロードする.

This module processes all PDF files in a specified S3 folder, converts each page to a JPEG image,
and uploads each JPEG file directly to S3.
"""

import os
import tempfile

import fitz  # PyMuPDF
from PIL import Image
from s3_utils import download_objects_from_s3, upload_file_to_s3


def lambda_handler(event, context):
    """Lambda function to convert PDF pages to JPEG and upload them to S3.

    Args:
        event (dict): Lambda event containing configuration parameters.
        context (object): Lambda runtime context.

    Returns:
        dict: Response containing status code and message.
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
            # PDF の内容を読み込み
            with open(file_path, "rb") as f:
                pdf_data = f.read()

            # バイト列から PDF ドキュメントをオープン
            pdf_doc = fitz.open(stream=pdf_data, filetype="pdf")

            # 高解像度設定
            dpi = 300.0
            scale = dpi / 72.0
            mat = fitz.Matrix(scale, scale)

            # PDF のファイル名（拡張子除去）
            base_filename = os.path.splitext(os.path.basename(file_path))[0]

            # 各ページごとに JPEG 画像に変換してアップロード
            for page_number, page in enumerate(pdf_doc, start=1):
                # ページを画像化
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

                # JPEG に変換してローカルファイルに保存
                jpeg_filename = f"{base_filename}_page{page_number}.jpg"
                jpeg_local_path = os.path.join(local_dir, jpeg_filename)
                img.save(jpeg_local_path, format="JPEG", quality=95)

                # S3 キーの作成（余計なスラッシュが入らないように）
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
