import json
import logging
import os
import time
from typing import Any, Dict, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

from src.data_mapping_mvp.csv_contract import (
    ValidationError,
    build_csv_content,
    map_canonical_payload_to_csv,
)

app = func.FunctionApp()


def _get_setting(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _get_blob_service_client() -> BlobServiceClient:
    connection_string = _get_setting("AzureWebJobsStorage")
    if not connection_string:
        raise RuntimeError("AzureWebJobsStorage is not configured")
    return BlobServiceClient.from_connection_string(connection_string)


def _write_blob_document(container_name: str, blob_name: str, content: str, content_type: str) -> str:
    if not container_name:
        raise ValueError("container_name is required")
    if not blob_name:
        raise ValueError("blob_name is required")

    blob_service = _get_blob_service_client()
    container_client = blob_service.get_container_client(container_name)
    container_client.create_container(exist_ok=True)

    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(
        content.encode("utf-8"),
        overwrite=True,
        content_settings=ContentSettings(content_type=content_type),
    )
    return blob_name


def _get_content_understanding_token() -> str:
    endpoint = _get_setting("CONTENT_UNDERSTANDING_ENDPOINT")
    if not endpoint:
        raise RuntimeError("CONTENT_UNDERSTANDING_ENDPOINT is not configured")

    credential = DefaultAzureCredential()
    token = credential.get_token("https://cognitiveservices.azure.com/.default")
    return token.token


def _build_content_understanding_url() -> str:
    endpoint = _get_setting("CONTENT_UNDERSTANDING_ENDPOINT")
    analyzer_id = _get_setting("CONTENT_UNDERSTANDING_ANALYZER_ID")
    api_version = _get_setting("CONTENT_UNDERSTANDING_API_VERSION", "2025-11-01")

    if not endpoint:
        raise RuntimeError("CONTENT_UNDERSTANDING_ENDPOINT is not configured")
    if not analyzer_id:
        raise RuntimeError("CONTENT_UNDERSTANDING_ANALYZER_ID is not configured")

    return f"{endpoint.rstrip('/')}/contentunderstanding/analyzers/{analyzer_id}:analyze?api-version={api_version}"


def _poll_content_understanding_operation(operation_url: str, token: str) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    for _ in range(12):
        request = urllib_request.Request(operation_url, headers=headers, method="GET")
        try:
            with urllib_request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Content Understanding polling failed: {exc.code} - {body}") from exc

        status = payload.get("status")
        if status == "succeeded":
            return payload
        if status == "failed":
            raise RuntimeError(f"Content Understanding analysis failed: {payload}")

        time.sleep(2)

    raise TimeoutError("Timed out waiting for Content Understanding analysis to complete")


def analyze_excel_blob(file_bytes: bytes, source_file: str) -> Dict[str, Any]:
    """Submit an Excel blob to the configured Content Understanding analyzer and return the result payload."""
    token = _get_content_understanding_token()
    url = _build_content_understanding_url()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
        "x-ms-file-name": source_file,
        "Accept": "application/json",
    }

    request = urllib_request.Request(url, data=file_bytes, headers=headers, method="POST")
    try:
        with urllib_request.urlopen(request, timeout=60) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            if response_body:
                payload = json.loads(response_body)
            else:
                payload = {}
            operation_location = response.headers.get("Operation-Location") or response.headers.get("operation-location")
            if operation_location:
                return _poll_content_understanding_operation(operation_location, token)
            return payload
    except urllib_error.HTTPError as exc:
        response_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Content Understanding request failed: {exc.code} - {response_text}") from exc


def _write_success_and_failure_outputs(source_file: str, csv_output: str, failure_json: Optional[str] = None) -> None:
    processed_container = _get_setting("PROCESSED_CONTAINER", "processed")
    failed_container = _get_setting("FAILED_CONTAINER", "failed")

    processed_name = source_file.rsplit(".", 1)[0] + ".csv" if "." in source_file else f"{source_file}.csv"
    _write_blob_document(processed_container, processed_name, csv_output, "text/csv")

    if failure_json is not None:
        failed_name = source_file.rsplit(".", 1)[0] + ".error.json" if "." in source_file else f"{source_file}.error.json"
        _write_blob_document(failed_container, failed_name, failure_json, "application/json")


def process_canonical_payload(payload: Dict[str, Any], source_file: str) -> str:
    """Convert a validated canonical payload into a single-row CSV payload."""
    row = map_canonical_payload_to_csv(payload, source_file=source_file)
    return build_csv_content([row])


def process_analyzer_result(result: Dict[str, Any], source_file: str) -> str:
    """Turn a Content Understanding response into the final CSV output expected by the pipeline."""
    payload = extract_canonical_payload_from_analyzer_result(result)
    return process_canonical_payload(payload, source_file=source_file)


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
    """Azure Function trigger that processes a raw Excel upload into a CSV or failure record."""
    source_file = blob.name.split("/")[-1] if blob.name else "unknown.xlsx"
    logging.info("Received Excel upload: %s (%d bytes)", source_file, blob.length)

    try:
        analyzer_result = analyze_excel_blob(blob.read(), source_file)
        csv_output = process_analyzer_result(analyzer_result, source_file=source_file)
        _write_success_and_failure_outputs(source_file, csv_output)
        logging.info("Processed upload to CSV: %s", source_file)
    except (ValueError, TypeError, ValidationError, RuntimeError, TimeoutError) as exc:
        failure_json = build_failed_record(source_file, str(exc))
        logging.error("Upload failed for %s: %s", source_file, exc)

        try:
            _write_success_and_failure_outputs(source_file, "", failure_json)
        except Exception:  # pragma: no cover - best effort for the failure path
            logging.exception("Unable to write failed blob for %s", source_file)

    return None


__all__ = [
    "app",
    "process_canonical_payload",
    "process_analyzer_result",
    "build_failed_record",
    "extract_canonical_payload_from_analyzer_result",
    "process_excel_upload",
    "analyze_excel_blob",
    "ValidationError",
]
