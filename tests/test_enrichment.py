import unittest

from src.data_mapping_mvp.enrichment import (
    enrich_measurements,
    lookup_spec,
    normalize_result,
    normalize_station_id,
)


class NormalizeResultTests(unittest.TestCase):
    def test_maps_synonyms_to_controlled_values(self):
        self.assertEqual(normalize_result("OK"), "PASS")
        self.assertEqual(normalize_result("GOOD"), "PASS")
        self.assertEqual(normalize_result("Y"), "PASS")
        self.assertEqual(normalize_result("accepted"), "PASS")
        self.assertEqual(normalize_result("FAIL-LOW"), "FAIL")
        self.assertEqual(normalize_result("reject"), "FAIL")
        self.assertEqual(normalize_result("REVIEW"), "REVIEW")
        self.assertEqual(normalize_result("HOLD"), "HOLD")
        self.assertEqual(normalize_result("INFO"), "INFO")


class NormalizeStationTests(unittest.TestCase):
    def test_normalizes_raw_station_headers(self):
        self.assertEqual(normalize_station_id("Torque Station 01", "Torque"), "STN-01")
        self.assertEqual(normalize_station_id("PRESS-FIT STN 03", "Press Fit"), "STN-03")
        self.assertEqual(normalize_station_id("LEAK TESTER L-2", "Leak"), "L-2")
        self.assertEqual(normalize_station_id("VISION INSPECTION (camera V4)", "Vision"), "V4")

    def test_falls_back_to_category_when_station_unknown(self):
        self.assertEqual(normalize_station_id("", "Functional"), "FTB-07")
        self.assertEqual(normalize_station_id(None, "Electrical"), "Electrical")


class LookupSpecTests(unittest.TestCase):
    def test_returns_expected_limits(self):
        self.assertEqual(lookup_spec("Torque", "Joint J1 torque"), (18, 19, 18.5, None))
        self.assertEqual(lookup_spec("Torque", "Joint J1 angle"), (42, 48, 45, None))
        self.assertEqual(lookup_spec("Press Fit", "Peak press force"), (4.5, 5.2, 4.85, None))
        self.assertEqual(lookup_spec("Leak", "Pressure drop"), (None, 1.5, 0, 10))

    def test_unknown_measurement_returns_all_none(self):
        self.assertEqual(lookup_spec("Pack-Out", "Package weight"), (None, None, None, None))


class EnrichMeasurementsTests(unittest.TestCase):
    def test_fills_defaults_specs_and_normalizes(self):
        enriched = enrich_measurements(
            [
                {
                    "serialNumber": "AX10001",
                    "stationId": "Torque Station 01",
                    "testCategory": "Torque",
                    "measurementName": "Joint J1 torque",
                    "measurementValue": 18.42,
                    "result": "OK",
                    "sourceRecordText": "raw line",
                }
            ]
        )
        row = enriched[0]

        self.assertEqual(row["result"], "PASS")
        self.assertEqual(row["stationId"], "STN-01")
        self.assertEqual(row["line"], "Line 2")
        self.assertEqual(row["shift"], "Day")
        self.assertEqual(row["lowerSpecLimit"], 18)
        self.assertEqual(row["upperSpecLimit"], 19)
        self.assertEqual(row["targetValue"], 18.5)

    def test_does_not_overwrite_existing_values(self):
        enriched = enrich_measurements(
            [
                {
                    "serialNumber": "AX10001",
                    "line": "Line 9",
                    "lowerSpecLimit": 1.0,
                    "testCategory": "Torque",
                    "measurementName": "Joint J1 torque",
                    "result": "PASS",
                    "sourceRecordText": "raw",
                    "stationId": "STN-01",
                }
            ]
        )
        row = enriched[0]

        self.assertEqual(row["line"], "Line 9")
        self.assertEqual(row["lowerSpecLimit"], 1.0)

    def test_propagates_single_work_order_to_blank_records(self):
        enriched = enrich_measurements(
            [
                {"serialNumber": "AX1", "workOrder": "NS-84721", "testCategory": "Torque", "measurementName": "t", "result": "PASS", "sourceRecordText": "a", "stationId": "STN-01"},
                {"serialNumber": "AX2", "testCategory": "Torque", "measurementName": "t", "result": "PASS", "sourceRecordText": "b", "stationId": "STN-01"},
                {"serialNumber": "AX3", "testCategory": "Torque", "measurementName": "t", "result": "PASS", "sourceRecordText": "c", "stationId": "STN-01"},
            ]
        )

        self.assertTrue(all(m["workOrder"] == "NS-84721" for m in enriched))

    def test_leaves_source_measurements_unmodified(self):
        source = [
            {
                "serialNumber": "AX10001",
                "testCategory": "Torque",
                "measurementName": "Joint J1 torque",
                "result": "OK",
                "sourceRecordText": "raw",
            }
        ]
        enrich_measurements(source)

        self.assertEqual(source[0]["result"], "OK")
        self.assertNotIn("line", source[0])


if __name__ == "__main__":
    unittest.main()
