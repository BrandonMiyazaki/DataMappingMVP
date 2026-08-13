import unittest

from function_app import build_failed_record, process_canonical_payload


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


if __name__ == "__main__":
    unittest.main()
