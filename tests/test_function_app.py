import json
import unittest
from pathlib import Path

from function_app import (
    build_failed_record,
    extract_canonical_payload_from_analyzer_result,
    process_analyzer_result,
    process_canonical_payload,
)


class FunctionAppTests(unittest.TestCase):
    def test_process_canonical_payload_returns_csv_output(self):
        payload = {
            "customerName": "Contoso",
            "reportingPeriod": "2026-07",
            "currency": "USD",
            "confidenceScore": 0.91,
            "lineItems": [
                {
                    "name": "Product A",
                    "quantity": 10,
                    "unitPrice": 15.5,
                    "totalAmount": 155.0,
                }
            ],
        }

        csv_content = process_canonical_payload(payload, source_file="sample.xlsx")

        self.assertIn("SourceFile,CustomerName,ReportingPeriod,LineItemName,Quantity,UnitPrice,TotalAmount,Currency,ConfidenceScore", csv_content)
        self.assertIn("sample.xlsx,Contoso,2026-07,Product A,10,15.50,155.00,USD,0.91", csv_content)

    def test_build_failed_record_contains_error_details(self):
        failure = build_failed_record(
            source_file="sample.xlsx",
            error_message="confidenceScore below threshold",
            payload={"confidenceScore": 0.5},
        )

        self.assertIn('"sourceFile": "sample.xlsx"', failure)
        self.assertIn('"status": "failed"', failure)
        self.assertIn('"error": "confidenceScore below threshold"', failure)

    def test_extracts_canonical_payload_from_fixture(self):
        fixture_path = Path(__file__).resolve().parent.parent / "fixtures" / "content_understanding_response.json"
        with fixture_path.open("r", encoding="utf-8") as handle:
            fixture = json.load(handle)

        payload = extract_canonical_payload_from_analyzer_result(fixture)

        self.assertEqual(payload["customerName"], "Contoso")
        self.assertEqual(payload["reportingPeriod"], "2026-07")
        self.assertEqual(payload["currency"], "USD")
        self.assertEqual(payload["confidenceScore"], 0.91)
        self.assertEqual(payload["lineItems"][0]["name"], "Product A")
        self.assertEqual(payload["lineItems"][0]["quantity"], 10)

    def test_process_analyzer_result_returns_csv_for_valid_fixture(self):
        fixture_path = Path(__file__).resolve().parent.parent / "fixtures" / "content_understanding_response.json"
        with fixture_path.open("r", encoding="utf-8") as handle:
            fixture = json.load(handle)

        csv_output = process_analyzer_result(fixture, source_file="sample.xlsx")

        self.assertIn("sample.xlsx,Contoso,2026-07,Product A,10,15.50,155.00,USD,0.91", csv_output)
        self.assertIn("SourceFile,CustomerName,ReportingPeriod", csv_output)


if __name__ == "__main__":
    unittest.main()
