import json
import logging
from typing import Any, Dict, Optional

import azure.functions as func

from src.data_mapping_mvp.csv_contract import (
    ValidationError,
    build_csv_content,
    map_canonical_payload_to_csv,
)

app = func.FunctionApp()


def process_canonical_payload(payload: Dict[str, Any], source_file: str) -> str:
    """Convert a validated canonical payload into a single-row CSV payload."""
    row = map_canonical_payload_to_csv(payload, source_file=source_file)
    return build_csv_content([row])


def build_failed_record(source_file: str, error_message: str, payload: Optional[Dict[str, Any]] = None) -> str:
    """Create a failure payload that can be persisted to the failed container."""
    failure = {
        "sourceFile": source_file,
        "status": "failed",
        "error": error_message,
    }
    if payload is not None:
        failure["payload"] = payload
    return json.dumps(failure, indent=2)


def extract_canonical_payload_from_analyzer_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a Content Understanding response into the normalized payload used by the CSV mapper."""
    content = result.get("result", {}).get("content") or []
    if not content:
        raise ValueError("No content returned from Content Understanding analyzer")

    document = content[0]
    fields = document.get("fields") or {}

    def get_field_value(field_name: str, default: Any = None) -> Any:
        field = fields.get(field_name)
        if field is None:
            return default

        if "valueString" in field:
            return field["valueString"]
        if "valueNumber" in field:
            return field["valueNumber"]
        if "valueArray" in field:
            return field["valueArray"]
        if "valueObject" in field:
            return field["valueObject"]
        return default

    line_items = get_field_value("lineItems", [])
    normalized_items = []
    for item in line_items:
        item_fields = item.get("valueObject") or {}
        normalized_items.append(
            {
                "name": item_fields.get("name", {}).get("valueString"),
                "quantity": item_fields.get("quantity", {}).get("valueNumber"),
                "unitPrice": item_fields.get("unitPrice", {}).get("valueNumber"),
                "totalAmount": item_fields.get("totalAmount", {}).get("valueNumber"),
            }
        )

    return {
        "customerName": get_field_value("customerName"),
        "reportingPeriod": get_field_value("reportingPeriod"),
        "currency": get_field_value("currency"),
        "confidenceScore": get_field_value("confidenceScore"),
        "lineItems": normalized_items,
    }


@app.function_name(name="excel_to_csv_blob_processor")
@app.blob_trigger(arg_name="blob", path="raw/{name}.xlsx", connection="AzureWebJobsStorage")
def process_excel_upload(blob: func.InputStream) -> None:
    """Azure Function trigger scaffold for the Excel-to-CSV processing pipeline.

    The actual runtime flow is:
    1. read uploaded blob from raw/
    2. submit file to Content Understanding
    3. validate extracted canonical payload
    4. map to CSV contract
    5. write processed/ output or failed/ record
    """
    source_file = blob.name.split("/")[-1] if blob.name else "unknown.xlsx"
    logging.info("Received Excel upload: %s (%d bytes)", source_file, blob.length)

    # TODO: replace this placeholder with actual Content Understanding invocation.
    # The function should fetch the analyzer result, validate it, and then call
    # process_canonical_payload(...) or build_failed_record(...).
    return None


__all__ = [
    "app",
    "process_canonical_payload",
    "build_failed_record",
    "extract_canonical_payload_from_analyzer_result",
    "process_excel_upload",
    "ValidationError",
]
