"""app.pdf_to_jpeg モジュール.

このモジュールは、指定されたPDFファイルの各ページをJPEG画像に変換するための関数を提供します。
変換されたJPEG画像は、指定されたローカルディレクトリに保存され、後続の処理（例: S3 へのアップロード）で利用できます。
"""

import os

import fitz  # PyMuPDF
from PIL import Image


def convert_pdf_to_jpeg(
    pdf_file_path, output_dir, dpi=300, quality=95, grayscale=False
):
    """指定されたPDFファイルの各ページをJPEGに変換し、ローカルディレクトリに保存します.

    Args:
        pdf_file_path (str): 変換対象のPDFファイルパス
        output_dir (str): 生成したJPEGファイルの保存先ディレクトリ
        dpi (int, optional): 画像解像度(DPI)。デフォルトは300
        quality (int, optional): JPEGの品質（0～100）。デフォルトは95
        grayscale (bool, optional): Trueの場合、画像をグレースケールに変換して保存。デフォルトはFalse

    Returns:
        list: 生成されたJPEGファイルのパスのリスト
    """
    jpeg_files = []
    try:
        # PDFデータを読み込む
        with open(pdf_file_path, "rb") as f:
            pdf_data = f.read()

        # PDFを開く
        pdf_doc = fitz.open(stream=pdf_data, filetype="pdf")

        # 解像度に合わせたスケール設定
        scale = dpi / 72.0
        mat = fitz.Matrix(scale, scale)

        # PDFのファイル名（拡張子除去）
        base_filename = os.path.splitext(os.path.basename(pdf_file_path))[0]

        # 各ページをJPEGに変換
        for page_number, page in enumerate(pdf_doc, start=1):
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

            # grayscaleがTrueの場合、画像をグレースケールに変換
            if grayscale:
                img = img.convert("L")

            jpeg_filename = f"{base_filename}_page{page_number}.jpg"
            jpeg_local_path = os.path.join(output_dir, jpeg_filename)
            img.save(jpeg_local_path, format="JPEG", quality=quality)
            jpeg_files.append(jpeg_local_path)

    except Exception as e:
        print(f"Error converting {pdf_file_path}: {e}")

    return jpeg_files
