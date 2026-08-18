import base64
import json
import logging
import os
import time
from typing import Any, Dict, List, NamedTuple, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

import azure.functions as func
from azure.core.exceptions import ResourceExistsError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

from src.data_mapping_mvp.csv_contract import (
    ValidationError,
    build_csv_content,
    map_measurements_resilient,
)
from src.data_mapping_mvp.enrichment import enrich_measurements

app = func.FunctionApp()


def _get_setting(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _get_blob_service_client() -> BlobServiceClient:
    account_name = _get_setting("AzureWebJobsStorage__accountName") or _get_setting("STORAGE_ACCOUNT_NAME")
    if account_name:
        account_url = f"https://{account_name}.blob.{os.getenv('STORAGE_ENDPOINT_SUFFIX', 'core.windows.net')}"
        return BlobServiceClient(account_url, credential=DefaultAzureCredential())
    connection_string = _get_setting("AzureWebJobsStorage")
    if connection_string:
        return BlobServiceClient.from_connection_string(connection_string)
    raise RuntimeError("Storage account is not configured (set AzureWebJobsStorage__accountName or AzureWebJobsStorage)")


def _write_blob_document(container_name: str, blob_name: str, content: str, content_type: str) -> str:
    if not container_name:
        raise ValueError("container_name is required")
    if not blob_name:
        raise ValueError("blob_name is required")

    blob_service = _get_blob_service_client()
    container_client = blob_service.get_container_client(container_name)
    try:
        container_client.create_container()
    except ResourceExistsError:
        pass

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
    attempts = int(_get_setting("CONTENT_UNDERSTANDING_POLL_ATTEMPTS", "90") or "90")
    interval = float(_get_setting("CONTENT_UNDERSTANDING_POLL_INTERVAL_SECONDS", "2") or "2")
    for _ in range(attempts):
        request = urllib_request.Request(operation_url, headers=headers, method="GET")
        try:
            with urllib_request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Content Understanding polling failed: {exc.code} - {body}") from exc

        status = str(payload.get("status", "")).lower()
        if status == "succeeded":
            return payload
        if status == "failed":
            raise RuntimeError(f"Content Understanding analysis failed: {payload}")

        time.sleep(interval)

    raise TimeoutError("Timed out waiting for Content Understanding analysis to complete")


def analyze_excel_blob(file_bytes: bytes, source_file: str) -> Dict[str, Any]:
    """Submit an Excel blob to the configured Content Understanding analyzer and return the result payload."""
    token = _get_content_understanding_token()
    url = _build_content_understanding_url()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    body = json.dumps({"inputs": [{"data": base64.b64encode(file_bytes).decode("ascii")}]}).encode("utf-8")
    request = urllib_request.Request(url, data=body, headers=headers, method="POST")
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


class PipelineOutput(NamedTuple):
    """Result of processing one upload: the CSV of valid rows plus quarantined records."""

    csv: str
    quarantined: List[Dict[str, Any]]


def process_canonical_payload(payload: Dict[str, Any]) -> PipelineOutput:
    """Convert a canonical payload into CSV rows, quarantining invalid records."""
    measurements = payload.get("measurements") if isinstance(payload, dict) else None
    if not isinstance(measurements, list) or not measurements:
        raise ValidationError("measurements must contain at least one record")
    rows, quarantined = map_measurements_resilient(measurements)
    return PipelineOutput(csv=build_csv_content(rows), quarantined=quarantined)


def process_analyzer_result(result: Dict[str, Any]) -> PipelineOutput:
    """Turn a Content Understanding response into the final CSV plus quarantined records."""
    payload = extract_canonical_payload_from_analyzer_result(result)
    payload["measurements"] = enrich_measurements(
        payload["measurements"],
        default_line=_get_setting("DEFAULT_LINE", "Line 2"),
        default_shift=_get_setting("DEFAULT_SHIFT", "Day"),
    )
    return process_canonical_payload(payload)


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


def build_quarantine_record(source_file: str, quarantined: List[Dict[str, Any]]) -> str:
    """Create a partial-failure record listing measurements that failed validation."""
    return json.dumps(
        {
            "sourceFile": source_file,
            "status": "partial",
            "quarantinedCount": len(quarantined),
            "records": quarantined,
        },
        indent=2,
    )


def _content_understanding_field_value(field: Any) -> Any:
    """Return the scalar/array/object value from a Content Understanding field object."""
    if not isinstance(field, dict):
        return None
    for key in (
        "valueString",
        "valueNumber",
        "valueInteger",
        "valueBoolean",
        "valueDate",
        "valueTime",
    ):
        if key in field:
            return field[key]
    if "valueArray" in field:
        return field["valueArray"]
    if "valueObject" in field:
        return field["valueObject"]
    return field.get("value")


def extract_canonical_payload_from_analyzer_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a Content Understanding response into the measurements payload used by the CSV mapper."""
    analyze = result.get("result", {}) if isinstance(result, dict) else {}
    contents = analyze.get("contents") or analyze.get("content") or []
    if not contents:
        raise ValueError("No content returned from Content Understanding analyzer")

    document = contents[0] or {}
    fields = document.get("fields") or {}
    raw_items = _content_understanding_field_value(fields.get("measurements")) or []

    measurements = []
    for item in raw_items:
        obj = item.get("valueObject") if isinstance(item, dict) else None
        if not isinstance(obj, dict):
            continue
        measurement = {
            key: _content_understanding_field_value(field_obj)
            for key, field_obj in obj.items()
        }
        measurements.append(measurement)

    return {"measurements": measurements}


@app.function_name(name="excel_to_csv_blob_processor")
@app.blob_trigger(
    arg_name="blob",
    path="raw/{name}.xlsx",
    connection="AzureWebJobsStorage",
    source=func.BlobSource.EVENT_GRID,
)
def process_excel_upload(blob: func.InputStream) -> None:
    """Azure Function trigger that processes a raw Excel upload into a CSV or failure record."""
    source_file = blob.name.split("/")[-1] if blob.name else "unknown.xlsx"
    logging.info("Received Excel upload: %s (%d bytes)", source_file, blob.length)

    try:
        analyzer_result = analyze_excel_blob(blob.read(), source_file)
        output = process_analyzer_result(analyzer_result)
        quarantine_json = (
            build_quarantine_record(source_file, output.quarantined)
            if output.quarantined
            else None
        )
        _write_success_and_failure_outputs(source_file, output.csv, quarantine_json)
        logging.info(
            "Processed upload %s: CSV written, %d record(s) quarantined",
            source_file,
            len(output.quarantined),
        )
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
    "PipelineOutput",
    "process_canonical_payload",
    "process_analyzer_result",
    "build_failed_record",
    "build_quarantine_record",
    "extract_canonical_payload_from_analyzer_result",
    "process_excel_upload",
    "analyze_excel_blob",
    "ValidationError",
]
