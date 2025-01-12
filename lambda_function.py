import boto3
import fitz  # PyMuPDF
from PIL import Image
import io
import os
from zipfile import ZipFile, ZIP_DEFLATED

def lambda_handler(event, context):
    s3 = boto3.client('s3')

    source_bucket = "shitadan"
    pdf_prefix    = "api/receipts/r6/pdf/"   # PDFのあるフォルダ
    jpeg_prefix   = "api/receipts/r6/jpeg/"  # 出力先フォルダ

    # この Lambda は「フォルダ内のPDFを全部処理」する想定
    # list_objects_v2 でPDF一覧を取得
    response = s3.list_objects_v2(
        Bucket=source_bucket,
        Prefix=pdf_prefix
    )

    if 'Contents' not in response:
        return {
            "statusCode": 200,
            "body": f"No PDFs found under {pdf_prefix}"
        }

    # まとめてZIPに格納するためのバッファ（メモリ上）
    zip_buffer = io.BytesIO()

    # ZIPファイルを「書き込みモード(w)」で開き、順次ファイル追加
    with ZipFile(zip_buffer, 'w', compression=ZIP_DEFLATED) as zipf:

        for item in response['Contents']:
            key = item['Key']

            # PDF以外 or フォルダ自身などはスキップ
            if not key.endswith(".pdf"):
                continue

            try:
                # PDFデータを取得
                pdf_obj = s3.get_object(Bucket=source_bucket, Key=key)
                pdf_data = pdf_obj['Body'].read()

                # PDFをPyMuPDFで開く
                pdf_doc = fitz.open(stream=pdf_data, filetype='pdf')

                # 高解像度にしたい場合はMatrixで拡大率を上げる
                dpi   = 300.0
                scale = dpi / 72.0
                mat   = fitz.Matrix(scale, scale)

                # PDFファイル名 (拡張子除去)
                base_filename = os.path.splitext(os.path.basename(key))[0]

                for page_number, page in enumerate(pdf_doc):
                    # ページをpixmap化
                    pix = page.get_pixmap(matrix=mat, alpha=False)

                    # Pillowで画像化
                    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

                    # JPEGに変換 (quality=95 など)
                    jpeg_buffer = io.BytesIO()
                    img.save(jpeg_buffer, format="JPEG", quality=95)
                    jpeg_buffer.seek(0)

                    # ZIP内部のファイル名
                    # 「<PDF名>_page_X.jpg」という形式にして区別できるようにする
                    jpeg_filename_in_zip = f"{base_filename}_page_{page_number + 1}.jpg"

                    # ZIPに追加
                    zipf.writestr(jpeg_filename_in_zip, jpeg_buffer.getvalue())

            except Exception as e:
                print(f"Error processing {key}: {e}")

    # すべてのPDFをZIPに詰め終わったら、ZIPバッファのポインタを先頭へ
    zip_buffer.seek(0)

    # ZIPファイルとしてS3へアップロード
    # 好みで日時やユニークIDなどを付けたファイル名にしてもOK
    zip_key = f"{jpeg_prefix}all_pdfs_{int(context.aws_request_id[:8],16)}.zip"

    s3.put_object(
        Bucket=source_bucket,
        Key=zip_key,
        Body=zip_buffer,
        ContentType="application/zip"
    )

    return {
        "statusCode": 200,
        "body": f"All PDF pages have been zipped into {zip_key}"
    }

