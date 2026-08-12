import unittest

from src.data_mapping_mvp.csv_contract import (
    ValidationError,
    build_csv_content,
    map_canonical_payload_to_csv,
)


class CsvContractTests(unittest.TestCase):
    def test_maps_canonical_payload_to_standardized_csv_row(self):
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

        row = map_canonical_payload_to_csv(payload, source_file="sample.xlsx")

        self.assertEqual(row["SourceFile"], "sample.xlsx")
        self.assertEqual(row["CustomerName"], "Contoso")
        self.assertEqual(row["ReportingPeriod"], "2026-07")
        self.assertEqual(row["LineItemName"], "Product A")
        self.assertEqual(row["Quantity"], "10")
        self.assertEqual(row["UnitPrice"], "15.50")
        self.assertEqual(row["TotalAmount"], "155.00")
        self.assertEqual(row["Currency"], "USD")
        self.assertEqual(row["ConfidenceScore"], "0.91")

    def test_rejects_missing_required_fields(self):
        payload = {
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

        with self.assertRaises(ValidationError):
            map_canonical_payload_to_csv(payload, source_file="sample.xlsx")

    def test_rejects_low_confidence_scores(self):
        payload = {
            "customerName": "Contoso",
            "reportingPeriod": "2026-07",
            "currency": "USD",
            "confidenceScore": 0.5,
            "lineItems": [
                {
                    "name": "Product A",
                    "quantity": 10,
                    "unitPrice": 15.5,
                    "totalAmount": 155.0,
                }
            ],
        }

        with self.assertRaises(ValidationError):
            map_canonical_payload_to_csv(payload, source_file="sample.xlsx")

    def test_builds_csv_content_with_header_row(self):
        row = {
            "SourceFile": "sample.xlsx",
            "CustomerName": "Contoso",
            "ReportingPeriod": "2026-07",
            "LineItemName": "Product A",
            "Quantity": "10",
            "UnitPrice": "15.50",
            "TotalAmount": "155.00",
            "Currency": "USD",
            "ConfidenceScore": "0.91",
        }

        csv_content = build_csv_content([row])

        self.assertIn("SourceFile,CustomerName,ReportingPeriod,LineItemName,Quantity,UnitPrice,TotalAmount,Currency,ConfidenceScore", csv_content)
        self.assertIn("sample.xlsx,Contoso,2026-07,Product A,10,15.50,155.00,USD,0.91", csv_content)


if __name__ == "__main__":
    unittest.main()
