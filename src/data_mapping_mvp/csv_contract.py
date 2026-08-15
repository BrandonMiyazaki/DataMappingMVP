from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Tuple


CSV_COLUMNS = [
    "Record_ID",
    "Event_Timestamp",
    "Work_Order",
    "Serial_Number",
    "Line",
    "Shift",
    "Station_ID",
    "Test_Category",
    "Measurement_Name",
    "Measurement_Value",
    "Measurement_Unit",
    "Lower_Spec_Limit",
    "Upper_Spec_Limit",
    "Target_Value",
    "Test_Duration_s",
    "Result",
    "Attempt_Number",
    "Error_Code",
    "Operator_ID",
    "Fixture_ID",
    "Recipe_ID",
    "Ambient_Temp_C",
    "Humidity_pct",
    "Source_Record_Text",
    "Notes",
]

# Fields the analyzer must supply for a record to be usable. Record_ID is
# assigned by the mapping layer, so it is not required from the source.
REQUIRED_FIELDS = [
    "serialNumber",
    "testCategory",
    "measurementName",
    "result",
    "sourceRecordText",
]

VALID_RESULTS = {"PASS", "FAIL", "REVIEW", "HOLD", "INFO"}

# Canonical measurement key -> output CSV column (Record_ID/Result handled explicitly).
_FIELD_TO_COLUMN = {
    "eventTimestamp": "Event_Timestamp",
    "workOrder": "Work_Order",
    "serialNumber": "Serial_Number",
    "line": "Line",
    "shift": "Shift",
    "stationId": "Station_ID",
    "testCategory": "Test_Category",
    "measurementName": "Measurement_Name",
    "measurementValue": "Measurement_Value",
    "measurementUnit": "Measurement_Unit",
    "lowerSpecLimit": "Lower_Spec_Limit",
    "upperSpecLimit": "Upper_Spec_Limit",
    "targetValue": "Target_Value",
    "testDurationSeconds": "Test_Duration_s",
    "attemptNumber": "Attempt_Number",
    "errorCode": "Error_Code",
    "operatorId": "Operator_ID",
    "fixtureId": "Fixture_ID",
    "recipeId": "Recipe_ID",
    "ambientTempC": "Ambient_Temp_C",
    "humidityPct": "Humidity_pct",
    "sourceRecordText": "Source_Record_Text",
    "notes": "Notes",
}

# Canonical keys whose values are numeric measurements.
_NUMERIC_FIELDS = {
    "measurementValue",
    "lowerSpecLimit",
    "upperSpecLimit",
    "targetValue",
    "testDurationSeconds",
    "ambientTempC",
    "humidityPct",
}


class ValidationError(ValueError):
    pass


def _normalize_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_number(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        raise ValidationError("numeric field cannot be a boolean")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    text = str(value).strip()
    if text == "":
        return ""
    try:
        number = float(text)
    except ValueError as exc:
        raise ValidationError(f"expected numeric value, got '{text}'") from exc
    return str(int(number)) if number.is_integer() else repr(number)


def _format_record_id(record_id: Any, index: int) -> str:
    existing = _normalize_string(record_id)
    if existing:
        return existing
    return f"REC-{index:04d}"


def map_measurement_to_csv_row(measurement: Dict[str, Any], index: int) -> Dict[str, str]:
    """Map one canonical measurement record to a standardized CSV row.

    ``index`` is 1-based and assigns Record_ID when the source omits it.
    """
    if not isinstance(measurement, dict):
        raise ValidationError("measurement must be an object")

    for field in REQUIRED_FIELDS:
        if not _normalize_string(measurement.get(field)):
            raise ValidationError(f"{field} is required")

    result = _normalize_string(measurement.get("result")).upper()
    if result not in VALID_RESULTS:
        raise ValidationError(
            f"result must be one of {sorted(VALID_RESULTS)}, got '{result}'"
        )

    row = {column: "" for column in CSV_COLUMNS}
    row["Record_ID"] = _format_record_id(measurement.get("recordId"), index)
    row["Result"] = result

    for field, column in _FIELD_TO_COLUMN.items():
        value = measurement.get(field)
        if field in _NUMERIC_FIELDS:
            row[column] = _normalize_number(value)
        else:
            row[column] = _normalize_string(value)

    return row


def map_measurements_payload_to_rows(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    """Map a canonical payload with a ``measurements`` array to CSV rows.

    Strict: raises ValidationError on the first invalid record.
    """
    if not isinstance(payload, dict):
        raise ValidationError("payload must be an object")

    measurements = payload.get("measurements")
    if not isinstance(measurements, list) or not measurements:
        raise ValidationError("measurements must contain at least one record")

    rows: List[Dict[str, str]] = []
    for offset, measurement in enumerate(measurements, start=1):
        rows.append(map_measurement_to_csv_row(measurement, offset))
    return rows


def map_measurements_resilient(
    measurements: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    """Map measurements one at a time, quarantining invalid records.

    Returns ``(rows, quarantined)`` where ``rows`` are valid CSV rows with
    sequential Record_IDs and ``quarantined`` is a list of
    ``{"sourceIndex", "error", "measurement"}`` for records that failed validation.
    """
    rows: List[Dict[str, str]] = []
    quarantined: List[Dict[str, Any]] = []
    for source_index, measurement in enumerate(measurements, start=1):
        try:
            rows.append(map_measurement_to_csv_row(measurement, len(rows) + 1))
        except ValidationError as exc:
            quarantined.append(
                {
                    "sourceIndex": source_index,
                    "error": str(exc),
                    "measurement": measurement,
                }
            )
    return rows, quarantined


def build_csv_content(rows: List[Dict[str, str]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()
