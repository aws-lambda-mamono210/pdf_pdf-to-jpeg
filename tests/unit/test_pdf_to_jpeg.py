"""test_pdf_to_jpeg モジュール.

このモジュールは、app.pdf_to_jpeg モジュールの convert_pdf_to_jpeg 関数のユニットテストを実装します。
テストでは、一時的なPDFファイルを生成してJPEG変換が正しく行われるか、およびエラーケースの挙動を確認します。
"""

import os
import tempfile
import unittest

import fitz  # PyMuPDF
from PIL import Image

from app.pdf_to_jpeg import convert_pdf_to_jpeg


class TestConvertPdfToJpeg(unittest.TestCase):
    """Unit tests for convert_pdf_to_jpeg function."""

    def setUp(self):
        """Set up temporary directory and sample PDF."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_pdf_path = os.path.join(self.temp_dir.name, "test.pdf")
        # Create a simple 1-page PDF using PyMuPDF.
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Test PDF for conversion", fontsize=12)
        doc.save(self.test_pdf_path)
        doc.close()

    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()

    def test_convert_pdf_to_jpeg_success(self):
        """Test successful PDF to JPEG conversion."""
        output_dir = self.temp_dir.name
        jpeg_files = convert_pdf_to_jpeg(self.test_pdf_path, output_dir)
        self.assertEqual(len(jpeg_files), 1)
        jpeg_file = jpeg_files[0]
        self.assertTrue(os.path.exists(jpeg_file))
        with Image.open(jpeg_file) as img:
            self.assertEqual(img.format, "JPEG")

    def test_convert_pdf_to_jpeg_grayscale(self):
        """Test successful PDF to JPEG conversion with grayscale option enabled."""
        output_dir = self.temp_dir.name
        jpeg_files = convert_pdf_to_jpeg(self.test_pdf_path, output_dir, grayscale=True)
        self.assertEqual(len(jpeg_files), 1)
        jpeg_file = jpeg_files[0]
        self.assertTrue(os.path.exists(jpeg_file))
        with Image.open(jpeg_file) as img:
            self.assertEqual(img.format, "JPEG")
            # グレースケール変換の場合はモードが "L" であることを確認
            self.assertEqual(img.mode, "L")

    def test_convert_pdf_to_jpeg_invalid_file(self):
        """Test conversion with invalid file returns empty list."""
        invalid_pdf_path = os.path.join(self.temp_dir.name, "nonexistent.pdf")
        jpeg_files = convert_pdf_to_jpeg(invalid_pdf_path, self.temp_dir.name)
        self.assertEqual(jpeg_files, [])


if __name__ == "__main__":
    unittest.main()
