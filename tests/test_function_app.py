import json
import unittest
from pathlib import Path

from function_app import (
    build_failed_record,
    build_quarantine_record,
    extract_canonical_payload_from_analyzer_result,
    process_analyzer_result,
    process_canonical_payload,
)


def _measurements_payload():
    return {
        "measurements": [
            {
                "eventTimestamp": "2026-07-14 06:02:11",
                "workOrder": "NS-84721",
                "serialNumber": "AX10001",
                "line": "Line 2",
                "shift": "Day",
                "stationId": "STN-01",
                "testCategory": "Torque",
                "measurementName": "Joint J1 torque",
                "measurementValue": 18.42,
                "measurementUnit": "N\u00b7m",
                "lowerSpecLimit": 18,
                "upperSpecLimit": 19,
                "targetValue": 18.5,
                "result": "PASS",
                "attemptNumber": 1,
                "sourceRecordText": "2026-07-14 06:02:11 WO=NS-84721 SN AX10001 joint:J1 torque=18.42Nm angle 44.8deg PASS",
            }
        ]
    }


class FunctionAppTests(unittest.TestCase):
    def test_process_canonical_payload_returns_multi_column_csv(self):
        output = process_canonical_payload(_measurements_payload())

        self.assertIn(
            "Record_ID,Event_Timestamp,Work_Order,Serial_Number,Line,Shift,Station_ID,Test_Category,Measurement_Name,Measurement_Value",
            output.csv,
        )
        self.assertIn("REC-0001", output.csv)
        self.assertIn("AX10001", output.csv)
        self.assertIn("Joint J1 torque", output.csv)
        self.assertEqual(output.quarantined, [])

    def test_process_canonical_payload_quarantines_invalid_records(self):
        payload = _measurements_payload()
        payload["measurements"].append({"testCategory": "Torque", "sourceRecordText": "orphan fragment"})

        output = process_canonical_payload(payload)

        self.assertIn("REC-0001", output.csv)
        self.assertEqual(len(output.quarantined), 1)
        self.assertEqual(output.quarantined[0]["sourceIndex"], 2)
        self.assertIn("required", output.quarantined[0]["error"])

    def test_build_failed_record_contains_error_details(self):
        failure = build_failed_record(
            source_file="sample.xlsx",
            error_message="serialNumber is required",
            payload={"measurements": []},
        )

        self.assertIn('"sourceFile": "sample.xlsx"', failure)
        self.assertIn('"status": "failed"', failure)
        self.assertIn('"error": "serialNumber is required"', failure)

    def test_build_quarantine_record_lists_failed_records(self):
        quarantine = build_quarantine_record(
            "sample.xlsx",
            [{"sourceIndex": 3, "error": "result is required", "measurement": {"serialNumber": "AX1"}}],
        )

        self.assertIn('"status": "partial"', quarantine)
        self.assertIn('"quarantinedCount": 1', quarantine)
        self.assertIn('"result is required"', quarantine)

    def test_extracts_measurements_from_fixture(self):
        fixture_path = Path(__file__).resolve().parent.parent / "fixtures" / "content_understanding_response.json"
        with fixture_path.open("r", encoding="utf-8") as handle:
            fixture = json.load(handle)

        payload = extract_canonical_payload_from_analyzer_result(fixture)

        self.assertEqual(len(payload["measurements"]), 3)
        first = payload["measurements"][0]
        self.assertEqual(first["serialNumber"], "AX10001")
        self.assertEqual(first["testCategory"], "Torque")
        self.assertEqual(first["measurementValue"], 18.42)
        self.assertEqual(payload["measurements"][2]["result"], "REVIEW")

    def test_process_analyzer_result_returns_row_per_measurement(self):
        fixture_path = Path(__file__).resolve().parent.parent / "fixtures" / "content_understanding_response.json"
        with fixture_path.open("r", encoding="utf-8") as handle:
            fixture = json.load(handle)

        output = process_analyzer_result(fixture)
        data_lines = [line for line in output.csv.strip().splitlines()[1:] if line]

        self.assertEqual(len(data_lines), 3)
        self.assertEqual(output.quarantined, [])
        self.assertIn("REC-0001", output.csv)
        self.assertIn("REC-0003", output.csv)
        self.assertIn("TORQUE_LOW", output.csv)
        self.assertIn("OCR_GLARE", output.csv)


if __name__ == "__main__":
    unittest.main()
