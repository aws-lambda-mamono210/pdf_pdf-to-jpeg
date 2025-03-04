"""AWS Lambda 関数: S3 内の指定フォルダにある PDF ファイルをすべて処理し、各ページを JPEG に変換した後、ZIP ファイルとしてまとめて S3 にアップロードする.

This module processes all PDF files in a specified S3 folder, converts each page to a JPEG image,
and stores the results in a ZIP archive, which is then uploaded back to S3.
"""

import io
import os
from zipfile import ZIP_DEFLATED, ZipFile

import boto3
import fitz  # PyMuPDF
from PIL import Image


def lambda_handler(event, context):
    """Process PDFs from an S3 bucket, convert each page to a JPEG image, and store them in a ZIP file.

    Args:
        event (dict): The event data passed to the Lambda function (unused in this case).
        context (LambdaContext): Runtime information provided by AWS Lambda.

    Returns:
        dict: The result containing the status code and output message.
    """
    s3 = boto3.client("s3")

    source_bucket = "shitadan"
    pdf_prefix = "api/receipts/r6/pdf/"  # PDF のあるフォルダ
    jpeg_prefix = "api/receipts/r6/jpeg/"  # 出力先フォルダ

    # 指定フォルダ内の PDF 一覧を取得
    response = s3.list_objects_v2(Bucket=source_bucket, Prefix=pdf_prefix)

    if "Contents" not in response:
        return {"statusCode": 200, "body": f"No PDFs found under {pdf_prefix}"}

    # ZIP ファイル格納用のバッファを作成
    zip_buffer = io.BytesIO()

    # ZIP ファイルを作成し、処理した JPEG を格納
    with ZipFile(zip_buffer, "w", compression=ZIP_DEFLATED) as zipf:
        for item in response["Contents"]:
            key = item["Key"]

            # PDF ファイルのみを処理
            if not key.endswith(".pdf"):
                continue

            try:
                # PDF データを取得
                pdf_obj = s3.get_object(Bucket=source_bucket, Key=key)
                pdf_data = pdf_obj["Body"].read()

                # PDF を開く
                pdf_doc = fitz.open(stream=pdf_data, filetype="pdf")

                # 高解像度設定
                dpi = 300.0
                scale = dpi / 72.0
                mat = fitz.Matrix(scale, scale)

                # PDF のファイル名（拡張子除去）
                base_filename = os.path.splitext(os.path.basename(key))[0]

                for page_number, page in enumerate(pdf_doc):
                    # ページを画像化
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

                    # JPEG に変換
                    jpeg_buffer = io.BytesIO()
                    img.save(jpeg_buffer, format="JPEG", quality=95)
                    jpeg_buffer.seek(0)

                    # ZIP 内のファイル名を作成
                    jpeg_filename_in_zip = f"{base_filename}_page_{page_number + 1}.jpg"
                    zipf.writestr(jpeg_filename_in_zip, jpeg_buffer.getvalue())

            except Exception as e:
                print(f"Error processing {key}: {e}")

    # ZIP バッファのポインタを先頭に戻す
    zip_buffer.seek(0)

    # ZIP ファイルを S3 へアップロード
    zip_key = f"{jpeg_prefix}all_pdfs_{int(context.aws_request_id[:8], 16)}.zip"
    s3.put_object(
        Bucket=source_bucket,
        Key=zip_key,
        Body=zip_buffer,
        ContentType="application/zip",
    )

    return {"statusCode": 200, "body": f"All PDF pages have been zipped into {zip_key}"}
