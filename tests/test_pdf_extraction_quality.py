import unittest

from scoring_app.pdf_extract import PdfExtractionError, extract_text_from_pdf_bytes

from test.fixture_builder import build_sample_document_text, build_text_pdf_bytes


class PdfExtractionQualityTestCase(unittest.TestCase):
    def test_valid_text_pdf_can_be_extracted(self):
        pdf_bytes = build_text_pdf_bytes(build_sample_document_text())
        extracted = extract_text_from_pdf_bytes(pdf_bytes)

        self.assertIn("温故知新个人汇报样例材料", extracted)
        self.assertIn("行动结果包括流程时长下降18%", extracted)

    def test_garbled_pdf_is_rejected(self):
        garbled_text = "锟Z 鍙 璇 鏂 鐨 褰 闂 鍙 璇 鐨 鍚 鍙 璇 鐨" * 8
        pdf_bytes = build_text_pdf_bytes(garbled_text)

        with self.assertRaises(PdfExtractionError):
            extract_text_from_pdf_bytes(pdf_bytes)


if __name__ == "__main__":
    unittest.main()
