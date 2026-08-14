import json
import unittest
from pathlib import Path

from function_app import (
    build_failed_record,
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
        csv_content = process_canonical_payload(_measurements_payload())

        self.assertIn(
            "Record_ID,Event_Timestamp,Work_Order,Serial_Number,Line,Shift,Station_ID,Test_Category,Measurement_Name,Measurement_Value",
            csv_content,
        )
        self.assertIn("REC-0001", csv_content)
        self.assertIn("AX10001", csv_content)
        self.assertIn("Joint J1 torque", csv_content)

    def test_build_failed_record_contains_error_details(self):
        failure = build_failed_record(
            source_file="sample.xlsx",
            error_message="serialNumber is required",
            payload={"measurements": []},
        )

        self.assertIn('"sourceFile": "sample.xlsx"', failure)
        self.assertIn('"status": "failed"', failure)
        self.assertIn('"error": "serialNumber is required"', failure)

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

        csv_output = process_analyzer_result(fixture)
        data_lines = [line for line in csv_output.strip().splitlines()[1:] if line]

        self.assertEqual(len(data_lines), 3)
        self.assertIn("REC-0001", csv_output)
        self.assertIn("REC-0003", csv_output)
        self.assertIn("TORQUE_LOW", csv_output)
        self.assertIn("OCR_GLARE", csv_output)


if __name__ == "__main__":
    unittest.main()
