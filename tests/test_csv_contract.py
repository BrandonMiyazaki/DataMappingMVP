import unittest

from src.data_mapping_mvp.csv_contract import (
    CSV_COLUMNS,
    ValidationError,
    build_csv_content,
    map_measurement_to_csv_row,
    map_measurements_payload_to_rows,
    map_measurements_resilient,
)


def _valid_measurement(**overrides):
    measurement = {
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
    measurement.update(overrides)
    return measurement


class CsvContractTests(unittest.TestCase):
    def test_maps_measurement_to_standardized_row(self):
        row = map_measurement_to_csv_row(_valid_measurement(), index=1)

        self.assertEqual(row["Record_ID"], "REC-0001")
        self.assertEqual(row["Event_Timestamp"], "2026-07-14 06:02:11")
        self.assertEqual(row["Work_Order"], "NS-84721")
        self.assertEqual(row["Serial_Number"], "AX10001")
        self.assertEqual(row["Station_ID"], "STN-01")
        self.assertEqual(row["Test_Category"], "Torque")
        self.assertEqual(row["Measurement_Name"], "Joint J1 torque")
        self.assertEqual(row["Measurement_Value"], "18.42")
        self.assertEqual(row["Measurement_Unit"], "N\u00b7m")
        self.assertEqual(row["Lower_Spec_Limit"], "18")
        self.assertEqual(row["Upper_Spec_Limit"], "19")
        self.assertEqual(row["Target_Value"], "18.5")
        self.assertEqual(row["Result"], "PASS")
        self.assertEqual(row["Attempt_Number"], "1")

    def test_maps_source_record_text_to_column(self):
        row = map_measurement_to_csv_row(_valid_measurement(), index=1)
        self.assertEqual(
            row["Source_Record_Text"],
            "2026-07-14 06:02:11 WO=NS-84721 SN AX10001 joint:J1 torque=18.42Nm angle 44.8deg PASS",
        )

    def test_assigns_sequential_record_ids(self):
        rows = map_measurements_payload_to_rows(
            {"measurements": [_valid_measurement(), _valid_measurement(serialNumber="AX10002")]}
        )

        self.assertEqual([r["Record_ID"] for r in rows], ["REC-0001", "REC-0002"])

    def test_preserves_explicit_record_id(self):
        row = map_measurement_to_csv_row(_valid_measurement(recordId="REC-9999"), index=1)
        self.assertEqual(row["Record_ID"], "REC-9999")

    def test_allows_blank_measurement_value_for_status_only_record(self):
        row = map_measurement_to_csv_row(
            _valid_measurement(
                measurementValue=None,
                measurementUnit=None,
                lowerSpecLimit=None,
                upperSpecLimit=None,
                targetValue=None,
                result="REVIEW",
                errorCode="OCR_GLARE",
                measurementName="Barcode readability",
            ),
            index=20,
        )

        self.assertEqual(row["Record_ID"], "REC-0020")
        self.assertEqual(row["Measurement_Value"], "")
        self.assertEqual(row["Result"], "REVIEW")
        self.assertEqual(row["Error_Code"], "OCR_GLARE")

    def test_normalizes_result_casing(self):
        row = map_measurement_to_csv_row(_valid_measurement(result="pass"), index=1)
        self.assertEqual(row["Result"], "PASS")

    def test_rejects_invalid_result_value(self):
        with self.assertRaises(ValidationError):
            map_measurement_to_csv_row(_valid_measurement(result="OK"), index=1)

    def test_rejects_missing_required_field(self):
        measurement = _valid_measurement()
        del measurement["serialNumber"]
        with self.assertRaises(ValidationError):
            map_measurement_to_csv_row(measurement, index=1)

    def test_rejects_empty_measurements_payload(self):
        with self.assertRaises(ValidationError):
            map_measurements_payload_to_rows({"measurements": []})

    def test_rejects_non_numeric_measurement_value(self):
        with self.assertRaises(ValidationError):
            map_measurement_to_csv_row(_valid_measurement(measurementValue="eighteen"), index=1)

    def test_resilient_quarantines_invalid_and_keeps_valid(self):
        valid = _valid_measurement()
        invalid = {"testCategory": "Torque", "sourceRecordText": "orphan"}
        rows, quarantined = map_measurements_resilient([valid, invalid, _valid_measurement(serialNumber="AX10002")])

        self.assertEqual([r["Record_ID"] for r in rows], ["REC-0001", "REC-0002"])
        self.assertEqual(len(quarantined), 1)
        self.assertEqual(quarantined[0]["sourceIndex"], 2)
        self.assertIn("required", quarantined[0]["error"])

    def test_resilient_all_valid_has_no_quarantine(self):
        rows, quarantined = map_measurements_resilient([_valid_measurement(), _valid_measurement()])
        self.assertEqual(len(rows), 2)
        self.assertEqual(quarantined, [])

    def test_builds_csv_content_with_header_and_all_columns(self):
        rows = map_measurements_payload_to_rows({"measurements": [_valid_measurement()]})
        csv_content = build_csv_content(rows)

        self.assertIn(",".join(CSV_COLUMNS), csv_content)
        self.assertIn("REC-0001", csv_content)
        self.assertIn("AX10001", csv_content)

    def test_column_count_is_twenty_five(self):
        self.assertEqual(len(CSV_COLUMNS), 25)


if __name__ == "__main__":
    unittest.main()
